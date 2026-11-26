"""The share picture shows every exercise up to 14: a list with large type for up to 6 (4 with a note), then two columns of tiles with the
best set and the number of sets. Nothing runs into the footer or the note; beyond 14 (10 with a note) the last tile says how many more."""
import subprocess, time, json
from playwright.sync_api import sync_playwright
from harness import *

NAMES = ['Assisted pull-up', 'Lat pulldown', 'Seated cable row', 'Machine chest press', 'Incline dumbbell bench press', 'Assisted dips', 'One-handed dumbbell row',
         'Machine chest fly', 'Face pull', 'Tricep extension', 'Dumbbell preacher curl', 'Lateral raise', 'Cable crunch', 'Cross armed extension', 'Hanging leg raise', 'Plank']

RUN = """async ([n, note, weights]) => {
  const names = NAMES_JSON;
  const lines = names.slice(0, n).map((name, i) => ({ name, detail: (10 + i) + ' @ ' + (20 + i) + ' kg', sets: i % 4 === 3 ? '2 sets' : '3 sets', pr: i === 4 || i === 8 }));
  const cv = await window.YC_SHARE.render({ title: 'Upper A', date: 'Thursday 19 Nov', minutes: 84, sets: 38, volume: 6420, note: note ? 'Slept badly, shoulder felt fine, will push the incline next week.' : '', lines,
    words: { time: 'Time', sets: 'Working sets', volume: 'Volume', pr: 'PR', more: '+ {0} more', tagline: 'Free forever. No tracking, no ads.' } }, { weights: weights !== false, note: !!note });
  const g = cv.getContext('2d');
  // text pixels (near white) inside each tile's name band
  const ink = (t) => { const d = g.getImageData(Math.round(t.x + 60), Math.round(t.y + 4), Math.round(Math.min(t.w - 80, 300)), Math.round(t.h * 0.5)).data; let k = 0; for (let i = 0; i < d.length; i += 4) if (d[i] > 225 && d[i + 1] > 225 && d[i + 2] > 225) k += 1; return k; };
  return { w: cv.width, h: cv.height, layout: cv.layout, ink: cv.layout.tiles.map(ink) };
}""".replace("NAMES_JSON", json.dumps(NAMES))

server = serve()
try:
    with sync_playwright() as pw:
        be = Backend()
        be.docs.append({'path': 'yc', 'data': {'app': 'yes-coach', 'schema': 1, 'intro_seen': True}})
        def sc(page):
            run = lambda n, note=False, weights=True: page.evaluate(RUN, [n, note, weights])
            for n in (1, 3, 6):
                r = run(n)
                check('%d exercises: the list, all shown, 1080 x 1350' % n, r['layout']['mode'] == 'list' and r['layout']['shown'] == n and r['w'] == 1080 and r['h'] == 1350, r['layout'])
            for n in (7, 10, 14):
                r = run(n); L = r['layout']
                check('%d exercises: tiles, every one shown' % n, L['mode'] == 'tiles' and L['shown'] == n and L['more'] == 0 and len(L['tiles']) == n, L)
                check('%d: the picture stays 1080 x 1350' % n, r['w'] == 1080 and r['h'] == 1350)
                check('%d: clear space above the footer' % n, max(t['y'] + t['h'] for t in L['tiles']) <= 1230, max(t['y'] + t['h'] for t in L['tiles']))
                check('%d: every tile has its name drawn' % n, all(k > 40 for k in r['ink']), r['ink'])
                overlap = [(a, b) for a in L['tiles'] for b in L['tiles'] if a is not b and a['x'] < b['x'] + b['w'] and b['x'] < a['x'] + a['w'] and a['y'] < b['y'] + b['h'] and b['y'] < a['y'] + a['h']]
                check('%d: two columns and no tile overlaps another' % n, not overlap and len({t['x'] for t in L['tiles']}) == 2, (len(overlap), L['tiles'][:2]))
            r = run(14, weights=False); check('without weights it still draws all 14', r['layout']['shown'] == 14 and all(k > 40 for k in r['ink']), r['ink'])
            r = run(14); L = r['layout']
            check('the header is compact with tiles: the first tile starts at 404', L['tiles'][0]['y'] == 404, L['tiles'][0])
            r = run(16); L = r['layout']
            check('16 exercises: 13 tiles and one that says 3 more', L['shown'] == 13 and L['more'] == 3 and len(L['tiles']) == 14 and L['tiles'][-1]['more'], L)
            # with a note
            r = run(4, note=True); check('4 exercises with a note: still the list', r['layout']['mode'] == 'list' and r['layout']['shown'] == 4, r['layout'])
            r = run(5, note=True); check('5 exercises with a note: tiles', r['layout']['mode'] == 'tiles' and r['layout']['shown'] == 5, r['layout'])
            r = run(12, note=True); L = r['layout']
            check('12 exercises with a note: all shown, the note fits under them', L['shown'] == 12 and L['more'] == 0 and L['bottom'] + 40 + 2 * 48 <= 1262, (L['shown'], L['bottom']))
            check('12 with a note: every tile has its name drawn', all(k > 40 for k in r['ink']), r['ink'])
            r = run(14, note=True); L = r['layout']
            check('14 exercises with a note: 11 tiles and 3 more', L['shown'] == 11 and L['more'] == 3, L)
        errs = session(pw, be, ALICE, sc, width=390); check('no page errors', not errs, errs)
finally:
    server.terminate()
done()
