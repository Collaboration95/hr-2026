"""Small exhaustive JRC class/mask/unknown controls with independent expected answers."""
import itertools
import json
import math
from pathlib import Path
import sys
import tempfile
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from validation.check_jrc import independent_result,independent_decode,strict
from engine.jrc import JrcDataset,evaluate_jrc
from engine.jrc_codec import encode_jrc_store,CANDIDATES

def rect(w,s,e,n):return {'type':'Polygon','coordinates':[[[w,n],[e,n],[e,s],[w,s],[w,n]]]}
def main():
    md={'shape':[2,2],'transform':[1,0,0,0,-1,2],'crs':'EPSG:4326'}
    v=np.array([[0,1],[1,0]],dtype=np.uint8)
    geometries=[rect(0,0,2,2),rect(-1,0,1,2),rect(-2,0,-1,2),rect(.01,.01,.1,.1),rect(0,1,1,2)]
    checks=[]
    for bits in itertools.product((False,True),repeat=4):
        m=np.array(bits,dtype=bool).reshape(2,2)
        ds=JrcDataset(v,m,md).validate()
        for missing in (False,True):
            for i,g in enumerate(geometries):
                expected,_=independent_result(v,m,md,g,missing)
                checks.append({'pass':strict(expected,evaluate_jrc(ds,g,missing)),'mask':list(bits),'missing':missing,'geometry':i})
    # Single known zero is a complete false mapped-class signal, not unknown.
    known=evaluate_jrc(JrcDataset(v,np.ones_like(v,dtype=bool),md),rect(0,1,1,2))
    checks.append({'pass':known['class_counts']=={'0':1,'1':0} and known['mapped_forest_present'] is False and known['unknown_cell_count']==0,'case':'known transparent zero'})
    with tempfile.TemporaryDirectory(prefix='jrc-masked-roundtrip-',dir=ROOT/'validation/jrc') as tmp:
        for candidate in CANDIDATES:
            mask=np.array([[True,False],[False,True]],dtype=bool)
            path=Path(tmp)/candidate
            encode_jrc_store(JrcDataset(v,mask,md),path,candidate,2)
            actual,valid,meta=independent_decode(path)
            checks.append({'pass':np.array_equal(actual,v) and np.array_equal(valid,mask) and strict(meta,md),'case':candidate+' preserves masked raw ones'})
    # Exact acquired JRC affine lattice: included boundary and one-ULP exclusion.
    md2={'shape':[2,2],'transform':[1/12000,0,98.77241666666667,0,-1/12000,8.581916666666666],'crs':'EPSG:4326'}
    a,_,x0,_,e,y0=md2['transform'];x=x0+1.5*a;y=y0+1.5*e
    for edge,count in [(math.nextafter(x,-math.inf),1),(x,1),(math.nextafter(x,math.inf),0)]:
        g=rect(edge,y-a/4,x+a/4,y+a/4)
        expected,_=independent_result(v,np.ones_like(v,dtype=bool),md2,g)
        actual=evaluate_jrc(JrcDataset(v,np.ones_like(v,dtype=bool),md2),g)
        checks.append({'pass':strict(expected,actual) and actual['selected_cell_count']==count,'case':'native boundary '+edge.hex()})
    report={'scope':'synthetic; raw class0/class1, all mask combinations, missing, outside, tiny, partial, original JRC ULP lattice','checks':checks,'pass':all(x['pass'] for x in checks)}
    (ROOT/'docs/lab/validator-jrc-unknown.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'pass':report['pass'],'checks':len(checks),'failures':[x for x in checks if not x['pass']]},indent=2))
    return int(not report['pass'])
if __name__=='__main__':sys.exit(main())
