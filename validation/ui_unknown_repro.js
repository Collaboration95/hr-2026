/* Paste/run in a validator-owned browser tab only, then use Commands → Reload
 * local evidence → Inspect native cells as a table → Show on map.
 * Explicit synthetic input; no source/canonical/frontend asset files are changed.
 * Reloading the page restores the real artifact and original fetch implementation.
 * Expected: unavailable raw values render Unknown/Unavailable, never absence.
 */
(async () => {
  const fetchOriginal = window.fetch.bind(window);
  const demo = await fetchOriginal('/data/demo-v1.json').then(r => r.json());
  const fixture = structuredClone(demo);
  const p = fixture.plots.find(p => p.plot_id === 'P-0003');
  p.source_result = {...p.source_result,
    selected_cell_count:1,in_coverage_cell_count:0,out_of_coverage_cell_count:1,
    valid_land_cell_count:0,unknown_cell_count:1,datamask_counts:{'0':0,'1':0,'2':0},
    canopy_histogram:null,lossyear_histogram:null,yearly_loss_counts:null,
    periods:{'2021-2023':{mapped_loss_present:null,observed_loss_cell_count:null},
      '2024-2025':{mapped_loss_present:null,observed_loss_cell_count:null}},
    support:'none',unknown_reasons:['out_of_coverage','no_valid_land']};
  p.compact_result = structuredClone(p.source_result);
  p.comparison.equal = true;
  const cell = structuredClone(p.evidence.features[0]);
  cell.properties = {...cell.properties,row:-1,col:-1,in_coverage:false,
    treecover2000:null,lossyear:null,datamask:null,band_validity:[false,false,false],valid_land:false};
  p.evidence.features = [cell];
  window.fetch = (...args) => String(args[0]).includes('/data/demo-v1.json')
    ? Promise.resolve(new Response(JSON.stringify(fixture), {status:200,headers:{'Content-Type':'application/json'}}))
    : fetchOriginal(...args);
  document.querySelector('[aria-label="Open commands"]').click();
  return {fixture:'SYNTHETIC validator-only null cell; no real observation claim',
    next:'Click Reload local evidence, open native-cell table, click Show on map'};
})();
