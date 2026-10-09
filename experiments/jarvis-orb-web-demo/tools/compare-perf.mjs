/**
 * Headless Chromium comparison, for diagnostics ONLY. Never benchmark claims.
 * Measurements are UI RAF + Chrome TaskDuration/JSHeap and are not GPU FPS.
 * Same browser/device, sequential windows; Qt Windows remains unverified.
 */
import { chromium } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';
const target = 'perf-results';
await mkdir(target, { recursive: true });
const demo = process.env.ORB_BASE_URL || 'http://127.0.0.1:5173';
const original = process.env.ORB_LEGACY_URL;
if (!original) throw new Error('ORB_LEGACY_URL is required for comparison');

const browser = await chromium.launch({
  headless: true,
  args: [
    '--enable-webgl', '--use-gl=angle', '--use-angle=swiftshader',
    '--enable-unsafe-swiftshader', '--disable-dev-shm-usage'
  ]
});

async function sample(label, url, testMode = false) {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1
  });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', err => errors.push(String(err.message)));
  const cdp = await context.newCDPSession(page);
  try {
    await page.goto(url, { waitUntil: 'load', timeout: 60000 });
    if (testMode) {
      await page.getByTestId('state-speaking').click();
      // Simulated signal only; no microphone or generated speech.
      await page.evaluate(() => window.setAudioLevel(0.65));
    } else {
      await page.evaluate(() => window.setBrahmaState?.('SPEAKING'));
    }
    await page.waitForTimeout(700);
    await cdp.send('Performance.enable');
    const before = await cdp.send('Performance.getMetrics');
    const measured = await page.evaluate(async () => {
      const intervals = [];
      let previous = 0, finished = false;
      let handle = 0;
      const tick = now => {
        if (finished) return;
        if (previous) intervals.push(now - previous);
        previous = now;
        handle = requestAnimationFrame(tick);
      };
      handle = requestAnimationFrame(tick);
      await new Promise(resolve => setTimeout(resolve, 2300));
      finished = true;
      cancelAnimationFrame(handle);
      const sorted = [...intervals].sort((a, b) => a - b);
      const delta = intervals.reduce((sum, n) => sum + n, 0);
      const canvas = document.querySelector('canvas');
      return {
        frames: intervals.length,
        uiRafFps: delta > 0 ? Math.round(1000 * intervals.length / delta * 10) / 10 : null,
        uiP95Ms: sorted.length ? Math.round(sorted[Math.floor((sorted.length - 1) * 0.95)] * 10) / 10 : null,
        uiLongFramesOver33ms: intervals.filter(n => n > 33.4).length,
        canvas: canvas ? [canvas.width, canvas.height] : null,
        visible: document.visibilityState
      };
    });
    const after = await cdp.send('Performance.getMetrics');
    const get = (metrics, name) => metrics.metrics.find(v => v.name === name)?.value ?? null;
    const metricDelta = (name) => {
      const a = get(before, name), b = get(after, name);
      return a === null || b === null ? null : Number((b - a).toFixed(4));
    };
    return {
      label, ...measured,
      taskDurationSeconds: metricDelta('TaskDuration'),
      scriptDurationSeconds: metricDelta('ScriptDuration'),
      jsHeapUsedBytes: get(after, 'JSHeapUsedSize'),
      errors
    };
  } finally {
    await cdp.detach().catch(() => {});
    await context.close();
  }
}

try {
  const results = {
    host: 'Linux GitHub Actions / software Chromium SwiftShader',
    note: 'Indicative only: browser UI RAF, main-thread task time and heap; NOT true Three.js draw FPS, GPU load or Windows Qt WebEngine performance',
    sequence: [
      await sample('new-orb', demo, true),
      await sample('original-background', original)
    ]
  };
  await writeFile(target + '/compare.json', JSON.stringify(results, null, 2), 'utf8');
  console.log(JSON.stringify(results, null, 2));
  if (results.sequence.some(v => v.errors.length)) process.exitCode = 1;
} finally {
  await browser.close();
}
