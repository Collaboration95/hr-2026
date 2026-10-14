import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { inflateSync } from 'node:zlib';
import { createHash } from 'node:crypto';
import { harness, demo, plots, years, declared, mapped, fmt, repoRoot, noOverflow, selectedCells, matrix } from './frozen-qa.mjs';

// Independent decoder for render-region.py's RGBA8, non-interlaced/filter-0 PNG.
// It never calls the app's decoder or derives expected counts from browser data.
function decodePng(bytes) {
  assert.deepEqual(bytes.subarray(0,8),Buffer.from([137,80,78,71,13,10,26,10]));
  let ihdr, ended=false; const idat=[];
  for(let offset=8;offset<bytes.length;) {
    assert.ok(offset+12<=bytes.length,'truncated PNG chunk');
    const size=bytes.readUInt32BE(offset),type=bytes.toString('ascii',offset+4,offset+8);
    assert.ok(offset+12+size<=bytes.length,'truncated PNG payload');
    const chunk=bytes.subarray(offset+8,offset+8+size);
    if(type==='IHDR') { assert.equal(ihdr,undefined); ihdr=chunk; }
    if(type==='IDAT') idat.push(chunk);
    offset+=size+12;
    if(type==='IEND') {assert.equal(offset,bytes.length);ended=true;break;}
  }
  assert.ok(ended && ihdr && idat.length); assert.equal(ihdr.length,13);
  const width=ihdr.readUInt32BE(0),height=ihdr.readUInt32BE(4);
  assert.deepEqual([...ihdr.subarray(8)],[8,6,0,0,0],'expected RGBA8, standard compression/filter, no interlace');
  const stride=width*4,raw=inflateSync(Buffer.concat(idat)); assert.equal(raw.length,(stride+1)*height);
  const rgba=Buffer.alloc(stride*height);
  for(let row=0;row<height;row++) {
    const start=row*(stride+1); assert.equal(raw[start],0,`filter must be 0 at row ${row}`);
    raw.copy(rgba,row*stride,start+1,start+1+stride);
  }
  return {width,height,rgba};
}
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
const pngBytes=await readFile(resolve(repoRoot,'app/public/region/hansen-bands.png'));
const png=decodePng(pngBytes);
const bands=Array.from({length:3},()=>Buffer.alloc(png.width*png.height));
const counts=Array(25).fill(0);
for(let i=0;i<png.width*png.height;i++) {
  const [loss,mask,canopy,alpha]=png.rgba.subarray(i*4,i*4+4);
  assert.ok(loss<=25 && mask<=2 && canopy<=100);assert.equal(alpha,255);
  bands[0][i]=loss;bands[1][i]=mask;bands[2][i]=canopy;
  if(mask===1 && loss>=1) counts[loss-1]++;
}
const {page,check,go,errors,shot,finish}=await harness('redesign');
const nav=name=>page.locator('nav[aria-label="Workspace view"]').getByRole('button',{name,exact:true});
try {
  await check('deep links render view/plot/year, optional years and invalid fallback',async()=>{
    for(const [route,view,id,year] of [
      ['#/map','Map',null,null],['#/map/P-0005/2025','Map','P-0005',2025],
      ['#/map/P-0003/2023','Map','P-0003',2023],['#/map/P-0005','Map','P-0005',2025],
      ['#/cohort','Cohort',null,null],['#/proof/P-0005/2025','Proof','P-0005',2025],
      ['#/proof/P-0001/2022','Proof','P-0001',2022],['#/live','Live query',null,null],
    ]) {
      await go(route); assert.equal(await nav(view).getAttribute('aria-current'),'page');
      if(view==='Map') {
        assert.equal(await page.locator('#plot-review-heading').count(),id?1:0);
        if(id) {assert.equal(await page.locator('#plot-review-heading').innerText(),id);assert.equal(await page.locator('.pl-scrub__cols [aria-pressed=true]').getAttribute('data-year'),String(year));}
        else assert.equal(await page.locator('.pl-scrub').getAttribute('data-mode'),'region');
      } else if(view==='Proof') {
        assert.equal(await page.getByRole('combobox',{name:'Proof plot',exact:true}).inputValue(),id);
        assert.equal(await page.getByRole('combobox',{name:'Proof year',exact:true}).inputValue(),String(year));
        assert.deepEqual(await page.locator('#proof-selected-year td').allTextContents(),[String(demo.plots.find(p=>p.plot_id===id).source_result.yearly_loss_counts[year]),String(demo.plots.find(p=>p.plot_id===id).compact_result.yearly_loss_counts[year]),'same']);
      } else await page.locator(view==='Cohort'?'#cohort-heading':'#live-heading').waitFor();
    }
    for(const route of ['#/unknown','#/map/P-9999/2025','#/map/P-0005/1999']) {
      await go(route); await page.waitForURL('**/#/map'); assert.equal(await page.locator('#plot-review-heading').count(),0);
    }
    return {deepLinks:8,invalidRoutes:3};
  });
  await check('history preserves plot/year across map, proof and cohort',async()=>{
    await go('#/map/P-0001/2022');
    await page.locator('.pl-review__actions').getByRole('button',{name:'Proof',exact:true}).click();
    await page.waitForURL('**/#/proof/P-0001/2022'); await nav('Cohort').click(); await page.waitForURL('**/#/cohort');
    await page.goBack(); await page.locator('#proof-heading').waitFor(); assert.equal(new URL(page.url()).hash,'#/proof/P-0001/2022');
    await page.goBack(); await page.locator('#plot-review-heading').waitFor(); assert.equal(new URL(page.url()).hash,'#/map/P-0001/2022');
    await selectedCells(page,plots.find(p=>p.plot_id==='P-0001'),2022);
    await page.goForward(); await page.locator('#proof-heading').waitFor(); assert.equal(new URL(page.url()).hash,'#/proof/P-0001/2022');
    await page.goForward(); await page.locator('#cohort-heading').waitFor(); assert.equal(new URL(page.url()).hash,'#/cohort');
  });
  await check('browser and actual map hook decode every PNG byte without colour conversion',async()=>{
    await go('#/map'); await page.locator('.pl-map[data-raster=ready]').waitFor();
    const manifest=await page.evaluate(async()=> (await fetch('/region/manifest.json')).json());
    assert.equal(hash(pngBytes),manifest.hansen.png_sha256);
    assert.deepEqual([png.height,png.width],manifest.hansen.shape_rows_columns);
    const browserDecode=await page.evaluate(async()=>{
      const hex=async bytes=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(b=>b.toString(16).padStart(2,'0')).join('');
      const bytes=await (await fetch('/region/hansen-bands.png')).arrayBuffer();
      const bitmap=await createImageBitmap(new Blob([bytes]),{colorSpaceConversion:'none',premultiplyAlpha:'none'});
      const canvas=document.createElement('canvas');canvas.width=bitmap.width;canvas.height=bitmap.height;
      const ctx=canvas.getContext('2d',{willReadFrequently:true,colorSpace:'srgb'});ctx.globalCompositeOperation='copy';ctx.imageSmoothingEnabled=false;ctx.drawImage(bitmap,0,0);
      const rgba=ctx.getImageData(0,0,canvas.width,canvas.height,{colorSpace:'srgb'}).data;bitmap.close();
      return {width:canvas.width,height:canvas.height,rgba:await hex(rgba),png:await hex(bytes)};
    });
    assert.deepEqual(browserDecode,{width:png.width,height:png.height,rgba:hash(png.rgba),png:hash(pngBytes)});
    // Observe the same shared hook used by MapStage, then unmount the temporary
    // read-only probe. This also catches regressions in the app's band extraction.
    const actualBands=await page.evaluate(async()=>{
      const React=(await import('/node_modules/.vite/deps/react.js')).default;
      const {createRoot}=(await import('/node_modules/.vite/deps/react-dom_client.js')).default;
      const {useRegionRaster}=await import('/src/map/region-raster.ts');
      const host=document.createElement('div');document.body.append(host);const root=createRoot(host);
      let timeout;
      try {
        return await new Promise((resolve,reject)=>{
          timeout=setTimeout(()=>reject(Error('map hook not ready')),5000);
          function Probe() {
            const raster=useRegionRaster();
            React.useEffect(()=>{
              if(raster.status==='unavailable')reject(Error(raster.error));
              if(raster.status!=='ready')return;
              const h=raster.data.hansen;
              Promise.all([h.lossyear,h.datamask,h.treecover].map(async b=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',b))].map(x=>x.toString(16).padStart(2,'0')).join(''))).then(digests=>resolve({digests,counts:raster.yearlyLossPixels,rows:h.rows,cols:h.cols,integrity:raster.data.integrity.hansen}));
            },[raster]);return null;
          }
          root.render(React.createElement(Probe));
        });
      } finally {clearTimeout(timeout);root.unmount();host.remove();}
    });
    assert.deepEqual(actualBands,{digests:bands.map(hash),counts,rows:png.height,cols:png.width,integrity:'sha256'});
    return {pixels:png.width*png.height,rgbaSha256:browserDecode.rgba,bandSha256:actualBands.digests};
  });
  await check('region scrubber equals all 25 independent land-loss PNG totals',async()=>{
    await go('#/map');await page.locator('.pl-map[data-raster=ready]').waitFor();
    assert.equal(await page.locator('.pl-scrub').getAttribute('data-mode'),'region');
    assert.deepEqual(await page.locator('.pl-scrub__col').evaluateAll(es=>es.map(e=>e.getAttribute('aria-label'))),years.map((y,i)=>`Year ${y}, ${fmt(counts[i])} loss pixels in region display raster`));
    assert.match(await page.locator('.pl-scrub__label').innerText(),/display raster/);return counts;
  });
  await check('plot scrubber and event footprints equal JSON for all17 plots',async()=>{
    for(const plot of plots) {
      const year=plot.plot_id==='P-0001'?2022:2025;
      await go(`#/map/${plot.plot_id}/${year}`);
      assert.deepEqual(await page.locator('.pl-scrub__col').evaluateAll(es=>es.map(e=>e.getAttribute('aria-label'))),years.map(y=>`Year ${y}, ${fmt(plot.source_result.yearly_loss_counts[y])} observed loss cells`));
      await selectedCells(page,plot,year);
      if(plot.plot_id==='P-0001') {assert.equal(await page.locator('.native-cell').count(),121);assert.equal(await page.locator('.native-cell[data-event=true]').count(),38);}
      if(plot.plot_id==='P-0005') {assert.equal(await page.locator('.native-cell').count(),262);assert.equal(await page.locator('.native-cell[data-event=true]').count(),11);}
    }
    return {plots:plots.length,annualCounts:plots.length*years.length};
  });
  await check('region and cohort matrices place every declared/mapped plot exactly',async()=>{
    await go('#/map');const region=await matrix(page,'.pl-matrix');
    const values=await page.locator('.pl-brief__stats .pl-stat__value').allTextContents();
    assert.deepEqual(values,[`${demo.summary.exact_match_count}/${demo.summary.plot_count}`,String(plots.filter(declared).length),String(plots.filter(p=>mapped(p)===true).length)]);
    await go('#/cohort');const cohort=await matrix(page,'.co-matrix');assert.deepEqual(region,cohort);return region;
  });
  await check('rail filter counts and contents match JSON and leave map/cohort scope intact',async()=>{
    await go('#/map');
    const tests=[['All',()=>true],['Declared indication',declared],['Mapped loss 2021–23',p=>mapped(p)===true],['Declared ≠ mapped',p=>mapped(p)!==null && declared(p)!==mapped(p)]];
    for(const [label,predicate] of tests) {
      const expected=plots.filter(predicate).map(p=>p.plot_id);
      const button=page.getByRole('group',{name:'Filter plots',exact:true}).getByRole('button',{name:`${label} ${expected.length}`,exact:true});
      await button.click();assert.equal(await button.getAttribute('aria-pressed'),'true');
      assert.deepEqual(await page.locator('button.plot-row').evaluateAll(es=>es.map(e=>e.dataset.plotId)),expected);
      assert.equal(await page.getByRole('button',{name:/Select P-\d+ on map/}).count(),plots.length);
    }
    await page.getByRole('textbox',{name:'Search plots',exact:true}).fill('P-0005');
    assert.deepEqual(await page.locator('button.plot-row').evaluateAll(es=>es.map(e=>e.dataset.plotId)),['P-0005']);
    await nav('Cohort').click();assert.equal(await page.locator('.co-barcode tbody tr').count(),plots.length);await matrix(page,'.co-matrix');
    return tests.map(([label,test])=>({label,count:plots.filter(test).length}));
  });
  await check('J/K, editable-field isolation and scrubber arrow/Home/End keyboard access',async()=>{
    await go('#/map');await page.locator('.pl-map[data-raster=ready]').waitFor();
    await page.getByRole('textbox',{name:'Search plots',exact:true}).fill('');
    await page.getByRole('group',{name:'Filter plots',exact:true}).getByRole('button',{name:`All ${plots.length}`,exact:true}).click();
    await page.locator('#main-content').focus();await page.keyboard.press('j');
    await page.waitForFunction(() => document.querySelector('#plot-review-heading')?.textContent === 'P-0001');
    await page.keyboard.press('j');await page.waitForFunction(() => document.querySelector('#plot-review-heading')?.textContent === 'P-0003');
    await page.keyboard.press('k');await page.waitForFunction(() => document.querySelector('#plot-review-heading')?.textContent === 'P-0001');
    await page.keyboard.press('/');const search=page.getByRole('textbox',{name:'Search plots',exact:true});
    assert.equal(await search.evaluate(e=>document.activeElement===e),true);
    await page.keyboard.press('j');assert.equal(await search.inputValue(),'j');assert.equal(await page.locator('#plot-review-heading').innerText(),'P-0001');
    await search.fill('');await page.locator('#plot-review-heading').focus();
    await page.locator('.pl-scrub__col[data-year="2025"]').focus();
    for(const [key,year] of [['ArrowLeft',2024],['Home',2001],['End',2025]]) {
      await page.keyboard.press(key);await page.waitForFunction(y=>document.querySelector('.pl-scrub__cols [aria-pressed=true]')?.dataset.year===String(y),year);
      const state=await page.evaluate(()=>({year:document.activeElement.dataset.year,visible:document.activeElement.matches(':focus-visible'),outline:getComputedStyle(document.activeElement).outlineStyle}));
      assert.equal(state.year,String(year));assert.equal(state.visible,true);assert.equal(state.outline,'solid');
    }
  });
  await check('JRC forest toggle and legend preserve valid transparent class0',async()=>{
    await go('#/map');await page.locator('.pl-map[data-raster=ready]').waitFor();
    const toggle=page.getByRole('button',{name:'JRC 2020 forest',exact:true});assert.equal(await toggle.getAttribute('aria-pressed'),'false');
    await toggle.click();assert.equal(await toggle.getAttribute('aria-pressed'),'true');
    const legend=page.getByRole('button',{name:'Legend',exact:true});if(await legend.getAttribute('aria-expanded')!=='true')await legend.click();
    const text=await page.locator('.pl-map__legend').innerText();assert.match(text,/class 0 non-forest shown transparent/);assert.match(text,/Class 0 is valid Non-forest, not missing data/);
    await toggle.click();assert.equal(await toggle.getAttribute('aria-pressed'),'false');
  });
  await check('Escape returns plot map to region and clears selected inspector',async()=>{
    await go('#/map/P-0005/2025');await page.locator('#plot-review-heading').focus();await page.keyboard.press('Escape');
    await page.waitForURL('**/#/map');await page.locator('.pl-scrub[data-mode=region]').waitFor();assert.equal(await page.locator('#plot-review-heading').count(),0);
    assert.equal(await page.locator('.native-cell').count(),0);assert.equal(await page.locator('.pl-scrub').getAttribute('data-mode'),'region');
    assert.equal(await page.getByRole('button',{name:/Select P-\d+ on map/}).count(),plots.length);
  });
  for(const route of ['#/map','#/map/P-0001/2022','#/map/P-0005/2025','#/cohort','#/proof/P-0005/2025','#/live']) await check(`390px no document overflow ${route}`,async()=>{
    await page.setViewportSize({width:390,height:844});await go(route);
    if(route.startsWith('#/map'))await page.locator('.pl-map[data-raster=ready]').waitFor();
    await shot(`mobile-${route.slice(2).replaceAll('/','-')}`);return noOverflow(page);
  });
  await check('redesign journeys have no page errors',async()=>assert.deepEqual(errors,[]));
} finally {await finish();}
