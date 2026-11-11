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
     opts: { weights: bool, note: bool } */
  function render(data, opts) {
    opts = opts || {};
    return loadFonts().then(function () {
      var cv = root.document.createElement('canvas');
      cv.width = W; cv.height = H;
      var ctx = cv.getContext('2d');
      var wd = data.words || {};
      ctx.fillStyle = INK; ctx.fillRect(0, 0, W, H);
      // a few slanted bars in the corner, the mark of the app
      skewRect(ctx, 780, -40, 70, 330, 'rgba(255,255,255,0.06)');
      skewRect(ctx, 880, -40, 70, 330, 'rgba(255,255,255,0.06)');
      skewRect(ctx, 980, -40, 70, 330, 'rgba(255,138,101,0.18)');

      // mark and name
      var bars = [[0, 12, 7, 16, WHITE], [9, 2, 9, 36, WHITE], [20, 12, 7, 16, POP], [29, 2, 9, 36, WHITE]];
      bars.forEach(function (b) { skewRect(ctx, PAD + b[0] * 1.6, 60 + b[1] * 1.6, b[2] * 1.6, b[3] * 1.6, b[4]); });
      ctx.fillStyle = WHITE; ctx.textBaseline = 'alphabetic';
      ctx.font = 'italic 800 48px ' + HEAD; ctx.fillText('YES COACH!', PAD + 110, 112);

      // date and title
      ctx.fillStyle = SOFT; ctx.font = '700 38px ' + HEAD;
      ctx.fillText(String(data.date || '').toUpperCase(), PAD, 232);
      ctx.fillStyle = WHITE;
      fit(ctx, String(data.title || '').toUpperCase(), '800', W - 2 * PAD, 150, 70, HEAD);
      ctx.fillText(String(data.title || '').toUpperCase(), PAD, 372);

      // numbers
      var stats = [];
      if (data.minutes != null) stats.push([duration(data.minutes), wd.time || 'Time']);
      stats.push([String(data.sets), wd.sets || 'Sets']);
      if (opts.weights !== false && data.volume != null) stats.push([Math.round(data.volume).toLocaleString('en').replace(/,/g, ' ') + ' kg', wd.volume || 'Volume']);
      var gap = 24, sw = (W - 2 * PAD - gap * (stats.length - 1)) / stats.length;
      stats.forEach(function (s, i) {
        var x = PAD + i * (sw + gap);
        skewRect(ctx, x, 430, sw, 150, 'rgba(255,255,255,0.10)');
        ctx.fillStyle = WHITE;
        fit(ctx, s[0], '800', sw - 60, 84, 40, HEAD);
        ctx.fillText(s[0], x + 28, 518);
        ctx.fillStyle = SOFT; ctx.font = '700 30px ' + HEAD;
        ctx.fillText(String(s[1]).toUpperCase(), x + 28, 562);
      });

      // exercises
      var note = opts.note && data.note ? String(data.note) : '';
      var rowH = 96, top = 650, maxRows = note ? 4 : 6;
      var lines = data.lines || [];
      var shown = lines.length > maxRows ? lines.slice(0, maxRows - 1) : lines.slice(0, maxRows);
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
      var next = top + shown.length * rowH;
      if (lines.length > shown.length) {
        ctx.fillStyle = SOFT; ctx.font = '700 38px ' + HEAD;
        ctx.fillText((wd.more || '+ {0} more').replace('{0}', lines.length - shown.length), PAD, next + 48);
        next += rowH;
      }
      if (note) {
        ctx.fillStyle = WHITE; ctx.font = 'italic 600 36px ' + BODY;
        wrap(ctx, '“' + note + '”', W - 2 * PAD, 3).forEach(function (ln, i) { ctx.fillText(ln, PAD, next + 40 + i * 48); });
      }
      // footer
      ctx.fillStyle = SOFT; ctx.font = '700 34px ' + HEAD;
      ctx.fillText(String(wd.tagline || 'Free forever. No tracking, no ads.').toUpperCase(), PAD, H - 64);
      return cv;
    });
  }

  function toBlob(cv) {
    return new Promise(function (res, rej) { cv.toBlob(function (b) { b ? res(b) : rej(new Error('no image')); }, 'image/png'); });
  }

  root.YC_SHARE = { render: render, toBlob: toBlob, duration: duration, W: W, H: H };
  if (typeof module !== 'undefined' && module.exports) module.exports = root.YC_SHARE;
})(typeof window !== 'undefined' ? window : globalThis);
