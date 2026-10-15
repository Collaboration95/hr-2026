#!/usr/bin/env python3
"""Independent scalar query checks and direct original-tile witness reads."""
import datetime as dt
import hashlib
import json
from contextlib import ExitStack
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT))
import numpy as np
import rasterio
from rasterio.windows import Window
from engine.model import Dataset
from engine.oracle import oracle_evaluate, _covered, _polygons

NAMES=('treecover2000','lossyear','datamask')

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for x in iter(lambda:f.read(1024*1024),b''): h.update(x)
    return h.hexdigest()

def load(files, end):
    arrays=[]; masks=[]; grids=[]
    for p in files:
        with rasterio.open(p) as ds:
            arrays.append(ds.read(1)); masks.append(ds.read_masks(1)!=0)
            grids.append({'shape':[ds.height,ds.width],'transform':list(ds.transform)[:6],'crs':str(ds.crs)})
    assert grids.count(grids[0])==3
    d=Dataset(np.stack(arrays),np.stack(masks),{**grids[0],'observation_end_year':end}).validate()
    assert d.bands[1].max()<=end-2000
    return d

def project(oracle,end):
    # Explicit fresh construction, avoiding future fields in serialized output.
    r={k:v for k,v in oracle.items() if k not in ('periods','lossyear_histogram','yearly_loss_counts')}
    r['periods']={'2021-2023':oracle['periods']['2021-2023']}
    r['lossyear_histogram']=oracle['lossyear_histogram'][:end-1999] if oracle['lossyear_histogram'] is not None else None
    r['yearly_loss_counts']={str(y):oracle['yearly_loss_counts'][str(y)] for y in (2021,2022,2023)} if oracle['yearly_loss_counts'] is not None else None
    r['observation_end_year']=end
    return r

def main():
    results=json.loads((HERE/'comparison.json').read_text())
    acq=json.loads((HERE/'acquisition.json').read_text())
    cp=json.loads((ROOT/'data/public/provenance.json').read_text())
    old_layers={x['band']:x for x in acq['layers']}
    cur_layers={x['band']:x for x in cp['layers']}
    old=load([HERE/old_layers[n]['chip_path'] for n in NAMES],2023)
    cur=load([ROOT/'data/public'/f'hansen_{n}_sample.tif' for n in NAMES],2025)
    geo=json.loads((ROOT/'data/company-sample/2026-10-12/200001-17plots-valid.geojson').read_text())
    geometries={f['properties']['ProductionPlace']:f['geometry'] for f in geo['features']}
    checks=[]
    for plot in results['plots']:
        pid=plot['plot_id']; geometry=geometries[pid]
        old_answer=project(oracle_evaluate(old,geometry),2023)
        cur_answer=project(oracle_evaluate(cur,geometry),2025)
        assert old_answer==plot['old_result'],pid
        assert cur_answer==plot['current_result'],pid
        checks.append({'plot_id':pid,'historical_scalar_oracle_equal':True,'current_scalar_oracle_equal':True})
    cells=json.loads((HERE/'selected-cells.json').read_text())['cells']
    cases=[('first_selected_0_to_24',lambda x:x['old_values'][1]==0 and x['current_values'][1]==24),
           ('first_selected_0_to_25',lambda x:x['old_values'][1]==0 and x['current_values'][1]==25),
           ('first_unchanged_2021_2023_event',lambda x:x['old_2021_2023_observed_event'] and not x['raw_loss_changed']),
           ('first_unchanged_zero',lambda x:x['old_values'][1]==x['current_values'][1]==0)]
    witnesses=[]
    with ExitStack() as stack:
        readers={'old':{},'current':{}}
        for name in NAMES:
            op=HERE/old_layers[name]['source_path']
            npth=ROOT/'data/public/raw'/cur_layers[name]['url'].rsplit('/',1)[-1]
            assert digest(op)==old_layers[name]['source_sha256']
            assert digest(npth)==cur_layers[name]['source_tile_sha256']
            readers['old'][name]=stack.enter_context(rasterio.open(op))
            readers['current'][name]=stack.enter_context(rasterio.open(npth))
        for label,predicate in cases:
            cell=next(x for x in cells if predicate(x))
            row,col=cell['row'],cell['col']
            a,b,c,d,e,f=old.metadata['transform']
            scalar_center=(c+a*(col+.5),f+e*(row+.5))
            assert list(scalar_center)==cell['center']
            assert _covered(scalar_center,_polygons(geometries[cell['plot_id']]))
            witness={'case':label,**cell,'independent_scalar_membership':True,'original_tile_reads':{}}
            for vintage, records in (('old',old_layers),('current',cur_layers)):
                values=[]; masks=[]; positions=[]
                for band in NAMES:
                    window=(records[band]['grid']['window_col_row_width_height'] if vintage=='old' else records[band]['window'])
                    global_col,global_row=col+window[0],row+window[1]
                    ds=readers[vintage][band]
                    w=Window(global_col,global_row,1,1)
                    values.append(int(ds.read(1,window=w)[0,0]))
                    masks.append(bool(ds.read_masks(1,window=w)[0,0]))
                    positions.append([global_row,global_col])
                key='old' if vintage=='old' else 'current'
                assert values==cell[key+'_values'] and masks==cell[key+'_masks']
                assert positions.count(positions[0])==3
                witness['original_tile_reads'][vintage]={'source_row_col':positions[0],'values':values,'masks':masks,'matches_chip':True}
            witnesses.append(witness)
    # Detect accidental historical future fields in every exported result.
    for p in results['plots']:
        oldr=p['old_result']
        assert set(oldr['periods'])=={'2021-2023'}
        assert all(int(y)<=2023 for y in oldr['yearly_loss_counts'])
        assert len(oldr['lossyear_histogram'])==24
        assert oldr['observation_end_year']==2023
    report={'checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
        'comparison_sha256':digest(HERE/'comparison.json'),
        'selected_cells_sha256':digest(HERE/'selected-cells.json'),
        'method':'Existing independent scalar ray-casting/counter oracle for all 17 plots in each release; four deterministic witnesses reread directly from both original tile sets, including per-band validity masks. No engine.query imports.',
        'oracle_checks':checks,'all_34_scalar_queries_equal':True,
        'historical_future_observation_leak_check_passed':True,
        'original_tile_sha256_verified_all_six':True,
        'witnesses':witnesses}
    (HERE/'independent-check.json').write_text(json.dumps(report,indent=2)+'\n')
    with (HERE/'chronology.jsonl').open('a') as f:
        f.write(json.dumps({'utc':report['checked_at_utc'],'event':'independent_check_complete','all_34_scalar_queries_equal':True,'direct_original_tile_witnesses':len(witnesses)})+'\n')
    print(json.dumps({'all_34_scalar_queries_equal':True,'historical_future_observation_leak_check_passed':True,'witnesses':witnesses},indent=2))

if __name__=='__main__':main()
