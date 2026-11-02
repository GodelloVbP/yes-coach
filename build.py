"""Build the web app (index.html) from the shared Yes Coach! source (src/yes-coach.html): adds the sign-in screen,
the Supabase layer and the install metadata. The artifact keeps running from the same source unchanged."""
import re, pathlib
HERE = pathlib.Path(__file__).parent
src = (HERE / 'src' / 'yes-coach.html').read_text()
brand = re.search(r'<h1 class="brand">.*?</h1>', src, re.S).group(0)

head = '''<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" type="image/png" href="icon-192.png">
<link rel="apple-touch-icon" href="icon-180.png">
<meta name="theme-color" content="#26358f">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Yes Coach">
<meta name="description" content="A free, ad-free workout tracker: log sets, plan your week, track your progress and what you eat.">
<style>
body.signed-out #stick, body.signed-out main, body.signed-out #resume, body.signed-out #restbar { display: none !important; }
.auth { padding-block: 2rem 3rem; display: flex; flex-direction: column; gap: 1rem; max-width: 26rem; }
.auth h2 { font-size: var(--t4); }
.au-form { display: flex; flex-direction: column; gap: 0.875rem; }
.au-form input { font: inherit; font-size: var(--t3); font-weight: 600; color: var(--ink); background: transparent; border: 0; border-bottom: 2px solid var(--ctl); border-radius: 0; min-height: 44px; padding: 0.25rem 0; width: 100%; }
.au-form input:focus { outline: none; border-bottom-color: var(--ink); box-shadow: 0 1px 0 var(--ink); }
#au-msg { min-height: 1.5em; }
#au-msg.bad { color: var(--warn); font-weight: 600; }
</style>
'''
auth = f'''<section class="auth in" id="auth" hidden aria-labelledby="au-h">
  {brand}
  <h2 id="au-h">Sign in</h2>
  <p class="note">A free, ad-free workout tracker. Your account keeps your log and plan in sync between your devices.</p>
  <form id="au-form" class="au-form" novalidate>
    <label class="ed-f" id="au-email-f"><span class="lab">Email</span><input id="au-email" type="email" autocomplete="email" inputmode="email"></label>
    <label class="ed-f" id="au-pass-f"><span class="lab">Password</span><input id="au-pass" type="password" autocomplete="current-password"></label>
    <button class="skew pop big" type="submit" id="au-go"><span>Sign in</span></button>
    <p class="note" id="au-msg" aria-live="polite"></p>
    <div class="foot-row"><button class="textbtn" type="button" id="au-alt"></button><button class="textbtn" type="button" id="au-forgot">Forgot password?</button></div>
  </form>
  <p class="note"><a class="link" href="privacy.html">Privacy</a></p>
</section>
'''
def once(s, old, new):
    assert s.count(old) == 1, old[:60]
    return s.replace(old, new)
# The source starts with the claude.ai page skeleton (<html><head>…</head><body>), so the title and links sit in <body>.
# iPhones read the home-screen icon only from <head>: build a real head and move the title and install metadata into it.
skel = re.match(r'<!doctype html><html><head>(.*?)</head><body>\s*<title>Yes Coach!</title>', src, re.S)
assert skel, 'unexpected start of the source'
base_style = re.search(r'<style>.*?</style>', skel.group(1), re.S).group(0)
out = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
       '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
       + base_style + '\n<title>Yes Coach!</title>\n' + head + '</head><body class="signed-out">' + src[skel.end():])
out = once(out, '<div class="stick" id="stick">', auth + '<div class="stick" id="stick">')
out = once(out, '<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>',
           '<script src="config.js"></script>\n<script src="vendor/supabase.js"></script>\n<script src="web.js"></script>\n<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>')
(HERE / 'index.html').write_text(out)
print('index.html', len(out) // 1000, 'kB')
