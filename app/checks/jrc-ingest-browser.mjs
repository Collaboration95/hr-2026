import { createServer } from 'vite';
import { createServer as createHttpServer } from 'node:http';
import assert from 'node:assert/strict';
import { panelFixture, cases } from './jrc-ingest-fixtures.mjs';

// Isolated loopback fixture server. Does not mount App, serve candidate JSON,
// copy assets, change Vite config, or contact a source/service.
const names = [...Object.keys(cases), 'mismatch', 'forgedEquality', 'pagination'];
const server = await createServer({ configFile: false, root: new URL('../', import.meta.url).pathname,
  cacheDir: 'node_modules/.vite-jrc-check',
  server: { middlewareMode: true, hmr: false },
});
const http = createHttpServer(async (req, res) => {
  if (!req.url?.startsWith('/__jrc_fixture__')) return server.middlewares(req, res);
  const url = new URL(req.url, 'http://127.0.0.1:5187'), requested = url.searchParams.get('case') ?? 'valid0';
  const name = names.includes(requested) ? requested : 'valid0';
  const data = panelFixture(name);
  const html = `<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Synthetic JRC panel QA</title><style>body{margin:0;padding:16px;background:#f4f6ec;font:14px system-ui}main{max-width:1100px;margin:auto}nav{display:flex;flex-wrap:wrap;gap:12px}a{color:#173d32;font-size:14px}</style></head><body><main><h1>Synthetic display QA · ${name}</h1><p>Artificial controls only. No accepted JRC observation or real supplier geometry is loaded here.</p><nav aria-label="Fixture cases">${names.map(n => `<a href="?case=${n}">${n}</a>`).join('')}</nav><div id="fixture"></div></main><script type="module">
import React from 'react';
import {createRoot} from 'react-dom/client';
import JrcBaseline from '/src/JrcBaseline.tsx';
createRoot(document.getElementById('fixture')).render(React.createElement(JrcBaseline, {data:${JSON.stringify(data)},plotId:'SYNTHETIC-JRC'}));
</script></body></html>`;
  try {
    res.statusCode = 200; res.setHeader('Content-Type', 'text/html; charset=utf-8');
    res.end(await server.transformIndexHtml(req.url, html));
  } catch (error) { console.error(error); res.statusCode = 500; res.end('Synthetic fixture unavailable'); }
});
await new Promise((resolve, reject) => { http.once('error', reject); http.listen(5187, '127.0.0.1', resolve); });
console.log('Synthetic JRC panel QA only: http://127.0.0.1:5187/__jrc_fixture__?case=valid0');
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, async () => { http.close(); await server.close(); process.exit(0); });

// Invoke only after T3 has explicitly failed or is unavailable. No installation.
if (process.argv.includes('--verify')) {
  process.env.PLAYWRIGHT_BROWSERS_PATH ??= new URL('../.cache/playwright', import.meta.url).pathname;
  let browser;
  try {
    const { chromium } = await import('playwright');
    browser = await chromium.launch({ headless: true });
    const page = await browser.newPage({ viewport: { width: 375, height: 812 }, reducedMotion: 'reduce' });
    const failures = [];
    page.on('pageerror', error => failures.push(error.message));
    for (const name of names) {
      await page.goto(`http://127.0.0.1:5187/__jrc_fixture__?case=${name}`);
      await page.locator('.jrc-baseline').waitFor();
      const expected = name === 'mismatch' || name === 'forgedEquality' || name === 'pagination' ? false : cases[name].flag;
      assert.equal(await page.locator('.jrc-signal').getAttribute('data-signal'), expected === null ? 'unknown' : String(expected));
      const layout = await page.evaluate(() => ({
        width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
        minEvidenceFont: Math.min(...[...document.querySelectorAll('.jrc-baseline :is(td,th,caption,summary,button,dt,dd,p)')].map(e => parseFloat(getComputedStyle(e).fontSize))),
        regionOverflow: document.querySelector('.jrc-table-scroll').scrollWidth > document.querySelector('.jrc-table-scroll').clientWidth,
        tableWidth: document.querySelector('.jrc-baseline table').getBoundingClientRect().width,
        rawColumnWidth: document.querySelector('.jrc-baseline th:nth-child(2)').getBoundingClientRect().width,
        transition: getComputedStyle(document.querySelector('.jrc-baseline button') ?? document.querySelector('.jrc-baseline')).transitionDuration,
      }));
      assert.ok(layout.scrollWidth <= layout.width, `${name}: page must contain table overflow`);
      assert.ok(layout.minEvidenceFont >= 12, `${name}: evidence must be 12px+`);
      assert.ok(layout.tableWidth >= 980 && layout.rawColumnWidth >= 130, `${name}: mobile columns must remain readable within the scroll region`);
      if (name !== 'noCenters' && name !== 'missingNoCenters') assert.equal(layout.regionOverflow, true);
      assert.equal(layout.transition, '0s');
      if (name === 'valid0') {
        assert.equal(await page.locator('.jrc-cell-state').innerText(), 'Mapped non-forest');
        assert.deepEqual(await page.locator('.jrc-counts dd').allTextContents(), ['1', '0', '1', '1', '0']);
      }
      if (name === 'invalidMask') {
        assert.deepEqual(await page.locator('.jrc-cell-state').allTextContents(), ['Unknown — invalid mask', 'Unknown — invalid mask']);
        assert.equal(await page.locator('tbody tr').count(), 2);
      }
      if (name === 'missingBand') assert.equal(await page.locator('.jrc-cell-state').innerText(), 'Unknown — band unavailable');
      if (name === 'mismatch' || name === 'forgedEquality') {
        assert.ok((await page.locator('.jrc-proof-warning').first().innerText()).includes('unconfirmed'));
        assert.equal(await page.locator('.jrc-proof-message:not(.jrc-proof-warning)').count(), 0);
      }
    }
    // Actual keyboard activation, not pointer click, opens cell/proof disclosure
    // and moves across all pages. Programmatic focus selects the test starting point.
    await page.goto('http://127.0.0.1:5187/__jrc_fixture__?case=pagination');
    const region = page.getByRole('region', { name: 'Native JRC cells' });
    await region.focus();
    assert.equal(await page.evaluate(() => document.activeElement.className), 'jrc-table-scroll');
    await page.keyboard.press('ArrowRight');
    await page.waitForFunction(() => document.querySelector('.jrc-table-scroll').scrollLeft > 0, null, { timeout: 1500 });
    assert.ok(await region.evaluate(e => e.scrollLeft > 0));
    const corners = page.locator('tbody summary').first();
    await corners.focus(); await page.keyboard.press('Enter');
    assert.equal(await corners.evaluate(e => e.parentElement.open), true);
    const next = page.getByRole('button', { name: 'Next cells' });
    await next.focus(); await page.keyboard.press('Enter');
    assert.equal(await page.locator('.jrc-pagination [role=status]').innerText(), 'Page 2 of 2');
    assert.equal(await page.locator('tbody tr').count(), 6);
    assert.equal(await next.isDisabled(), true);
    const previous = page.getByRole('button', { name: 'Previous cells' });
    await previous.focus(); await page.keyboard.press('Enter');
    assert.equal(await page.locator('.jrc-pagination [role=status]').innerText(), 'Page 1 of 2');
    const proof = page.locator('.jrc-proof > summary');
    await proof.focus(); await page.keyboard.press('Enter');
    assert.equal(await proof.evaluate(e => e.parentElement.open), true);
    const benchmarkDisclosure = page.getByText('JRC-only store and benchmark disclosure', { exact: true });
    await benchmarkDisclosure.focus(); await page.keyboard.press('Enter');
    assert.ok((await page.locator('.jrc-proof').innerText()).includes('Benchmark: Unavailable'));
    await proof.focus();
    await page.keyboard.press('Tab');
    assert.equal(await page.evaluate(() => document.activeElement.tagName), 'SUMMARY');
    assert.deepEqual(failures, []);
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto('http://127.0.0.1:5187/__jrc_fixture__?case=valid0');
    await page.locator('.jrc-baseline').waitFor();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    console.log(JSON.stringify({ pass: true, cases: names.length, mobile: '375×812', desktop: '1280×800', keyboard: 'region scroll, corners, paging, proof, Tab', reducedMotion: true, pageErrors: failures }));
    if (process.argv.includes('--screenshot')) {
      await page.setViewportSize({ width: 375, height: 812 });
      await page.goto('http://127.0.0.1:5187/__jrc_fixture__?case=valid0');
      await page.locator('.jrc-baseline').waitFor();
      console.log('SCREENSHOT:' + (await page.screenshot({ fullPage: true })).toString('base64'));
    }
  } finally {
    await browser?.close(); http.closeAllConnections(); http.close(); await server.close();
  }
  process.exit(0);
}
