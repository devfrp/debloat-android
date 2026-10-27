// debloat-android: le champ de noms de paquets du hero, le switcher Sûr / Avancé,
// les touches Copier et la touche de téléchargement de ton système mise en avant.
document.documentElement.classList.add('js');

(() => {
  // ------------------------------------------------------------- field
  const canvas = document.querySelector('.field');
  const hero = document.querySelector('.hero');
  if (!canvas || !hero) return;
  const ctx = canvas.getContext('2d');
  const css = getComputedStyle(document.documentElement);
  const tint = ['--color-glyph-1', '--color-glyph-2', '--color-glyph-3', '--color-glyph-4', '--color-accent-deep']
    .map((t) => css.getPropertyValue(t).trim());
  const font = css.getPropertyValue('--font-outlier').trim();
  // The bloat the app removes, as the field's text: raw on the left, cleared on the right.
  const text = ('com.samsung.android.app.spage com.facebook.appmanager com.facebook.services ' +
    'com.samsung.android.game.gamehome com.miui.msa.global com.samsung.android.bixby.agent ' +
    'com.netflix.mediaclient com.microsoft.skydrive com.samsung.android.arzone com.miui.analytics ' +
    'com.huawei.appmarket com.coloros.gamespace com.samsung.android.app.tips com.facebook.system ').repeat(4);
  const CW = 8, CH = 16;
  const reduce = matchMedia('(prefers-reduced-motion: reduce)');
  let cols = 0, rows = 0, dpr = 1, avoid = [], pointer = null, t = 0, visible = true, last = 0;

  function noise(x, y, z) {
    return (Math.sin(x * 0.19 + z) + Math.sin(y * 0.37 - z * 0.7) + Math.sin((x + y) * 0.11 + z * 0.5)) / 3;
  }
  function rects() {
    const h = hero.getBoundingClientRect();
    // the field keeps to two bands above and below the content, so no glyph sits by the type
    const rs = [...hero.querySelectorAll('.hero-text, .hero-shot')].map((el) => el.getBoundingClientRect());
    if (!rs.length) { avoid = []; return; }
    const left = Math.min(...rs.map((r) => r.left)), right = Math.max(...rs.map((r) => r.right));
    const top = Math.min(...rs.map((r) => r.top)), bottom = Math.max(...rs.map((r) => r.bottom));
    avoid = [{ x0: -1, x1: cols + 1, y0: (top - h.top) / CH - 3, y1: (bottom - h.top) / CH + 3 }];
  }
  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = hero.clientWidth, h = hero.clientHeight;
    canvas.width = w * dpr; canvas.height = h * dpr;
    cols = Math.ceil(w / CW); rows = Math.ceil(h / CH);
    rects();
    draw();
  }
  function draw() {
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cols * CW, rows * CH);
    ctx.font = `12px ${font}`;
    ctx.textBaseline = 'top';
    for (let y = 0; y < rows; y++) {
      for (let x = 0; x < cols; x++) {
        if (avoid.some((r) => x > r.x0 && x < r.x1 && y > r.y0 && y < r.y1)) continue;
        const raw = 1 - x / cols;                       // denser on the left
        let d = (noise(x, y, t) + 1) / 2 * raw * 1.4;
        if (pointer) {
          const dx = x - pointer.x, dy = (y - pointer.y) * 2;
          d -= Math.max(0, 1 - Math.hypot(dx, dy) / 10) * 0.8;   // the lens clears the bloat
        }
        if (d < 0.32) continue;
        const level = Math.min(tint.length - 1, Math.floor((d - 0.32) * 7));
        ctx.fillStyle = tint[level];
        ctx.fillText(text[(y * 131 + x) % text.length], x * CW, y * CH + 2);
      }
    }
  }
  function frame(now) {
    if (visible && !reduce.matches) {
      if (now - last > 33) { t += 0.012; draw(); last = now; }
      requestAnimationFrame(frame);
    }
  }
  new IntersectionObserver(([e]) => {
    visible = e.isIntersecting;
    if (visible && !reduce.matches) requestAnimationFrame(frame);
  }).observe(hero);
  hero.addEventListener('pointermove', (e) => {
    const r = hero.getBoundingClientRect();
    pointer = { x: (e.clientX - r.left) / CW, y: (e.clientY - r.top) / CH };
    if (reduce.matches) draw();
  }, { passive: true });
  hero.addEventListener('pointerleave', () => { pointer = null; if (reduce.matches) draw(); });
  addEventListener('resize', resize);
  document.fonts && document.fonts.ready.then(resize);
  resize();
})();

(() => {
  // ---------------------------------------------------------- switcher
  const keys = document.querySelectorAll('[data-switch]');
  keys.forEach((key) => key.addEventListener('click', () => {
    keys.forEach((k) => {
      const on = k === key;
      k.setAttribute('aria-pressed', String(on));
      document.getElementById(k.dataset.switch).hidden = !on;
    });
  }));

  // -------------------------------------------------------------- copy
  document.querySelectorAll('.copy').forEach((btn) => {
    const label = btn.textContent;
    btn.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(btn.previousElementSibling.textContent);
        btn.textContent = btn.dataset.done;
      } catch {
        btn.textContent = btn.dataset.fail;
      }
      setTimeout(() => { btn.textContent = label; }, 1600);
    });
  });

  // ------------------------------------------- your system's file first
  const ua = navigator.userAgent;
  const os = /Windows/.test(ua) ? 'windows' : /Mac OS X/.test(ua) && !/Mobile/.test(ua) ? 'macos' : 'linux';
  document.querySelectorAll('.keys[data-dl]').forEach((row) => {
    const mine = row.querySelector(`[data-os="${os}"]`);
    if (!mine) return;
    row.querySelectorAll('.key').forEach((k) => k.classList.remove('key--primary'));
    mine.classList.add('key--primary');
    row.prepend(mine);
  });
})();
