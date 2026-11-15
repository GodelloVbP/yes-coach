"""Copy plancheck.js into the connector (supabase/functions/mcp/index.ts), between the PLANCHECK markers.
The Edge Function is pasted into Supabase as one file and cannot import from the site, so it carries this copy.
build.py runs this; tests/plancheck.test.mjs fails when the copy differs."""
import pathlib
HERE = pathlib.Path(__file__).resolve().parent.parent
BEGIN = '// PLANCHECK BEGIN: a copy of plancheck.js made by tools/sync_plancheck.py. Edit plancheck.js, then run python3 build.py.\n'
END = '// PLANCHECK END\n'

def block():
    src = (HERE / 'plancheck.js').read_text()
    return BEGIN + 'const PLANCHECK: any = (() => { const module: any = { exports: {} };\n' + src + 'return module.exports; })();\n' + END

def sync():
    p = HERE / 'supabase' / 'functions' / 'mcp' / 'index.ts'
    s = p.read_text()
    i, j = s.find(BEGIN), s.find(END)
    assert i >= 0 and j > i, 'PLANCHECK markers missing in index.ts'
    new = s[:i] + block() + s[j + len(END):]
    if new != s: p.write_text(new)
    return new != s

if __name__ == '__main__':
    print('updated' if sync() else 'already the same')
