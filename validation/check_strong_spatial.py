"""Independent TIFF/mask/accounting and exact-rational spatial witness audit.
Does not import either research implementation or the strong control decoder.
"""
from compression import zstd
from fractions import Fraction as F
import hashlib,json,math
from pathlib import Path
import sys
import numpy as np
import rasterio
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from validation.run_checks import digest,file_hash,result_for,selected_cells

def exact(a,b):return json.dumps(a,sort_keys=True)==json.dumps(b,sort_keys=True)

def clip(ring,bounds):
    points=[tuple(map(F,p)) for p in ring[:-1]]
    for axis,limit,greater in [(0,bounds[0],True),(0,bounds[2],False),(1,bounds[1],True),(1,bounds[3],False)]:
        out=[];limit=F(limit)
        if not points:break
        for a,b in zip(points[-1:]+points[:-1],points):
            ia=a[axis]>=limit if greater else a[axis]<=limit
            ib=b[axis]>=limit if greater else b[axis]<=limit
            if ia!=ib:
                t=(limit-a[axis])/(b[axis]-a[axis]);out.append(tuple(a[j]+t*(b[j]-a[j]) for j in (0,1)))
            if ib:out.append(b)
        points=out
    if len(points)<3:return F(0)
    return abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points,points[1:]+points[:1])))/2

def area(geom,bounds):
    polys=[geom['coordinates']] if geom['type']=='Polygon' else geom['coordinates']
    return sum(clip(p[0],bounds)-sum(clip(h,bounds) for h in p[1:]) for p in polys)

def bounds(md,r,c):
    a,_,x,_,e,y=md['transform'];return x+c*a,y+(r+1)*e,x+(c+1)*a,y+r*e

def overlap(md,geom):
    polys=[geom['coordinates']] if geom['type']=='Polygon' else geom['coordinates'];points=[p for poly in polys for ring in poly for p in ring]
    a,_,x,_,e,y=md['transform'];c0=math.floor((min(p[0] for p in points)-x)/a)-1;c1=math.ceil((max(p[0] for p in points)-x)/a)+1;r0=math.floor((max(p[1] for p in points)-y)/e)-1;r1=math.ceil((min(p[1] for p in points)-y)/e)+1
    assert (r1-r0+1)*(c1-c0+1)<100000
    return [(r,c) for r in range(r0,r1+1) for c in range(c0,c1+1) if area(geom,bounds(md,r,c))>0]

def real_known_reduction(bands,masks,cells):
    # Assert independently that this real cohort is fully covered valid land;
    # synthetic unknown tests belong to the previous general validator checks.
    n=len(cells);h,w=bands.shape[1:];canopy=[0]*101;loss=[0]*26
    for r,c in cells:
        assert 0<=r<h and 0<=c<w and masks[:,r,c].all() and bands[2,r,c]==1
        canopy[int(bands[0,r,c])]+=1;loss[int(bands[1,r,c])]+=1
    return {'selected_cell_count':n,'in_coverage_cell_count':n,'out_of_coverage_cell_count':0,'valid_land_cell_count':n,'unknown_cell_count':0,'datamask_counts':{'0':0,'1':n,'2':0},'canopy_histogram':canopy,'lossyear_histogram':loss,'yearly_loss_counts':{str(2000+i):loss[i] for i in range(1,26)},'periods':{k:{'mapped_loss_present':sum(loss[lo:hi+1])>0,'observed_loss_cell_count':sum(loss[lo:hi+1])} for k,lo,hi in [('2021-2023',21,23),('2024-2025',24,25)]},'support':'complete','unknown_reasons':[]}

def main():
    accepted=json.loads((ROOT/'artifacts/demo-v1.json').read_text());strong=json.loads((ROOT/'artifacts/strong-baseline-v1.json').read_text());spatial=json.loads((ROOT/'data/experimental/spatial-sensitivity/results.json').read_text());witness=json.loads((ROOT/'data/experimental/spatial-sensitivity/witnesses.json').read_text())
    watched=[ROOT/'artifacts/demo-v1.json',ROOT/'artifacts/benchmark-v1.json',ROOT/'artifacts/experiments/retained-choice.json',ROOT/'engine/query.py',ROOT/'artifacts/strong-baseline-v1.json',ROOT/'data/experimental/spatial-sensitivity/results.json']
    before={str(p.relative_to(ROOT)):file_hash(p) for p in watched};checks=[]
    def check(ok,label,detail=None):checks.append({'pass':bool(ok),'label':label,'detail':detail})
    arrays=[];maskarrays=[]
    for source in accepted['dataset']['sources']:
        p=ROOT/source['path'];check(file_hash(p)==source['sha256'],'pinned source '+source['band'])
        with rasterio.open(p) as src:arrays.append(src.read(1));maskarrays.append(src.read_masks(1)!=0)
    bands=np.stack(arrays);masks=np.stack(maskarrays);md=accepted['dataset']
    for control in strong['controls']:
        path=ROOT/control['store_path'];manifest=json.loads((path/'manifest.json').read_text())
        check(manifest['manifest_sha256']==digest({k:v for k,v in manifest.items() if k!='manifest_sha256'}),'control manifest selfhash '+control['candidate'])
        with rasterio.open(path/'bands.tif') as src:
            cb=src.read();tiff_masks=src.read_masks()!=0
            check(np.array_equal(cb,bands),'independent full TIFF values '+control['candidate'])
            check(src.shape==(604,1233) and str(src.crs)=='EPSG:4326' and list(src.transform)[:6]==md['transform'],'native grid '+control['candidate'])
            check(src.compression.value.lower()=='zstd' and src.block_shapes==[(control['block_size'],control['block_size'])]*3 and src.profile['interleave']=='band','actual TIFF layout '+control['candidate'])
        if manifest['masks']['mode']=='implicit_all_valid':cm=np.ones(cb.shape,dtype=bool);check(tiff_masks.all() and masks.all(),'implicit masks justified '+control['candidate'])
        else:
            raw=zstd.decompress((path/'masks.zst').read_bytes());cm=np.unpackbits(np.frombuffer(raw,dtype=np.uint8),bitorder='little')[:bands.size].astype(bool).reshape(bands.shape)
        check(np.array_equal(cm,masks) and exact(manifest['metadata'],md),'independent masks/reconstruction metadata '+control['candidate'])
        check(sum(p.stat().st_size for p in path.iterdir())==control['storage']['total_bytes'],'complete control bytes '+control['candidate'],control['storage']['total_bytes'])
        for f in control['storage']['files']:check(file_hash(path/f['path'])==f['sha256'] and (path/f['path']).stat().st_size==f['bytes'],'control measured file '+control['candidate']+'/'+f['path'])
    for path,sha in strong['identity']['guard'].items():check(file_hash(ROOT/path)==sha,'code/input guard '+path)
    check(file_hash(ROOT/'engine/query.py')==accepted['benchmark']['identity']['implementation_sha256']['query.py'],'production center query unchanged from accepted benchmark')
    source_total=sum((ROOT/f['path']).stat().st_size for f in strong['source']['storage']['files']);custom_total=sum((ROOT/strong['accepted_custom']['store_path']/f['path']).stat().st_size for f in strong['accepted_custom']['storage']['files'])
    check(source_total==585293 and custom_total==535012,'actual source/custom baseline bytes')
    reduction=custom_total-min(c['storage']['total_bytes'] for c in strong['controls']);check(reduction==2568,'control complete storage advantage',reduction)
    real_geos={f['properties']['ProductionPlace']:f['geometry'] for f in json.loads((ROOT/'data/company-sample/2026-10-12/200001-17plots-valid.geojson').read_text())['features']}
    changes=[];total_center=total_overlap=0;independent_sets={}
    for p in spatial['plots']:
        pid=p['plot_id'];g=real_geos[pid];check(exact(g,p['geometry']) and digest(g)==p['geometry_sha256'],pid+' exact geometry')
        center=selected_cells(md,g);over=overlap(md,g);independent_sets[pid]=(set(center),set(over));total_center+=len(center);total_overlap+=len(over)
        for name,cells in [('center_covers',center),('positive_area_overlap',over)]:
            r=real_known_reduction(bands,masks,cells);reported=p['rules'][name]
            check([list(x) for x in cells]==reported['selected_cells'],pid+' independently clipped cellset '+name)
            check(exact(r,reported['source_result']) and exact(r,reported['compact_result']),pid+' independent full result '+name)
            if name=='center_covers':cr=r;check(exact(r,next(x for x in accepted['plots'] if x['plot_id']==pid)['source_result']),pid+' production remains center rule')
            else:
                for period in r['periods']:
                    if r['periods'][period]['mapped_loss_present'] is not cr['periods'][period]['mapped_loss_present']:changes.append((pid,period))
    check(total_center==1048 and total_overlap==1385,'independently recomputed total support',{'center':total_center,'overlap':total_overlap})
    check(set(changes)=={(x['plot_id'],x['period']) for x in spatial['changed_period_flags']},'all independently recomputed changed flags',changes)
    witness_records=[]
    for group in witness['changed_period_flags']:
        for w in group['witnesses']:
            pid=w['plot_id'];r,c=w['row'],w['col'];b=bounds(md,r,c);fraction=area(real_geos[pid],b)/((F(b[2])-F(b[0]))*(F(b[3])-F(b[1])))
            check((r,c) not in independent_sets[pid][0] and (r,c) in independent_sets[pid][1],pid+' witness inclusion '+str((r,c)))
            check([w['raw_values'][n] for n in ('treecover2000','lossyear','datamask')]==bands[:,r,c].tolist() and all(w['band_validity'].values())==bool(masks[:,r,c].all()),pid+' witness source values '+str((r,c)))
            check(abs(float(fraction)-w['angular_cell_intersection_fraction'])<1e-9,pid+' rational angular fraction '+str((r,c)))
            witness_records.append({'plot':pid,'row':r,'col':c,'raw':bands[:,r,c].tolist(),'exact_binary_coordinate_fraction':str(fraction),'fraction':float(fraction),'recorded_fraction':w['angular_cell_intersection_fraction']})
    check(len(witness_records)==15,'all15 changed-flag event witnesses')
    check(before=={str(p.relative_to(ROOT)):file_hash(p) for p in watched},'all accepted/research inputs unchanged during audit')
    report={'pass':all(c['pass'] for c in checks),'checks':checks,'changes':changes,'witnesses':witness_records,'accepted_fingerprints':before,'scope':'independent Fraction clipping of actual rings; no GEOS membership/intersection or study helper; TIFF decompression shares rasterio/GDAL'}
    (ROOT/'docs/lab/validator-strong-spatial-independent.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'pass':report['pass'],'failures':[c for c in checks if not c['pass']],'changed_flags':changes,'witness_count':len(witness_records)},indent=2))
    return int(not report['pass'])
if __name__=='__main__':sys.exit(main())
