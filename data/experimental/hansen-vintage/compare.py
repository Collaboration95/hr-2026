#!/usr/bin/env python3
"""Read-only core reuse, with explicit release coverage and period filtering."""
import copy
import datetime as dt
import hashlib
import json
from collections import Counter
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
import numpy as np
import rasterio
from engine.model import BAND_NAMES, Dataset
from engine.query import evaluate, select_cells
from engine.source import load_source, load_plots, sha256_file, object_hash

PERIOD = '2021-2023'

def write(name, x):
    (HERE/name).write_text(json.dumps(x, indent=2, allow_nan=False)+'\n')

def period_export(result, end_year):
    """Never serialize core default future false flags on historical data."""
    out = copy.deepcopy(result)
    out['periods'] = {PERIOD: out['periods'][PERIOD]}
    out['yearly_loss_counts'] = ({str(y): out['yearly_loss_counts'][str(y)] for y in range(2021,2024)}
                               if out['yearly_loss_counts'] is not None else None)
    if out['lossyear_histogram'] is not None:
        out['lossyear_histogram'] = out['lossyear_histogram'][:end_year-2000+1]
    out['observation_end_year'] = end_year
    assert set(out['periods']) == {PERIOD}
    assert out['yearly_loss_counts'] is None or set(out['yearly_loss_counts']) == {'2021','2022','2023'}
    if end_year == 2023:
        assert out['lossyear_histogram'] is None or len(out['lossyear_histogram']) == 24
    return out

def load_old():
    manifest=json.loads((HERE/'acquisition.json').read_text())
    assert manifest['status']=='complete' and manifest['all_three_historical_bands']
    bands, masks, sources=[],[],[]
    grid=None
    for name in BAND_NAMES:
        rec=next(x for x in manifest['layers'] if x['band']==name)
        p=HERE/rec['chip_path']
        assert sha256_file(p)==rec['chip_sha256']
        with rasterio.open(p) as src:
            g={'shape':[src.height,src.width], 'transform':list(src.transform)[:6], 'crs':str(src.crs)}
            assert grid is None or grid==g
            grid=g
            bands.append(src.read(1)); masks.append(src.read_masks(1)!=0)
        sources.append({'band':name,'path':str(p.relative_to(ROOT)),'sha256':rec['chip_sha256'], 'nodata':rec['nodata']})
    metadata={**grid,'product':'Hansen Global Forest Change 2023 v1.11', 'observation_end_year':2023,
              'company_historical_release':'UNKNOWN', 'license':'CC BY 4.0', 'sources':sources,
              'band_names':list(BAND_NAMES), 'source_url':manifest['official_archive_page']}
    ds=Dataset(np.stack(bands),np.stack(masks),metadata).validate()
    assert ds.bands[1].max()<=23
    return ds, manifest

def transitions(old,new,where):
    return [{'old_code':a,'current_code':b,'cells':n} for (a,b),n in sorted(Counter(zip(
        old[where].astype(int).tolist(),new[where].astype(int).tolist())).items())]

def main():
    start=dt.datetime.now(dt.timezone.utc).isoformat()
    bound_paths=[ROOT/'engine'/x for x in ('query.py','source.py','model.py','oracle.py')]
    bound_paths += list((ROOT/'data/public').glob('*.tif'))
    bound_paths += [ROOT/'data/public/provenance.json', ROOT/'artifacts/demo-v1.json',
        ROOT/'data/company-sample/2026-10-12/200001-17plots-valid.geojson',
        ROOT/'data/company-sample/2026-10-12/200001-17plots-valid_2025-08-02T09_11_12Z.csv']
    before={str(p.relative_to(ROOT)):sha256_file(p) for p in bound_paths}
    old,manifest=load_old(); current=load_source(ROOT); plots=load_plots(ROOT)
    canonical=json.loads((ROOT/'artifacts/demo-v1.json').read_text())
    byid={p['plot_id']:p for p in canonical['plots']}
    assert len(plots)==17 and len(byid)==17
    same_grid=all(old.metadata[k]==current.metadata[k] for k in ('shape','transform','crs'))
    assert same_grid, 'Grid differs: cannot use unresampled same-cell comparison'
    aoi={}
    for i,name in enumerate(BAND_NAMES):
        changed=old.bands[i]!=current.bands[i]
        aoi[name]={'raw_changed_cells':int(changed.sum()),'mask_changed_cells':int((old.masks[i]!=current.masks[i]).sum()),
                   'raw_transition_counts':transitions(old.bands[i],current.bands[i],changed),
                   'old_invalid_mask_cells':int((~old.masks[i]).sum()),'current_invalid_mask_cells':int((~current.masks[i]).sum())}
    ol=(old.bands[1]>=21)&(old.bands[1]<=23)&old.masks.all(axis=0)&(old.bands[2]==1)
    cl=(current.bands[1]>=21)&(current.bands[1]<=23)&current.masks.all(axis=0)&(current.bands[2]==1)
    aoi['shared_period']={'old_observed_2021_2023_cells':int(ol.sum()),'current_observed_2021_2023_cells':int(cl.sum()),
                          'event_membership_changed_cells':int((ol!=cl).sum()),
                          'shared_period_raw_year_changed_cells':int(((ol|cl)&(old.bands[1]!=current.bands[1])).sum())}
    results=[]; allcells=[]; union=set()
    for plot in plots:
        pid=plot['plot_id']; geometry=plot['geometry']
        oldr=period_export(evaluate(old,geometry),2023)
        fresh=evaluate(current,geometry)
        canonical_equal=fresh==byid[pid]['source_result']
        assert canonical_equal, f'Current source query differs from canonical: {pid}'
        assert geometry==byid[pid]['geometry'] and plot['supplier']==byid[pid]['supplier']
        newr=period_export(fresh,2025)
        rows,cols=select_cells(old.metadata,geometry)
        nr,nc=select_cells(current.metadata,geometry)
        assert np.array_equal(rows,nr) and np.array_equal(cols,nc)
        inside=(rows>=0)&(cols>=0)&(rows<old.bands.shape[1])&(cols<old.bands.shape[2])
        assert inside.all()
        ov,cv=old.bands[:,rows,cols],current.bands[:,rows,cols]
        om,cm=old.masks[:,rows,cols],current.masks[:,rows,cols]
        rawchanged=ov[1]!=cv[1]
        oldtarget=(ov[1]>=21)&(ov[1]<=23)&om.all(axis=0)&(ov[2]==1)
        newtarget=(cv[1]>=21)&(cv[1]<=23)&cm.all(axis=0)&(cv[2]==1)
        cells=[]
        a,b,c,d,e,f=old.metadata['transform']
        for j,(r,col) in enumerate(zip(rows.tolist(),cols.tolist())):
            union.add((r,col))
            item={'plot_id':pid,'row':r,'col':col,'center':[c+(col+.5)*a,f+(r+.5)*e],
                  'old_values':ov[:,j].tolist(),'current_values':cv[:,j].tolist(),
                  'old_masks':om[:,j].tolist(),'current_masks':cm[:,j].tolist(),
                  'old_2021_2023_observed_event':bool(oldtarget[j]),'current_2021_2023_observed_event':bool(newtarget[j]),
                  'raw_loss_changed':bool(rawchanged[j])}
            cells.append(item)
        allcells.extend(cells)
        results.append({'plot_id':pid,'geometry_sha256':object_hash(geometry),'selection_same':True,
            'old_result':oldr,'current_result':newr,'current_full_core_result_matches_canonical':canonical_equal,
            'current_core_result_sha256':object_hash(fresh),'canonical_source_result_sha256':object_hash(byid[pid]['source_result']),
            'raw_changed_cells_by_band':{name:int((ov[i]!=cv[i]).sum()) for i,name in enumerate(BAND_NAMES)},
            'mask_changed_cells_by_band':{name:int((om[i]!=cm[i]).sum()) for i,name in enumerate(BAND_NAMES)},
            'raw_loss_transitions':transitions(ov[1],cv[1],rawchanged),
            'shared_period_membership_changed_cells':int((oldtarget!=newtarget).sum()),
            'period_result_changed':oldr['periods'][PERIOD]!=newr['periods'][PERIOD],
            'period_flag_changed':oldr['periods'][PERIOD]['mapped_loss_present']!=newr['periods'][PERIOD]['mapped_loss_present'],
            'period_year_counts_changed':oldr['yearly_loss_counts']!=newr['yearly_loss_counts'],
            'changed_loss_witnesses':[x for x in cells if x['raw_loss_changed']][:10],
            'unchanged_witness':next((x for x in cells if not x['raw_loss_changed']),None)})
    after={str(p.relative_to(ROOT)):sha256_file(p) for p in bound_paths}
    assert before==after, 'Bound source, core or canonical files changed during study'
    result={'schema_version':'plotline.hansen-vintage-study.v1','started_at_utc':start,
        'completed_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
        'preregistration_sha256':sha256_file(HERE/'preregistration.json'),
        'acquisition_manifest_sha256':sha256_file(HERE/'acquisition.json'),
        'hypothesis_scope':'Hypothetical fixed-release comparison; company historical release UNKNOWN; no fitting to declarations',
        'comparison_period':PERIOD,'query_version':canonical['query_version'],
        'historical_dataset':old.metadata,'current_dataset':current.metadata,
        'historical_future_observations':'Unavailable after 2023. Core default future fields removed before export.',
        'historical_histogram_note':'24 bins encode raw codes 0..23. Zero means no mapped loss within that release coverage, not observed absence after 2023.',
        'matched_grid':same_grid,'aoi_pixels':int(old.bands.shape[1]*old.bands.shape[2]),'aoi_differences':aoi,
        'unchanged_bound_inputs_and_core':before==after,'input_and_code_sha256':before,
        'summary':{'plots':len(results),'selected_cell_sum':sum(p['old_result']['selected_cell_count'] for p in results),
            'distinct_selected_cells':len(union),'plots_with_raw_loss_changes':[p['plot_id'] for p in results if p['raw_changed_cells_by_band']['lossyear']],
            'plots_with_period_result_changes':[p['plot_id'] for p in results if p['period_result_changed']],
            'plots_with_period_flag_changes':[p['plot_id'] for p in results if p['period_flag_changed']],
            'plots_with_2021_2023_year_count_changes':[p['plot_id'] for p in results if p['period_year_counts_changed']],
            'current_canonical_matches':sum(p['current_full_core_result_matches_canonical'] for p in results)},
        'plots':results}
    write('comparison.json',result)
    write('selected-cells.json',{'band_order':list(BAND_NAMES),'historical_observation_end_year':2023,
        'company_historical_release':'UNKNOWN','cells':allcells})
    with (HERE/'chronology.jsonl').open('a') as f:
        f.write(json.dumps({'utc':result['completed_at_utc'],'event':'comparison_complete','summary':result['summary']})+'\n')
    print(json.dumps({'summary':result['summary'],'aoi_differences':aoi},indent=2))

if __name__=='__main__': main()
