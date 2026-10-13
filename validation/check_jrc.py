"""Independent JRC source/window, exact scalar query, codec and accounting audit.
No production query/codec/oracle/verification helpers; no canonical writes.
"""
from compression import zstd
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import struct
import sys
import xml.etree.ElementTree as ET
import numpy as np
import rasterio
from rasterio.windows import Window

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from validation.run_checks import selected_cells,digest,file_hash

def strict(a,b):
    return json.dumps(a,sort_keys=True,allow_nan=False)==json.dumps(b,sort_keys=True,allow_nan=False)

def independent_result(values,mask,metadata,geometry,missing=False):
    cells=selected_cells(metadata,geometry)
    h,w=values.shape
    covered=valid=invalid=outside=0
    counts={'0':0,'1':0}
    evidence=[]
    for r,c in cells:
        inside=0<=r<h and 0<=c<w
        evidence.append({'row':r,'col':c,'value':int(values[r,c]) if inside else None,'valid':bool(mask[r,c]) if inside else False})
        if not inside:outside+=1
        else:
            covered+=1
            if missing or not bool(mask[r,c]):invalid+=1
            else:valid+=1;counts[str(int(values[r,c]))]+=1
    n=len(cells);unknown=n if missing else outside+invalid
    reasons=[]
    if n==0:reasons.append('no_selected_cells')
    if outside:reasons.append('out_of_coverage')
    if invalid:reasons.append('band_mask_invalid')
    if n and not valid:reasons.append('no_valid_cells')
    if missing:reasons.append('missing_band')
    result={'selected_cell_count':n,'in_coverage_cell_count':covered,'out_of_coverage_cell_count':outside,
            'valid_cell_count':valid,'unknown_cell_count':unknown,'class_counts':counts if valid else None,
            'mapped_forest_present':(True if counts['1'] else None if unknown else False) if valid else None,
            'support':'unavailable' if missing else 'none' if not valid else 'partial' if unknown else 'complete',
            'unknown_reasons':reasons}
    return result,evidence

def independent_decode(path):
    index=json.loads((path/'index.json').read_text());payload=(path/'payload.bin').read_bytes()
    assert payload[:12]==struct.pack('<8sI',b'JRCBIN1\0',1)
    assert digest({k:v for k,v in index.items() if k!='index_sha256'})==index['index_sha256']
    assert hashlib.sha256(payload).hexdigest()==index['payload_sha256'] and len(payload)==index['payload_bytes']
    shape=index['metadata']['shape'];v=np.zeros(shape,dtype=np.uint8);m=np.zeros(shape,dtype=bool);seen=np.zeros(shape,dtype=np.uint8)
    offset=12
    for item in index['chunks']:
        assert item['offset']==offset
        compressed=payload[offset:offset+item['size']];offset+=item['size']
        assert hashlib.sha256(compressed).hexdigest()==item['sha256']
        n=item['height']*item['width'];bitbytes=(n+7)//8
        packed='packed' in index['candidate'];boundary=bitbytes if packed else n
        assert item['raw_size']==boundary+bitbytes<=8*1024*1024
        assert zstd.get_frame_info(compressed).decompressed_size==item['raw_size']
        d=zstd.ZstdDecompressor();raw=d.decompress(compressed,max_length=item['raw_size']+1)
        assert len(raw)==item['raw_size'] and d.eof and not d.unused_data
        assert hashlib.sha256(raw).hexdigest()==item['raw_sha256']
        values=np.unpackbits(np.frombuffer(raw[:boundary],dtype=np.uint8),bitorder='little')[:n] if packed else np.frombuffer(raw[:boundary],dtype=np.uint8)
        masks=np.unpackbits(np.frombuffer(raw[boundary:],dtype=np.uint8),bitorder='little')[:n].astype(bool)
        if n%8:
            assert raw[-1]>>(n%8)==0
            if packed:assert raw[boundary-1]>>(n%8)==0
        assert np.all(values<=1)
        r,c,h,w=(item[k] for k in ('row','col','height','width'))
        v[r:r+h,c:c+w]=values.reshape(h,w);m[r:r+h,c:c+w]=masks.reshape(h,w);seen[r:r+h,c:c+w]+=1
    assert offset==len(payload) and np.all(seen==1)
    return v,m,index['metadata']

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,default=ROOT/'docs/lab/validator-jrc-independent.json');args=parser.parse_args()
    artifact_path=ROOT/'artifacts/jrc-baseline-v1.json'
    watched=[artifact_path,*sorted((ROOT/'engine').glob('jrc*.py'))]
    before={str(p.relative_to(ROOT)):file_hash(p) for p in watched}
    artifact=json.loads(artifact_path.read_text());md=artifact['dataset'];report={'checks':[],'failures':[]}
    def check(ok,label,evidence=None):
        report['checks'].append({'pass':bool(ok),'label':label,'evidence':evidence})
        if not ok:report['failures'].append(label)
    prov_path=ROOT/'data/experimental/jrc/provenance.json';prov=json.loads(prov_path.read_text())
    check(file_hash(prov_path)=='c99d7780af8778be4c1ad7123c31fbee3b09401d3ff4d48e2eeece15ea434f7b','pinned acquisition manifest')
    qml=ROOT/'data/experimental/lead/jrc-semantics/JRC_GFC2020_V4.qml'
    check(file_hash(qml)=='d089a9d21a10537a13c77f206fd8ac844d364800b48580361893179d902080b0','pinned official QML')
    labels={x.attrib['value']:dict(x.attrib) for x in ET.fromstring(qml.read_bytes()).findall('.//colorrampshader/item')}
    check(labels['0']['label']=='Non-forest' and labels['0']['alpha']=='0' and labels['1']['label']=='Forest','official QML zero is Non-forest despite alpha0',labels)
    xml=ROOT/'data/experimental/lead/jrc-semantics/JRC_GFC2020_V4.xml';xml_root=ET.fromstring(xml.read_bytes())
    check(file_hash(xml)=='cdccfb393e306cf6775a2041263c09885a275a67b8098acde6536f06358a66b9','pinned official XML')
    check(all(md['xml_observations'][key]==xml_root.findtext('.//'+tag) for key,tag in [('title','resTitle'),('create_date','createDate'),('publication_date','pubDate'),('revision_date','reviseDate')]),'XML older dates retained exactly')
    check(md['citation']==prov['required_citation'],'exact required source citation')
    check(md['version']=='v4' and type(md['reference_year']) is int and md['reference_year']==2020 and md['publication_year']==2026,'separate reference2020/version4/publication2026')
    chip=ROOT/'data/experimental/jrc'/prov['chip_file'];source=ROOT/'data/experimental/jrc'/prov['source_file']
    check(file_hash(chip)==prov['chip_sha256'] and chip.stat().st_size==prov['chip_bytes'],'original chip identity')
    check(file_hash(source)==prov['source_sha256'] and source.stat().st_size==prov['source_bytes'],'full source tile identity')
    with rasterio.open(chip) as ch,rasterio.open(source) as src:
        row,col,h,w=prov['chip_window_source_row_col_height_width'];win=Window(col,row,w,h)
        v=ch.read(1);m=ch.read_masks(1)!=0
        check(v.shape==(1809,3695) and v.size==6684255,'exact native JRC grid')
        check(ch.nodata is None and np.all(m),'all chip masks known; nodata absent')
        check(np.array_equal(v,src.read(1,window=win)),'all original window pixels exact')
        check(np.array_equal(m,src.read_masks(1,window=win)!=0),'all original window mask bits exact')
        check(list(ch.transform)[:6]==list(src.window_transform(win))[:6]==md['transform'],'native original window/chip affine equality')
        check(ch.transform.a==1/12000 and ch.transform.e==-1/12000 and str(ch.crs)=='EPSG:4326','native angular step/CRS')
    counts={str(k):int(n) for k,n in zip(*np.unique(v,return_counts=True))}
    check(counts==prov['decoded_value_counts'],'full source class histogram',counts)
    geofile=ROOT/'data/company-sample/2026-10-12/200001-17plots-valid.geojson'
    geo={f['properties']['ProductionPlace']:f['geometry'] for f in json.loads(geofile.read_text())['features']}
    answers=[];plot_rows=[]
    for p in artifact['plots']:
        expected,evidence=independent_result(v,m,md,geo[p['plot_id']]);answers.append(expected)
        check(strict(expected,p['source_result']) and strict(expected,p['compact_result']),p['plot_id']+' independent full query with strict JSON types')
        check(strict(p['geometry'],geo[p['plot_id']]) and p['geometry_sha256']==digest(geo[p['plot_id']]),p['plot_id']+' exact input geometry/hash')
        check(strict(evidence,p['evidence']['cells']),p['plot_id']+' all independent native evidence records')
        check(p['receipt']['source_result_sha256']==digest(expected) and p['receipt']['evidence_sha256']==digest(p['evidence']),p['plot_id']+' result/evidence receipts')
        plot_rows.append({'plot_id':p['plot_id'],**expected})
    check(sum(a['selected_cell_count'] for a in answers)==9511==artifact['summary']['selected_cell_count_sum'],'cohort selected sum')
    check({str(k):sum(a['class_counts'][str(k)] for a in answers) for k in (0,1)}==artifact['summary']['class_counts_sum'],'cohort class sums')
    check(artifact['full_chip']['raw_sha256']==hashlib.sha256(v.tobytes()).hexdigest() and artifact['full_chip']['mask_sha256']==hashlib.sha256(m.tobytes()).hexdigest(),'full-chip raw/mask digests independent')
    benchmark=artifact['benchmark'];answer_hash=digest(answers)
    check(benchmark['baseline']['answer_sha256']==answer_hash,'benchmark pinned independent answers')
    for candidate in benchmark['candidates']:
        path=ROOT/candidate['storage']['path'];cv,cm,cmeta=independent_decode(path)
        check(np.array_equal(cv,v) and np.array_equal(cm,m) and strict(cmeta,md),path.name+' independent full raw/mask/metadata roundtrip')
        actual=sum(p.stat().st_size for p in path.iterdir() if p.is_file())
        check(actual==candidate['storage']['total_bytes'],path.name+' actual complete store bytes',actual)
        check(candidate['answer_sha256']==answer_hash,path.name+' answer digest')
        for record in candidate['storage']['files']:
            f=ROOT/record['path'];check(f.stat().st_size==record['bytes'] and file_hash(f)==record['sha256'],path.name+' measured '+f.name)
        for field in ('encode','decode','hot_17_queries'):
            for unit in ('wall','cpu'):
                stats=candidate[field][unit];samples=sorted(stats['samples']);position=.95*(len(samples)-1);lo=int(position);hi=min(lo+1,len(samples)-1);p95=samples[lo]+(samples[hi]-samples[lo])*(position-lo)
                check(stats['min']==samples[0] and stats['median']==statistics.median(samples) and abs(stats['p95']-p95)<1e-10,path.name+' '+field+' '+unit+' statistics')
    base_files=benchmark['baseline']['files'];base_total=sum((ROOT/f['path']).stat().st_size for f in base_files)
    check(base_total==57653==benchmark['baseline']['total_bytes'],'same-chip loader baseline actual files')
    selected_bytes=sum(p.stat().st_size for p in (ROOT/artifact['store']['path']).iterdir() if p.is_file())
    common_meta=sum((ROOT/f['path']).stat().st_size for f in base_files[1:]);common_plots=sum((ROOT/f['path']).stat().st_size for f in benchmark['common_plot_inputs'])
    check(selected_bytes==21459 and common_meta==11415 and common_plots==19265,'selected and symmetric support accounting')
    report['storage']={'source_loader':base_total,'selected_store':selected_bytes,'symmetric_compact':selected_bytes+common_meta,'source_with_common_plots':base_total+common_plots,'symmetric_compact_with_common_plots':selected_bytes+common_meta+common_plots}
    for name in ('cold_source','cold_smallest_encoded'):
        check(all(c['answer_sha256']==answer_hash for c in benchmark[name]['children']),name+' every archived child answer')
    check(artifact['content_sha256']==digest({k:x for k,x in artifact.items() if k!='content_sha256'}),'artifact content digest')
    check(before=={str(p.relative_to(ROOT)):file_hash(p) for p in watched},'implementation/artifact stable during independent check')
    report.update(pass_all=not report['failures'],plots=plot_rows,source_hash=file_hash(source),chip_hash=file_hash(chip),content=artifact['content_sha256'],scope='JRC-only cells and native grid; no browser, area or Hansen count inference')
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:x for k,x in report.items() if k not in ('checks','plots')},indent=2))
    return int(not report['pass_all'])

if __name__=='__main__':sys.exit(main())
