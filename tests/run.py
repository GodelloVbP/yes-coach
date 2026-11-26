#!/usr/bin/env python3
"""Build, then run the tests a change can affect, in parallel.

  python3 tests/run.py              the tests that touch what changed since origin/main (committed or not), plus the fast Node tests
  python3 tests/run.py --list       only say which tests that is, and why
  python3 tests/run.py --all        every test (what a release or a change to the test setup needs)
  python3 tests/run.py --map        run every test with code coverage and rebuild tests/affected-map.json from scratch
  --quick [SECONDS]  only as many of the selected tests as fit in about that time (default 120), the ones the change belongs to most first
  options: --base REF (default origin/main), -j N (parallel browsers, default 6), --no-update (leave the map alone)

How a change picks its tests: while a browser test runs, tests/e2e/cover.py records which lines of the app it ran (JavaScript and CSS, as
hashes of the line text, so moved lines still match). tests/affected-map.json keeps, per line, the tests that ran it. A changed line selects
the tests that ran it (the old text of a removed or changed line, the new text of an added one); new code no test has run yet is judged by
the lines around it; code almost every test runs (start-up, data tables) runs a small broad set; a change to the page's markup, the test
setup or a file the map knows nothing about runs everything. After a green run the map is refreshed for the tests that ran.
"""
import argparse, concurrent.futures, hashlib, json, os, pathlib, re, resource, shutil, socket, subprocess, sys, tempfile, time

ROOT = pathlib.Path(__file__).resolve().parents[1]
E2E = ROOT / 'tests' / 'e2e'
MAP = ROOT / 'tests' / 'affected-map.json'
MIN_LEN = 12
CORE = 0.7      # a line that this share of the tests ran is start-up or data: a change there runs the smoke set
SMOKE_N = 8
SHARD_SECONDS = 12   # a long file is split over workers so that each part takes about this long
MAX_SHARDS = 4
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

def empty_map(): return {'version': 1, 'commit': '', 'order': [], 'tests': {}, 'index': {}, 'smoke': [], 'noshard': []}

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

def i18n_tests(base, f, m):
    """Tests that loaded this language file and whose own text names a changed entry: the English text, or its translation. The tests about
    languages as such (e2e_lang*) are chosen by STATIC."""
    try:
        old = json.loads(sh('git', 'show', base + ':' + f).stdout or '{}')
        new = json.loads((ROOT / f).read_text())
    except Exception:
        return {n for n, t in m['tests'].items() if f in t.get('fetched', [])}  # unreadable: all that loaded it
    keys = [k for k in set(old) | set(new) if old.get(k) != new.get(k) and len(k) >= 6]
    vals = [new[k] for k in keys if isinstance(new.get(k), str) and len(new[k]) >= 6]
    out = set()
    for n, t in m['tests'].items():
        if f not in t.get('fetched', []): continue
        src = (E2E / (n + '.py')).read_text()
        if any(k in src for k in keys) or any(v in src for v in vals): out.add(n)
    return out

def select(base, m, names):
    """-> ({test: reason}, notes)"""
    sel, notes = {}, []
    score = {}  # how closely a change belongs to a test: 1 / (the number of tests that ran the line), summed
    def add(ts, why, w=0.0):
        for t in ts:
            sel.setdefault(t, why)
            score[t] = score.get(t, 0.0) + w
    files = changed_files(base)
    # a rebuild alone rewrites the timestamp and the script hash in the security header: that is not a change
    files = [f for f in files if not (f in m['index'] and f.endswith('.html') and not any(lines_of(hk['rm'] + hk['add']) for hk in hunks(base, f)))]
    live = {n for n in names}
    total = max(1, len(m['tests']))
    for n, deps in STATIC.items():  # tests the map has no coverage for follow the files they are about
        if n in live and any(re.match(d, f) for f in files for d in deps): add({n}, 'about a file that changed', 1.0)
    for f in files:
        mt = re.match(r'^tests/e2e/(e2e_\w+)\.py$', f)
        if mt:
            add({mt.group(1)} & live, 'its own file changed', 1e6); continue
        if ALL_TRIGGERS.match(f):
            return {n: 'test setup changed: ' + f for n in names}, notes, {}
        if f in m['index']:
            for hk in hunks(base, f):
                if 'm' in hk['reg'] and f.endswith('.html'):
                    if not lines_of(hk['rm'] + hk['add']): continue
                    return {n: 'the markup of %s changed' % f for n in names}, notes, {}
                direct = [h(l) for l in lines_of(hk['rm'] + hk['add'])]
                if not direct: continue
                masks = [int(m['index'][f].get(k, '0'), 16) for k in direct]
                known = [x for x in masks if x]
                core = [x for x in known if bin(x).count('1') >= CORE * total]
                hit = set()
                for x in known:
                    if x not in core:
                        ts = tests_of(m, x); hit |= ts
                        for t in ts: score[t] = score.get(t, 0.0) + 1.0 / len(ts)
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
        if re.match(r'^i18n/\w+\.json$', f):  # a translation file: the tests that ran in that language and mention a key or text that changed
            add(i18n_tests(base, f, m) & live, 'uses a translation that changed in ' + f); continue
        fetched = {n for n, t in m['tests'].items() if f in t.get('fetched', [])}
        if fetched: add(fetched & live, 'loads ' + f); continue
        if IGNORED.match(f): continue
        return {n: 'a file the map knows nothing about changed: ' + f for n in names}, notes, {}
    return sel, notes, score

# ------------------------------------------------------------------ running
def run_node(timeout=300):
    cmds = [['node', str(p)] for p in sorted((ROOT / 'tests').glob('*.test.mjs'))]
    cmds += [['node', '--experimental-strip-types', '--no-warnings', str(p)] for p in sorted((ROOT / 'supabase' / 'tests').glob('*.test.mjs'))]
    res = []
    for c in cmds:
        r = subprocess.run(c, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        res.append((pathlib.Path(c[-1]).name, r.returncode == 0, (r.stdout + r.stderr).strip().split('\n')[-1][:120]))
    return res

def free_port():
    with socket.socket() as sk:  # a port nobody holds, also when an earlier run left a server behind
        sk.bind(('127.0.0.1', 0))
        return sk.getsockname()[1]

def shards_for(m, name):
    """How many parts a file runs in: by how long it took last time. Files that did not survive being split are not."""
    if name in m.get('noshard', []): return 1
    if 'session(' not in (E2E / (name + '.py')).read_text(): return 1  # only the shared harness knows how to run part of a file
    dur = m['tests'].get(name, {}).get('dur', 0)
    return 1 if dur < 2 * SHARD_SECONDS - 4 else min(MAX_SHARDS, -(-int(dur) // SHARD_SECONDS))

def run_e2e(name, port, cover_dir, shard=None):
    env = dict(os.environ, YC_PORT=str(port), PYTHONDONTWRITEBYTECODE='1')
    if cover_dir: env['YC_COVER'] = cover_dir
    if shard: env['YC_SHARD'] = shard
    t0 = time.time()
    r = subprocess.run([sys.executable, name + '.py'], cwd=E2E, env=env, capture_output=True, text=True)
    out = r.stdout + r.stderr
    ok = r.returncode == 0 and bool(OK.search(out))
    return {'name': name, 'shard': shard, 'ok': ok, 'dur': time.time() - t0, 'out': out, 'code': r.returncode}

def main():
    ap = argparse.ArgumentParser(description='run the tests a change can affect')
    ap.add_argument('--all', action='store_true'); ap.add_argument('--map', action='store_true'); ap.add_argument('--list', action='store_true')
    ap.add_argument('--base', default='origin/main'); ap.add_argument('-j', type=int, default=6); ap.add_argument('--no-update', action='store_true')
    ap.add_argument('--quick', nargs='?', const=120, type=int, metavar='SECONDS', help='only as many of the selected tests as fit in this time (default 120), the ones the change belongs to most first')
    a = ap.parse_args()
    t_start = time.time()
    r0 = resource.getrusage(resource.RUSAGE_CHILDREN); cpu0 = r0.ru_utime + r0.ru_stime
    if a.base == 'origin/main': subprocess.run(['git', 'fetch', '-q', 'origin', 'main'], cwd=ROOT, capture_output=True, timeout=30)  # compare with the main of today
    names = sorted(p.stem for p in E2E.glob('e2e_*.py'))
    if sh('git', 'rev-parse', '--verify', '-q', a.base).returncode: a.base = 'HEAD'
    b = subprocess.run([sys.executable, 'build.py'], cwd=ROOT, capture_output=True, text=True)
    if b.returncode: print(b.stdout, b.stderr); return 1
    m = load_map()
    reasons, notes, score = {}, [], {}
    if a.all or a.map or not m:
        reasons = {n: ('--map' if a.map else '--all' if a.all else 'no map yet: run everything and build it') for n in names}
        if a.map or not m: m = empty_map()
    else:
        sel, notes, score = select(a.base, m, names)
        for n in names:  # new or edited tests, and tests the map has no coverage for, always run
            t = m['tests'].get(n)
            if t is None: sel.setdefault(n, 'not in the map yet')
            elif t['sha'] != sha(E2E / (n + '.py')): sel.setdefault(n, 'the test changed since the map')

        reasons = sel
    chosen = [n for n in names if n in reasons]
    skipped = []
    if a.quick and len(chosen) > 1:
        chosen.sort(key=lambda n: -score.get(n, 0.0))  # the closest to the change first
        used, keep = 0.0, []
        for n in chosen:
            est = m['tests'].get(n, {}).get('dur', 30) * 1.2 / a.j  # an estimate of the wall time it adds on a full set of workers
            if keep and used + est > a.quick: skipped.append(n); continue
            keep.append(n); used += est
        chosen = keep
    chosen.sort(key=lambda n: -m['tests'].get(n, {}).get('dur', 30))  # the long ones first
    print('base %s, map from %s%s' % (a.base, m.get('commit') or 'nothing', ''))
    print('e2e: %d of %d tests' % (len(chosen), len(names)))
    why = {}
    for n in chosen: why.setdefault(reasons[n], []).append(n)
    for r, ns in sorted(why.items(), key=lambda kv: -len(kv[1])): print('  %s: %s' % (r, ', '.join(x.replace('e2e_', '') for x in ns[:12]) + (' …' if len(ns) > 12 else '')))
    for n in notes: print('  note:', n)
    if skipped: print('  --quick left out %d of the selected tests to stay near %ds: %s (run without --quick for them)' % (len(skipped), a.quick, ', '.join(x.replace('e2e_', '') for x in skipped)))
    if a.list: return 0
    cover = tempfile.mkdtemp(prefix='yc-cover-') if not a.no_update else None
    plan = [(n, '%d/%d' % (i, k) if k > 1 else None) for n in chosen for k in [shards_for(m, n)] for i in range(k)]
    plan.sort(key=lambda t: -m['tests'].get(t[0], {}).get('dur', 30) / shards_for(m, t[0]))  # the long parts first
    print('running %d parts on %d workers' % (len(plan), a.j))
    results, bad, parts = {}, [], {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.j + 1) as ex:
        node_f = ex.submit(run_node)
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=a.j)
        futs = [pool.submit(lambda t: run_e2e(t[0], free_port(), cover, t[1]), t) for t in plan]
        for f in concurrent.futures.as_completed(futs):
            r = f.result(); parts.setdefault(r['name'], []).append(r)
            last = [l for l in r['out'].split('\n') if OK.match(l)]
            print('%s %s%s (%.0fs) %s' % ('ok  ' if r['ok'] else 'FAIL', r['name'], ' ' + r['shard'] if r['shard'] else '', r['dur'], last[-1] if last else ''), flush=True)
        pool.shutdown()
        node = node_f.result()
    for n, rs in parts.items():
        results[n] = {'name': n, 'ok': all(r['ok'] for r in rs), 'dur': sum(r['dur'] for r in rs), 'out': '\n'.join(r['out'] for r in rs)}
        if not results[n]['ok']: bad.append(n)
    for n, ok, last in node:
        print('%s node %s %s' % ('ok  ' if ok else 'FAIL', n, last))
        if not ok: bad.append('node:' + n)
    # a file that failed in a crowd gets one go on its own, whole: parallel runs can be slow enough to trip a timeout, and some files cannot
    # be split by scenario (their scenarios hand state to each other)
    for n in [x for x in bad if not x.startswith('node:')]:
        r = run_e2e(n, free_port(), cover)
        print('%s %s alone (%.0fs)' % ('ok  ' if r['ok'] else 'FAIL', n, r['dur']))
        if r['ok']:
            if any(p['shard'] for p in parts[n]):
                print('  (it failed split and passed whole: not split from now on)')
                m.setdefault('noshard', []).append(n)
            else: print('  (it failed alongside the others and passed alone: a timing flake)')
            bad.remove(n); results[n] = r
        else: results[n] = r
    for n in bad:
        r = results.get(n)
        if r: print('--- %s\n%s' % (n, '\n'.join([l for l in r['out'].split('\n') if l.startswith(('FAIL', 'PAGE ERRORS')) or 'Error' in l or 'Traceback' in l][:12])))
    if cover and not a.no_update:  # what a test that passed ran is true whatever the others did
        for n in [c for c in chosen if c not in bad]:
            fs = sorted(pathlib.Path(cover).glob(n + '.json')) + sorted(pathlib.Path(cover).glob(n + '.s*.json'))
            if fs:
                cov = {}
                for f in fs:
                    for k, v in json.loads(f.read_text()).items(): cov.setdefault(k, set()).update(v)
                absorb(m, n, cov, results[n]['dur'], sha(E2E / (n + '.py')))
            else:  # a test with no coverage of its own (it does not use the shared harness): remember that it passed as it is now
                t = m['tests'].setdefault(n, {'cov': False, 'lines': 0, 'fetched': []})
                t.update(sha=sha(E2E / (n + '.py')), dur=round(results[n]['dur'], 1))
                bit(m, n)
        for n in list(m['tests']):
            if n not in names: m['tests'].pop(n); [m['index'].pop(f) for f in list(m['index']) if not m['index'][f]]
        finish_map(m)
        print('map updated for %d tests' % len([c for c in chosen if c not in bad]))
    if cover: shutil.rmtree(cover, ignore_errors=True)
    u = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = u.ru_utime + u.ru_stime - cpu0
    print('%s in %.0fs: %d e2e files, %d node files; %.0f CPU seconds on %d cores (%.0f%% busy)' % ('FAILED' if bad else 'all passed', time.time() - t_start, len(chosen), len(node), cpu, os.cpu_count(), 100 * cpu / max(1, (time.time() - t_start) * os.cpu_count())))
    return 1 if bad else 0

if __name__ == '__main__':
    sys.exit(main())
