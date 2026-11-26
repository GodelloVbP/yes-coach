#!/usr/bin/env python3
"""Build, then run the tests a change can affect, in parallel.

  python3 tests/run.py              the tests that touch what changed since origin/main (committed or not), plus the fast Node tests
  python3 tests/run.py --list       only say which tests that is, and why
  python3 tests/run.py --all        every test (what a release or a change to the test setup needs)
  python3 tests/run.py --map        run every test with code coverage and rebuild tests/affected-map.json from scratch
  options: --base REF (default origin/main), -j N (parallel browsers, default 3), --no-update (leave the map alone)

How a change picks its tests: while a browser test runs, tests/e2e/cover.py records which lines of the app it ran (JavaScript and CSS, as
hashes of the line text, so moved lines still match). tests/affected-map.json keeps, per line, the tests that ran it. A changed line selects
the tests that ran it (the old text of a removed or changed line, the new text of an added one); new code no test has run yet is judged by
the lines around it; code almost every test runs (start-up, data tables) runs a small broad set; a change to the page's markup, the test
setup or a file the map knows nothing about runs everything. After a green run the map is refreshed for the tests that ran.
"""
import argparse, concurrent.futures, hashlib, json, os, pathlib, queue, re, shutil, subprocess, sys, tempfile, threading, time

ROOT = pathlib.Path(__file__).resolve().parents[1]
E2E = ROOT / 'tests' / 'e2e'
MAP = ROOT / 'tests' / 'affected-map.json'
MIN_LEN = 12
CORE = 0.7      # a line that this share of the tests ran is start-up or data: a change there runs the smoke set
SMOKE_N = 8
OK = re.compile(r'^(passed|\d+ .*passed)', re.M)

def sh(*cmd, cwd=ROOT, check=False):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check)

def h(line): return hashlib.sha1(line.encode()).hexdigest()[:8]
def sha(path): return hashlib.sha1(pathlib.Path(path).read_bytes()).hexdigest()[:10]

# ------------------------------------------------------------------ the map
def load_map():
    try:
        m = json.loads(MAP.read_text())
        return m if m.get('version') == 1 else None
    except Exception:
        return None

def empty_map(): return {'version': 1, 'commit': '', 'order': [], 'tests': {}, 'index': {}, 'smoke': []}

def bit(m, name):
    if name not in m['order']: m['order'].append(name)
    return 1 << m['order'].index(name)

def tests_of(m, mask): return {n for i, n in enumerate(m['order']) if mask >> i & 1}

def absorb(m, name, cov, dur, test_sha):
    """Replace one test's entry with what it just ran."""
    b = bit(m, name)
    for f, hs in list(m['index'].items()):
        for k in list(hs):
            v = int(hs[k], 16) & ~b
            if v: hs[k] = format(v, 'x')
            else: del hs[k]
        if not hs: del m['index'][f]
    n = 0
    for f, hashes in cov.items():
        if f == '_fetched': continue
        d = m['index'].setdefault(f, {})
        for k in hashes:
            d[k] = format(int(d.get(k, '0'), 16) | b, 'x'); n += 1
    m['tests'][name] = {'sha': test_sha, 'dur': round(dur, 1), 'cov': True, 'lines': n, 'fetched': sorted(cov.get('_fetched', []))}

def finish_map(m):
    m['commit'] = sh('git', 'rev-parse', '--short', 'HEAD').stdout.strip()
    # the smoke set: a few cheap tests that between them run as many different lines as possible (greedy, by new lines per second), so a
    # change in start-up or data code still meets a broad sample of the app
    universe = {(f, k): int(v, 16) for f, hs in m['index'].items() for k, v in hs.items()}
    chosen, left = [], set(universe)
    for _ in range(SMOKE_N):
        best, gain = None, 0
        for n in m['order']:
            if n not in m['tests'] or n in chosen: continue
            i = m['order'].index(n)
            g = sum(1 for key in left if universe[key] >> i & 1) / max(8.0, m['tests'][n].get('dur', 30))
            if g > gain: best, gain = n, g
        if best is None: break
        i = m['order'].index(best)
        chosen.append(best); left = {key for key in left if not universe[key] >> i & 1}
    m['smoke'] = chosen
    MAP.write_text(json.dumps(m, separators=(',', ':'), sort_keys=True) + '\n')

# ------------------------------------------------------------------ which tests
def changed_files(base):
    out = set(sh('git', 'diff', '--name-only', base).stdout.split())
    out |= set(sh('git', 'ls-files', '-o', '--exclude-standard').stdout.split())
    return sorted(out)

# browser tests that do not go through the shared harness, so no coverage is recorded: the files each one is about
STATIC = {'e2e_consent': [r'consent\.html$', r'config\.js$', r'vendor/'], 'e2e_captcha': [r'captcha\.js$', r'config\.js$'],
          'e2e_landing': [r'index\.html$', r'i18n'], 'e2e_langonly': [r'i18n', r'index\.html$']}
ALL_TRIGGERS = re.compile(r'^(build\.py|tests/run\.(py|sh)|tests/e2e/(harness|cover)\.py)$')
IGNORED = re.compile(r'^(.*\.(md|sql|png|webp|woff2|txt)|\.gitignore|\.nojekyll|supabase/.*|tools/.*|fonts/.*|shots/.*|tests/affected-map\.json|src/yes-coach\.html|tests/[a-z]+\.test\.mjs|tests/e2e/__pycache__/.*|manifest\.webmanifest|privacy\.html|connect\.html|CONTRIBUTING.*|.*_AUDIT.*|DESIGN_.*|PLAN_MAKER.*)$')

def regions(text):
    """'m' markup, 's' script, 'c' style, for each line."""
    out, mode = [], 'm'
    for ln in text.split('\n'):
        low = ln.lower()
        if mode == 'm':
            if re.search(r'<script\b(?![^>]*\bsrc=)[^>]*>', low) and '</script>' not in low: mode = 's'
            elif re.search(r'<style\b[^>]*>', low) and '</style>' not in low: mode = 'c'
            out.append('m')
        else:
            if (mode == 's' and '</script>' in low) or (mode == 'c' and '</style>' in low): mode = 'm'; out.append('m')
            else: out.append(mode)
    return out

def hunks(base, path):
    """[(removed lines, added lines, context lines before/after, regions touched)] from git diff, with 6 lines of context."""
    new = (ROOT / path).read_text(errors='replace') if (ROOT / path).exists() else ''
    old = sh('git', 'show', base + ':' + path).stdout
    rn, ro = regions(new), regions(old)
    diff = sh('git', 'diff', '-U6', '--no-color', base, '--', path).stdout
    res, cur = [], None
    for ln in diff.split('\n'):
        m = re.match(r'^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@', ln)
        if m:
            cur = {'rm': [], 'add': [], 'ctx': [], 'reg': set()}; res.append(cur)
            o, n = int(m.group(1)), int(m.group(2))
            continue
        if cur is None or ln.startswith('\\'): continue
        if ln.startswith('-') and not ln.startswith('---'):
            cur['rm'].append(ln[1:]); cur['reg'].add(ro[o - 1] if 0 < o <= len(ro) else 'm'); o += 1
        elif ln.startswith('+') and not ln.startswith('+++'):
            cur['add'].append(ln[1:]); cur['reg'].add(rn[n - 1] if 0 < n <= len(rn) else 'm'); n += 1
        elif ln.startswith(' '):
            cur['ctx'].append(ln[1:]); o += 1; n += 1
    return res

GENERATED = ('name="yc-build"', 'Content-Security-Policy')  # lines the build writes itself: the timestamp, and the script hash in the security header
def lines_of(ls): return [l.strip() for l in ls if len(l.strip()) >= MIN_LEN and not any(g in l for g in GENERATED)]

def select(base, m, names):
    """-> ({test: reason}, notes)"""
    sel, notes = {}, []
    def add(ts, why):
        for t in ts: sel.setdefault(t, why)
    files = changed_files(base)
    # a rebuild alone rewrites the timestamp and the script hash in the security header: that is not a change
    files = [f for f in files if not (f in m['index'] and f.endswith('.html') and not any(lines_of(hk['rm'] + hk['add']) for hk in hunks(base, f)))]
    live = {n for n in names}
    total = max(1, len(m['tests']))
    for n, deps in STATIC.items():  # tests the map has no coverage for follow the files they are about
        if n in live and any(re.match(d, f) for f in files for d in deps): sel.setdefault(n, 'about a file that changed')
    for f in files:
        mt = re.match(r'^tests/e2e/(e2e_\w+)\.py$', f)
        if mt:
            add({mt.group(1)} & live, 'its own file changed'); continue
        if ALL_TRIGGERS.match(f):
            return {n: 'test setup changed: ' + f for n in names}, notes
        if f in m['index']:
            for hk in hunks(base, f):
                if 'm' in hk['reg'] and f.endswith('.html'):
                    if not lines_of(hk['rm'] + hk['add']): continue
                    return {n: 'the markup of %s changed' % f for n in names}, notes
                direct = [h(l) for l in lines_of(hk['rm'] + hk['add'])]
                if not direct: continue
                masks = [int(m['index'][f].get(k, '0'), 16) for k in direct]
                known = [x for x in masks if x]
                core = [x for x in known if bin(x).count('1') >= CORE * total]
                hit = set()
                for x in known:
                    if x not in core: hit |= tests_of(m, x)
                new = [x for x in masks if not x]
                if new or core:
                    if core and not hit: notes.append('%s: start-up or data code changed, smoke set' % f); add(set(m['smoke']), 'start-up or data code in ' + f)
                    near = lines_of(hk['ctx'][:4] + hk['ctx'][-4:])
                    ctxm = [int(m['index'][f].get(h(l), '0'), 16) for l in near]
                    for x in ctxm:
                        if x and bin(x).count('1') < CORE * total: hit |= tests_of(m, x)
                    if new and not hit: notes.append('%s: new code with nothing known around it, smoke set' % f); add(set(m['smoke']), 'new code in ' + f)
                add(hit & live, 'ran lines changed in ' + f)
            continue
        fetched = {n for n, t in m['tests'].items() if f in t.get('fetched', [])}
        if fetched: add(fetched & live, 'loads ' + f); continue
        if IGNORED.match(f): continue
        return {n: 'a file the map knows nothing about changed: ' + f for n in names}, notes
    return sel, notes

# ------------------------------------------------------------------ running
def run_node(timeout=300):
    cmds = [['node', str(p)] for p in sorted((ROOT / 'tests').glob('*.test.mjs'))]
    cmds += [['node', '--experimental-strip-types', '--no-warnings', str(p)] for p in sorted((ROOT / 'supabase' / 'tests').glob('*.test.mjs'))]
    res = []
    for c in cmds:
        r = subprocess.run(c, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        res.append((pathlib.Path(c[-1]).name, r.returncode == 0, (r.stdout + r.stderr).strip().split('\n')[-1][:120]))
    return res

def run_e2e(name, port, cover_dir, attempt=1):
    env = dict(os.environ, YC_PORT=str(port), PYTHONDONTWRITEBYTECODE='1')
    if cover_dir: env['YC_COVER'] = cover_dir
    t0 = time.time()
    r = subprocess.run([sys.executable, name + '.py'], cwd=E2E, env=env, capture_output=True, text=True)
    out = r.stdout + r.stderr
    ok = r.returncode == 0 and bool(OK.search(out))
    return {'name': name, 'ok': ok, 'dur': time.time() - t0, 'out': out, 'code': r.returncode}

def main():
    ap = argparse.ArgumentParser(description='run the tests a change can affect')
    ap.add_argument('--all', action='store_true'); ap.add_argument('--map', action='store_true'); ap.add_argument('--list', action='store_true')
    ap.add_argument('--base', default='origin/main'); ap.add_argument('-j', type=int, default=3); ap.add_argument('--no-update', action='store_true')
    a = ap.parse_args()
    t_start = time.time()
    names = sorted(p.stem for p in E2E.glob('e2e_*.py'))
    if sh('git', 'rev-parse', '--verify', '-q', a.base).returncode: a.base = 'HEAD'
    b = subprocess.run([sys.executable, 'build.py'], cwd=ROOT, capture_output=True, text=True)
    if b.returncode: print(b.stdout, b.stderr); return 1
    m = load_map()
    reasons, notes = {}, []
    if a.all or a.map or not m:
        reasons = {n: ('--map' if a.map else '--all' if a.all else 'no map yet: run everything and build it') for n in names}
        if a.map or not m: m = empty_map()
    else:
        sel, notes = select(a.base, m, names)
        for n in names:  # new or edited tests, and tests the map has no coverage for, always run
            t = m['tests'].get(n)
            if t is None: sel.setdefault(n, 'not in the map yet')
            elif t['sha'] != sha(E2E / (n + '.py')): sel.setdefault(n, 'the test changed since the map')

        reasons = sel
    chosen = [n for n in names if n in reasons]
    chosen.sort(key=lambda n: -m['tests'].get(n, {}).get('dur', 30))  # the long ones first
    print('base %s, map from %s%s' % (a.base, m.get('commit') or 'nothing', ''))
    print('e2e: %d of %d tests' % (len(chosen), len(names)))
    why = {}
    for n in chosen: why.setdefault(reasons[n], []).append(n)
    for r, ns in sorted(why.items(), key=lambda kv: -len(kv[1])): print('  %s: %s' % (r, ', '.join(x.replace('e2e_', '') for x in ns[:12]) + (' …' if len(ns) > 12 else '')))
    for n in notes: print('  note:', n)
    if a.list: return 0
    cover = tempfile.mkdtemp(prefix='yc-cover-') if not a.no_update else None
    ports = queue.Queue()
    for i in range(a.j): ports.put(8800 + i)
    results, bad = {}, []
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.j + 1) as ex:
        node_f = ex.submit(run_node)
        def task(n):
            p = ports.get()
            try: return run_e2e(n, p, cover)
            finally: ports.put(p)
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=a.j)
        futs = [pool.submit(task, n) for n in chosen]
        for f in concurrent.futures.as_completed(futs):
            r = f.result(); results[r['name']] = r
            fails = [l for l in r['out'].split('\n') if l.startswith('FAIL')]
            last = [l for l in r['out'].split('\n') if OK.match(l)]
            print('%s %s (%.0fs) %s' % ('ok  ' if r['ok'] else 'FAIL', r['name'], r['dur'], last[-1] if last else ''), flush=True)
            if not r['ok']: bad.append(r['name'])
        pool.shutdown()
        node = node_f.result()
    for n, ok, last in node:
        print('%s node %s %s' % ('ok  ' if ok else 'FAIL', n, last))
        if not ok: bad.append('node:' + n)
    # a test that failed in a crowd gets one go on its own: parallel runs can be slow enough to trip a timeout
    for n in [x for x in bad if not x.startswith('node:')]:
        r = run_e2e(n, 8800, cover)
        print('%s %s alone (%.0fs)' % ('ok  ' if r['ok'] else 'FAIL', n, r['dur']))
        if r['ok']:
            print('  (it failed alongside the others and passed alone: a timing flake)'); bad.remove(n); results[n] = r
        else: results[n] = r
    for n in bad:
        r = results.get(n)
        if r: print('--- %s\n%s' % (n, '\n'.join([l for l in r['out'].split('\n') if l.startswith(('FAIL', 'PAGE ERRORS')) or 'Error' in l or 'Traceback' in l][:12])))
    if cover and not a.no_update:  # what a test that passed ran is true whatever the others did
        for n in [c for c in chosen if c not in bad]:
            f = pathlib.Path(cover) / (n + '.json')
            if f.exists():
                absorb(m, n, json.loads(f.read_text()), results[n]['dur'], sha(E2E / (n + '.py')))
            elif n not in m['tests']:
                m['tests'][n] = {'sha': sha(E2E / (n + '.py')), 'dur': round(results[n]['dur'], 1), 'cov': False, 'lines': 0, 'fetched': []}
                bit(m, n)
        for n in list(m['tests']):
            if n not in names: m['tests'].pop(n); [m['index'].pop(f) for f in list(m['index']) if not m['index'][f]]
        finish_map(m)
        print('map updated for %d tests' % len([c for c in chosen if c not in bad]))
    if cover: shutil.rmtree(cover, ignore_errors=True)
    print('%s in %.0fs: %d e2e files, %d node files' % ('FAILED' if bad else 'all passed', time.time() - t_start, len(chosen), len(node)))
    return 1 if bad else 0

if __name__ == '__main__':
    sys.exit(main())
