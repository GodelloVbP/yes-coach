// The share image: a 1080 × 1350 picture of a finished day, drawn on a canvas. No page state, no outside requests.
// Used by the app as window.YC_SHARE. Fonts come from fonts/fonts.css, so they are loaded before drawing.
(function (root) {
  'use strict';
  var W = 1080, H = 1350, PAD = 72;
  var INK = '#26358f', POP = '#ff8a65', SOFT = '#c3c8e6', WHITE = '#ffffff';
  var HEAD = '"Barlow Condensed", "Arial Narrow", sans-serif';
  var BODY = '"Barlow", "Helvetica Neue", Arial, sans-serif';

  // 95 min -> "1 h 35", 42 min -> "42 min"
  function duration(min) {
    min = Math.round(min);
    if (min < 60) return min + ' min';
    var m = min % 60;
    return Math.floor(min / 60) + ' h' + (m ? ' ' + (m < 10 ? '0' : '') + m : '');
  }

  function loadFonts() {
    if (!root.document || !root.document.fonts) return Promise.resolve();
    var want = ['800 40px "Barlow Condensed"', 'italic 800 40px "Barlow Condensed"', '700 40px "Barlow Condensed"', '600 34px Barlow', '700 34px Barlow'];
    return Promise.all(want.map(function (f) { return root.document.fonts.load(f, 'Aa0'); })).then(function () { return root.document.fonts.ready; }).catch(function () {});
  }

  function skewRect(ctx, x, y, w, h, fill) {
    ctx.save();
    ctx.transform(1, 0, -0.25, 1, 0.25 * (y + h / 2), 0); // skewX(-14deg) around the middle of the box
    ctx.fillStyle = fill;
    ctx.fillRect(x, y, w, h);
    ctx.restore();
  }

  function fit(ctx, text, weight, maxW, size, min, family) {
    var s = size;
    for (; s > min; s -= 4) { ctx.font = weight + ' ' + s + 'px ' + family; if (ctx.measureText(text).width <= maxW) break; }
    ctx.font = weight + ' ' + s + 'px ' + family;
    return s;
  }

  function wrap(ctx, text, maxW, maxLines) {
    var words = String(text).replace(/\s+/g, ' ').trim().split(' ');
    var lines = [], cur = '';
    for (var i = 0; i < words.length; i += 1) {
      var next = cur ? cur + ' ' + words[i] : words[i];
      if (ctx.measureText(next).width > maxW && cur) { lines.push(cur); cur = words[i]; } else cur = next;
    }
    if (cur) lines.push(cur);
    if (lines.length > maxLines) { lines = lines.slice(0, maxLines); lines[maxLines - 1] = lines[maxLines - 1].replace(/\s*\S*$/, '') + '…'; }
    return lines;
  }

  /* data: { title, date (already formatted), minutes (number or null), sets, volume (kg or null),
             lines: [{ name, detail, sets, pr }], note, words: { time, sets, volume, pr, more, tagline } }
     opts: { weights: bool, note: bool }
     Up to 6 exercises (4 with a note) are a list with large type. More are two columns of tiles, each with the best set and the number of
     sets: up to 14 (12 with a note); beyond that the last tile says how many more. The canvas carries `layout` (what was drawn) for tests. */
  function render(data, opts) {
    opts = opts || {};
    return loadFonts().then(function () {
      var cv = root.document.createElement('canvas');
      cv.width = W; cv.height = H;
      var ctx = cv.getContext('2d');
      var wd = data.words || {};
      var note = opts.note && data.note ? String(data.note) : '';
      var lines = data.lines || [];
      var tiles = lines.length > (note ? 4 : 6);
      // With tiles the app's name goes to the top right and the date and title move up beside it: the exercises need the room
      var c = tiles ? { brand: 40, date: 92, dateSize: 36, title: 214, titleSize: 130, statsY: 250, statsH: 120, statsFs: 70, statsLab: 26, top: 404 }
                    : { brand: 60, date: 232, dateSize: 38, title: 372, titleSize: 150, statsY: 430, statsH: 150, statsFs: 84, statsLab: 30, top: 650 };
      ctx.fillStyle = INK; ctx.fillRect(0, 0, W, H);
      // a few slanted bars in the corner, the mark of the app
      skewRect(ctx, 780, -40, 70, 330, 'rgba(255,255,255,0.06)');
      skewRect(ctx, 880, -40, 70, 330, 'rgba(255,255,255,0.06)');
      skewRect(ctx, 980, -40, 70, 330, 'rgba(255,138,101,0.18)');

      // mark and name
      var bars = [[0, 12, 7, 16, WHITE], [9, 2, 9, 36, WHITE], [20, 12, 7, 16, POP], [29, 2, 9, 36, WHITE]];
      ctx.textBaseline = 'alphabetic';
      ctx.font = 'italic 800 48px ' + HEAD;
      var nameW = ctx.measureText('YES COACH!').width;
      var bx = tiles ? W - PAD - nameW - 110 : PAD;                               // left edge of the mark
      bars.forEach(function (b) { skewRect(ctx, bx + b[0] * 1.6, c.brand + b[1] * 1.6, b[2] * 1.6, b[3] * 1.6, b[4]); });
      ctx.fillStyle = WHITE;
      ctx.fillText('YES COACH!', bx + 110, c.brand + 52);

      // date and title
      ctx.fillStyle = SOFT; ctx.font = '700 ' + c.dateSize + 'px ' + HEAD;
      ctx.fillText(String(data.date || '').toUpperCase(), PAD, c.date);
      ctx.fillStyle = WHITE;
      fit(ctx, String(data.title || '').toUpperCase(), '800', W - 2 * PAD, c.titleSize, 70, HEAD);
      ctx.fillText(String(data.title || '').toUpperCase(), PAD, c.title);

      // numbers
      var stats = [];
      if (data.minutes != null) stats.push([duration(data.minutes), wd.time || 'Time']);
      stats.push([String(data.sets), wd.sets || 'Sets']);
      if (opts.weights !== false && data.volume != null) stats.push([Math.round(data.volume).toLocaleString('en').replace(/,/g, ' ') + ' kg', wd.volume || 'Volume']);
      var gap = 24, sw = (W - 2 * PAD - gap * (stats.length - 1)) / stats.length;
      stats.forEach(function (st, i) {
        var x = PAD + i * (sw + gap);
        skewRect(ctx, x, c.statsY, sw, c.statsH, 'rgba(255,255,255,0.10)');
        ctx.fillStyle = WHITE;
        fit(ctx, st[0], '800', sw - 60, c.statsFs, 40, HEAD);
        ctx.fillText(st[0], x + 28, c.statsY + Math.round(c.statsH * 0.587));
        ctx.fillStyle = SOFT; ctx.font = '700 ' + c.statsLab + 'px ' + HEAD;
        ctx.fillText(String(st[1]).toUpperCase(), x + 28, c.statsY + c.statsH - 18);
      });

      var layout = { mode: tiles ? 'tiles' : 'list', total: lines.length, shown: 0, more: 0, tiles: [], bottom: 0 };
      var next;
      if (!tiles) {
        // exercises as a list
        var rowH = 96, top = c.top;
        var shown = lines.slice(0, note ? 4 : 6);
        shown.forEach(function (l, i) {
          var y = top + i * rowH;
          ctx.fillStyle = 'rgba(255,255,255,0.18)'; ctx.fillRect(PAD, y + rowH - 10, W - 2 * PAD, 2);
          var x = PAD;
          if (l.pr) {
            skewRect(ctx, x, y + 14, 78, 54, POP);
            ctx.fillStyle = INK; ctx.font = '800 38px ' + HEAD; ctx.fillText(wd.pr || 'PR', x + 18, y + 54);
            x += 104;
          }
          var detail = opts.weights !== false ? l.detail : l.sets;
          ctx.font = '700 46px ' + HEAD;
          var dw = detail ? ctx.measureText(detail).width : 0;
          ctx.fillStyle = WHITE;
          fit(ctx, String(l.name).toUpperCase(), '800', W - PAD - x - dw - 40, 52, 30, HEAD);
          ctx.fillText(String(l.name).toUpperCase(), x, y + 58);
          if (detail) { ctx.font = '700 46px ' + HEAD; ctx.fillStyle = l.pr ? POP : SOFT; ctx.textAlign = 'right'; ctx.fillText(detail, W - PAD, y + 58); ctx.textAlign = 'left'; }
        });
        layout.shown = shown.length;
        next = top + shown.length * rowH;
      } else {
        // exercises as two columns of tiles, the first column filled first
        var slots = note ? 12 : 14;
        var over = lines.length > slots;
        var show = over ? lines.slice(0, slots - 1) : lines;
        var count = show.length + (over ? 1 : 0);
        var rows = Math.ceil(count / 2);
        var tgap = 14, cw = (W - 2 * PAD - tgap) / 2;
        var room = (note ? 1066 : 1228) - c.top;                                  // down to the footer, or to the room the note needs
        var th = Math.max(76, Math.min(150, Math.floor((room - tgap * (rows - 1)) / rows)));
        var nameSize = th >= 130 ? 48 : th >= 108 ? 42 : 36, subSize = th >= 130 ? 36 : th >= 108 ? 34 : 30;
        for (var i = 0; i < count; i += 1) {
          var col = i < rows ? 0 : 1, r = i % rows;
          var tx = PAD + col * (cw + tgap), ty = c.top + r * (th + tgap);
          var l = show[i];
          layout.tiles.push({ x: tx, y: ty, w: cw, h: th, more: !l });
          if (!l) {
            // the last tile says how many are not shown
            skewRect(ctx, tx, ty, cw, th, 'rgba(255,255,255,0.05)');
            ctx.fillStyle = SOFT; ctx.font = '800 ' + nameSize + 'px ' + HEAD;
            ctx.fillText((wd.more || '+ {0} more').replace('{0}', lines.length - show.length).toUpperCase(), tx + 66, ty + th / 2 + nameSize * 0.34);
            continue;
          }
          skewRect(ctx, tx, ty, cw, th, l.pr ? 'rgba(255,138,101,0.22)' : 'rgba(255,255,255,0.09)');
          skewRect(ctx, tx, ty, 8, th, l.pr ? POP : 'rgba(255,255,255,0.25)');
          ctx.fillStyle = l.pr ? POP : SOFT; ctx.font = '800 ' + Math.round(nameSize * 0.84) + 'px ' + HEAD;
          ctx.fillText(String(i + 1), tx + 26, ty + th * 0.4);
          var reserve = l.pr ? 130 : 100;
          ctx.fillStyle = WHITE;
          fit(ctx, String(l.name).toUpperCase(), '800', cw - reserve - 36, nameSize, 22, HEAD);
          ctx.fillText(String(l.name).toUpperCase(), tx + 66, ty + th * 0.43);
          var sub = opts.weights !== false ? [l.detail, l.sets].filter(Boolean).join('  ·  ') : String(l.sets || '');
          ctx.fillStyle = l.pr ? POP : SOFT; ctx.font = '700 ' + subSize + 'px ' + HEAD;
          ctx.fillText(String(sub).toUpperCase(), tx + 66, ty + th * 0.82);
          if (l.pr) {
            skewRect(ctx, tx + cw - 62, ty + 10, 50, 32, POP);
            ctx.fillStyle = INK; ctx.font = '800 24px ' + HEAD; ctx.fillText(wd.pr || 'PR', tx + cw - 52, ty + 34);
          }
        }
        layout.shown = show.length; layout.more = over ? lines.length - show.length : 0;
        next = c.top + rows * (th + tgap) - tgap + 40;
      }
      layout.bottom = next;
      if (!tiles && lines.length > layout.shown) {
        ctx.fillStyle = SOFT; ctx.font = '700 38px ' + HEAD;
        layout.more = lines.length - layout.shown;
        ctx.fillText((wd.more || '+ {0} more').replace('{0}', layout.more), PAD, next + 48);
        next += 96;
      }
      if (note) {
        ctx.fillStyle = WHITE; ctx.font = 'italic 600 36px ' + BODY;
        wrap(ctx, '“' + note + '”', W - 2 * PAD, 3).forEach(function (ln, i) { ctx.fillText(ln, PAD, next + 40 + i * 48); });
      }
      // footer
      ctx.fillStyle = SOFT; ctx.font = '700 34px ' + HEAD;
      ctx.fillText(String(wd.tagline || 'Free forever. No tracking, no ads.').toUpperCase(), PAD, H - 64);
      cv.layout = layout;
      return cv;
    });
  }

  function toBlob(cv) {
    return new Promise(function (res, rej) { cv.toBlob(function (b) { b ? res(b) : rej(new Error('no image')); }, 'image/png'); });
  }

  root.YC_SHARE = { render: render, toBlob: toBlob, duration: duration, W: W, H: H };
  if (typeof module !== 'undefined' && module.exports) module.exports = root.YC_SHARE;
})(typeof window !== 'undefined' ? window : globalThis);
