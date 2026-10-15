/* Validator-owned tab only. Run, then Commands → Reload local evidence → Show
 * proof. Source 2023=0 versus compact 2023=1 must reject or display mismatch.
 * Reloading the page restores real data. No canonical/app asset is changed.
 */
(async () => {
  const originalFetch = window.fetch.bind(window);
  const fixture = await originalFetch('/data/demo-v1.json').then(r => r.json());
  const p = fixture.plots.find(p => p.plot_id === 'P-0003');
  p.compact_result.yearly_loss_counts['2023'] = 1;
  p.compact_result.lossyear_histogram[0] -= 1;
  p.compact_result.lossyear_histogram[23] += 1;
  p.compact_result.periods['2021-2023'] = {mapped_loss_present:true,observed_loss_cell_count:1};
  // Keep the deliberately false equality flag/hash; runtime should check it.
  window.fetch = (...args) => String(args[0]).includes('/data/demo-v1.json')
    ? Promise.resolve(new Response(JSON.stringify(fixture), {status:200,headers:{'Content-Type':'application/json'}}))
    : originalFetch(...args);
  document.querySelector('[aria-label="Open commands"]').click();
  return {fixture:'INVALID validator-only comparison, no real observation claim',
    source2023:0,compact2023:1,falseAdvertisedEquality:p.comparison.equal};
})();
