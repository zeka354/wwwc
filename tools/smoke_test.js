// Smoke test: loads the game in headless Chromium, plays a few seconds and fails on any JS error.
//   npm i -D playwright && npx playwright install chromium   (once)
//   node tools/smoke_test.js
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const path = require('path');

(async () => {
  const srv = spawn('python3', ['-m', 'http.server', '8765'], { cwd: path.join(__dirname, '..', 'game'), stdio: 'ignore' });
  await new Promise(r => setTimeout(r, 800));
  const b = await chromium.launch();
  const errs = [];
  try {
    const pg = await b.newPage({ viewport: { width: 1280, height: 720 } });
    pg.on('pageerror', e => errs.push(String(e)));
    pg.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
    await pg.goto('http://localhost:8765/index.html');
    await pg.waitForFunction(() => !document.getElementById('bStart').disabled, null, { timeout: 15000 });
    await pg.click('#bStart');
    await pg.evaluate(() => { G.waves.forEach(w => w.done = true); spawn('shadow', G.p.x + 120); });
    await pg.waitForTimeout(800);
    for (const k of ['KeyJ', 'KeyJ', 'KeyJ']) { await pg.keyboard.press(k); await pg.waitForTimeout(120); }
    await pg.waitForTimeout(700);
    await pg.keyboard.press('KeyK'); await pg.waitForTimeout(1200);
    await pg.keyboard.press('KeyL'); await pg.waitForTimeout(600);
    await pg.keyboard.press('Space'); await pg.waitForTimeout(250); await pg.keyboard.press('Space'); await pg.waitForTimeout(1200);
    await pg.evaluate(() => { G.p.idleT = 29.9; }); await pg.waitForTimeout(400);
    const st = await pg.evaluate(() => ({ state: G.p.state, score: G.score, hp: G.p.hp }));
    await pg.screenshot({ path: path.join(__dirname, 'smoke.png') });
    console.log('state after test:', st);
    if (st.state !== 'afk') errs.push('AFK did not start');
    if (st.score <= 0) errs.push('combo/ritual did not kill the test shadow');
  } finally { await b.close(); srv.kill(); }
  if (errs.length) { console.error('FAIL\n' + errs.join('\n')); process.exit(1); }
  console.log('OK');
})();
