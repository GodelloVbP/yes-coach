"""Which lines of the app does a test run? Switched on by YC_COVER=<folder>: the browser's own code coverage (JavaScript and CSS, through the
DevTools protocol) is collected while the test runs and written to <folder>/<test>.json as the lines that ran, each as a short hash of its
text, so the result survives line numbers moving. tests/run.py uses it to pick the tests a change can affect. Without YC_COVER nothing here runs."""
import os, sys, json, time, hashlib, bisect, pathlib, urllib.parse

OUT = os.environ.get('YC_COVER')
REPO = pathlib.Path(__file__).resolve().parents[2]
MIN_LEN = 12  # shorter lines (a closing brace, a bare else) say nothing and would match everything

_s = {'sessions': [], 'last': 0.0, 'js': {}, 'css': {}, 'sheets': {}, 'src': {}, 'lines': {}, 'texts': {}, 'fetched': set()}

def _h(line): return hashlib.sha1(line.encode()).hexdigest()[:8]

def attach(ctx, page):
    if not OUT: return
    _add(ctx, page)
    ctx.on('page', lambda pg: _add(ctx, pg) if pg is not page else None)
    for name in ('goto', 'reload'):
        orig = getattr(page, name)
        def wrapped(*a, _o=orig, **k):
            snap(0)
            return _o(*a, **k)
        setattr(page, name, wrapped)

def _add(ctx, page):
    try:
        page.on('request', lambda r: _s['fetched'].add(urllib.parse.urlparse(r.url).path.lstrip('/')) if r.url.startswith(('http://localhost', 'http://127.0.0.1')) else None)
        cdp = ctx.new_cdp_session(page)
        cdp.send('Profiler.enable'); cdp.send('Profiler.startPreciseCoverage', {'callCount': False, 'detailed': True})
        cdp.send('Debugger.enable')
        cdp.send('DOM.enable'); cdp.send('CSS.enable'); cdp.send('CSS.startRuleUsageTracking')
        cdp.on('CSS.styleSheetAdded', lambda e, _c=cdp: _s['sheets'].__setitem__((id(_c), e['header']['styleSheetId']), e['header']))
        _s['sessions'].append(cdp)
    except Exception:
        pass

def snap(every=0):
    """Take what ran since the last snapshot. Before a navigation and at the end; in between at most every `every` seconds (a page can also
    navigate by itself, and what ran in the page before it is lost unless it was taken)."""
    if not OUT or not _s['sessions']: return
    now = time.time()
    if every and now - _s['last'] < every: return
    _s['last'] = now
    for cdp in list(_s['sessions']):
        try:
            for sc in cdp.send('Profiler.takePreciseCoverage')['result']:
                url = sc['url']
                if not url.startswith('http://localhost') and not url.startswith('http://127.0.0.1'): continue
                key = (id(cdp), sc['scriptId'])
                if key not in _s['src']: _s['src'][key] = (url, cdp.send('Debugger.getScriptSource', {'scriptId': sc['scriptId']})['scriptSource'])
                src = _s['src'][key][1]
                arr = _s['js'].setdefault(key, bytearray(len(src)))
                one = bytearray(len(src))
                for fn in sc['functions']:  # parent ranges come before the ranges inside them: inner ones overwrite
                    for r in fn['ranges']:
                        one[r['startOffset']:r['endOffset']] = b'\x01' * (r['endOffset'] - r['startOffset']) if r['count'] > 0 else bytes(r['endOffset'] - r['startOffset'])
                for i, v in enumerate(one):
                    if v: arr[i] = 1
        except Exception:
            pass
        try:
            for r in cdp.send('CSS.takeCoverageDelta')['coverage']:
                if not r.get('used'): continue
                sid = r['styleSheetId']
                k = (id(cdp), sid)
                if k not in _s['texts']:
                    try: _s['texts'][k] = cdp.send('CSS.getStyleSheetText', {'styleSheetId': sid})['text']
                    except Exception: continue
                _s['css'].setdefault(k, []).append((r['startOffset'], r['endOffset']))
        except Exception:
            pass

def _file_for(url):
    path = urllib.parse.urlparse(url).path.lstrip('/') or 'index.html'
    f = REPO / path
    return (path, f.read_text(errors='replace')) if f.is_file() else (None, None)

def _lines_hit(text, spans):
    starts = [0]
    for i, ch in enumerate(text):
        if ch == '\n': starts.append(i + 1)
    out = set()
    for a, b in spans:
        la, lb = bisect.bisect_right(starts, a) - 1, bisect.bisect_right(starts, max(a, b - 1)) - 1
        for ln in range(la, lb + 1): out.add(ln)
    return starts, out

def finish():
    """Write the lines that ran: {file: [line hashes]}."""
    if not OUT: return
    snap(0)
    res = {}
    for key, arr in _s['js'].items():
        url, src = _s['src'][key]
        path, text = _file_for(url)
        if path is None: continue
        base = 0 if src == text else text.find(src)
        if base < 0: continue
        spans, i, n = [], 0, len(arr)
        while i < n:  # runs of covered characters
            if arr[i]:
                j = i
                while j < n and arr[j]: j += 1
                spans.append((base + i, base + j)); i = j
            else: i += 1
        lines = text.split('\n')
        _, hit = _lines_hit(text, spans)
        for ln in hit:
            t = lines[ln].strip()
            if len(t) >= MIN_LEN: res.setdefault(path, set()).add(_h(t))
    for key, spans in _s['css'].items():
        header = _s['sheets'].get(key)
        sheet = _s['texts'].get(key)
        if not header or not sheet: continue
        path, text = _file_for(header.get('sourceURL') or '')
        if path is None: continue
        lines = text.split('\n')
        sl = sheet.split('\n')
        off = header.get('startLine', 0)
        starts, hit = _lines_hit(sheet, spans)
        for ln in hit:
            if ln >= len(sl): continue
            t = sl[ln].strip()
            if len(t) >= MIN_LEN: res.setdefault(path, set()).add(_h(t))
    name = os.path.basename(sys.argv[0]).replace('.py', '')
    pathlib.Path(OUT).mkdir(parents=True, exist_ok=True)
    f = pathlib.Path(OUT) / (name + '.json')
    old = {}
    if f.exists():  # a test file runs several sessions: keep what the earlier ones ran
        try: old = {k: set(v) for k, v in json.loads(f.read_text()).items()}
        except Exception: old = {}
    for k, v in res.items(): old.setdefault(k, set()).update(v)
    old.setdefault('_fetched', set()).update(p for p in _s['fetched'] if p and not p.endswith('index.html'))
    f.write_text(json.dumps({k: sorted(v) for k, v in old.items()}))
    for k in ('js', 'css', 'sheets', 'src', 'texts', 'fetched'): _s[k].clear()
    _s['sessions'].clear()
