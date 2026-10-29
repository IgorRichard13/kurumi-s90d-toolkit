/* Kurumi Saver: a chibi quicando nas bordas, estilo logo de DVD.
   O palco e fixo em 1920x1080 e escalado para a janela, como no Kurumi Home. */
(function () {
  'use strict';

  var STAGE_W = 1920;
  var STAGE_H = 1080;

  // Politica conservadora de burn-in para OLED: fundo preto, sem texto/logo
  // fixo e fade para preto aos 10 min. Nao e um limite da Samsung.
  var MAX_MS = 10 * 60 * 1000;
  var FADE_MS = 60 * 1000;

  var stage = document.getElementById('stage');
  var sprite = document.getElementById('sprite');
  var img = document.getElementById('chibi');
  var placeholder = document.getElementById('placeholder');

  var x = 120, y = 120;
  var vx = 4.2, vy = 3.4;
  var w = 220, h = 220;
  var last = 0;
  var startedAt = 0;
  var flipped = false;
  var scale = 1;

  function fit() {
    scale = Math.min(window.innerWidth / STAGE_W, window.innerHeight / STAGE_H);
    stage.style.transform = 'scale(' + scale + ')';
  }

  function measure() {
    // A altura do sprite pode incluir o placeholder ou margens; usamos a
    // dimensao real da imagem visivel para a borda de baixo.
    var visible = (img && img.offsetWidth) ? img : placeholder;
    w = visible.offsetWidth || 220;
    h = visible.offsetHeight || 220;
    if (x + w > STAGE_W) x = Math.max(0, STAGE_W - w);
    if (y + h > STAGE_H) y = Math.max(0, STAGE_H - h);
  }

  function flip() {
    flipped = !flipped;
    img.style.transform = flipped ? 'scaleX(-1)' : '';
  }

  function frame(now) {
    if (!startedAt) startedAt = now;
    var elapsed = now - startedAt;
    if (elapsed >= MAX_MS) {
      stage.style.opacity = '0';
      return;
    }
    if (elapsed > MAX_MS - FADE_MS) {
      stage.style.opacity = String((MAX_MS - elapsed) / FADE_MS);
    }
    if (!last) last = now;
    var dt = Math.min(40, now - last) / 16.667;
    last = now;

    x += vx * dt;
    y += vy * dt;

    if (x <= 0) { x = 0; vx = Math.abs(vx); flip(); }
    else if (x + w >= STAGE_W) { x = STAGE_W - w; vx = -Math.abs(vx); flip(); }
    if (y <= 0) { y = 0; vy = Math.abs(vy); }
    else if (y + h >= STAGE_H) { y = STAGE_H - h; vy = -Math.abs(vy); }

    sprite.style.transform = 'translate3d(' + x + 'px,' + y + 'px,0)';
    requestAnimationFrame(frame);
  }

  function start() {
    fit();
    window.addEventListener('resize', fit);
    measure();

    if (img.complete && img.naturalWidth) {
      placeholder.style.display = 'none';
    }
    img.onload = function () { placeholder.style.display = 'none'; measure(); };
    img.onerror = function () {
      img.style.display = 'none';
      placeholder.style.display = 'flex';
      measure();
    };

    requestAnimationFrame(frame);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
