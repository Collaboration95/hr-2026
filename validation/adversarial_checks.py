"""Bounded independent geometry/unknown and compressed-input checks.

Production query/decoder are the systems under test; expected query results
come from validation/run_checks.py, not engine helpers. No canonical writes.
"""
from compression import zstd
import json
import math
from pathlib import Path
import random
import sys
import tempfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from validation.run_checks import result_for, digest
from engine.model import Dataset
from engine.query import evaluate
from engine.indexed import evaluate_reader
from engine import codecs


def rectangle(w, s, e, n):
    return [[w, n], [e, n], [e, s], [w, s], [w, n]]


class FixtureReader:
    def __init__(self, dataset):
        self.metadata = dataset.metadata
        self.dataset = dataset
    def read_window(self, r0, r1, c0, c1):
        return self.dataset.bands[:, r0:r1, c0:c1], self.dataset.masks[:, r0:r1, c0:c1]


def main():
    checks, failures = [], []
    def check(ok, label, detail=None):
        checks.append({'pass': bool(ok), 'label': label, 'detail': detail})
        if not ok: failures.append(label)
    rng = random.Random(202610130522)
    np_rng = np.random.default_rng(202610130522)
    metadata = {'shape': [7, 9], 'transform': [.00025, 0, 98.77225, 0, -.00025, 8.582], 'crs': 'EPSG:4326'}
    a, _, ox, _, e, oy = metadata['transform']
    x = lambda c: ox+(c+.5)*a
    y = lambda r: oy+(r+.5)*e
    for iteration in range(180):
        b = np.stack([np_rng.integers(0, maximum+1, size=(7,9), dtype=np.uint8) for maximum in (100,25,2)])
        m = np_rng.random(b.shape) > .12
        c0, r0 = rng.randint(-2, 6), rng.randint(-2, 4)
        c1, r1 = c0+rng.randint(1, 4), r0+rng.randint(1, 4)
        ring = rectangle(x(c0), y(r1), x(c1), y(r0))
        shape = iteration % 3
        if shape == 0:
            geometry = {'type':'Polygon', 'coordinates':[ring]}
        elif shape == 1:
            left, right = x(c0)+.25*a, x(c1)-.25*a
            low, high = y(r1)+.25*a, y(r0)-.25*a
            geometry = {'type':'Polygon', 'coordinates':[ring, rectangle(left, low, right, high)]}
        else:
            # Disjoint island avoids invalid overlapping multipart topology.
            other = rectangle(x(c1+1), y(r1), x(c1+2), y(r0))
            geometry = {'type':'MultiPolygon', 'coordinates':[[ring], [other]]}
        missing = tuple(n for n in ('treecover2000','lossyear','datamask') if rng.random() < .10)
        dataset = Dataset(b, m, metadata).validate()
        expected, _ = result_for(b, m, metadata, geometry, missing)
        actual = evaluate(dataset, geometry, missing)
        windowed = evaluate_reader(FixtureReader(dataset), geometry, missing)
        check(expected == actual == windowed, f'seeded native-grid geometry/masks/unknown {iteration}', {'type':geometry['type'], 'missing':missing})
    # Native-decimal, one-ULP boundaries, both ring windings, isolated positive.
    b = np.zeros((3,7,9), dtype=np.uint8)
    b[0] = 80
    b[2] = 1
    b[1,1,1] = 25
    m = np.ones_like(b, dtype=bool)
    for edge, count in [(math.nextafter(x(1), -math.inf),1), (x(1),1), (math.nextafter(x(1),math.inf),0)]:
        ring = rectangle(edge, y(1)-a/4, x(1)+a/4, y(1)+a/4)
        for winding in (ring, list(reversed(ring))):
            geometry = {'type':'Polygon', 'coordinates':[winding]}
            expected, cells = result_for(b,m,metadata,geometry)
            actual = evaluate(Dataset(b,m,metadata), geometry)
            indexed = evaluate_reader(FixtureReader(Dataset(b,m,metadata)), geometry)
            check(expected == actual == indexed and len(cells) == count, 'native one-ULP boundary '+edge.hex())

    def reject(label, action):
        try:
            action()
        except ValueError as error:
            check(True, label, str(error))
        else:
            check(False, label, 'accepted invalid input')
    small = zstd.compress(b'A'*300)
    check(codecs._decompress(small, 300) == b'A'*300, 'valid independently generated 300-byte zstd frame')
    reject('bounded 64KiB frame cannot satisfy 1-byte declared stream', lambda: codecs._decompress(zstd.compress(b'B'*65536),1))
    reject('two concatenated frames rejected', lambda: codecs._decompress(small+small,300))
    reject('trailing 1-byte junk rejected', lambda: codecs._decompress(small+b'X',300))
    reject('truncated frame rejected', lambda: codecs._decompress(small[:-1],300))
    reject('unknown decompressed size rejected', lambda: codecs._decompress(zstd.compress(b'AB', options={zstd.CompressionParameter.content_size_flag:0}),2))
    # Two-byte content size retained; inject a non-single-segment history window.
    assert small[4] & 0x20 and small[4] >> 6 == 1
    huge_window = small[:4]+bytes([small[4] & ~0x20, 0xa0])+small[5:]
    reject('300-byte frame advertising 1GiB window rejected before decode', lambda: codecs._decompress(huge_window,300))
    with tempfile.TemporaryDirectory(prefix='bounded-codec-',dir=ROOT/'validation') as temporary:
        path = Path(temporary)/'store'
        tiny_metadata = {'shape':[2,2],'transform':[1,0,0,0,-1,2],'crs':'EPSG:4326'}
        tiny = np.zeros((3,2,2),dtype=np.uint8)
        tiny[2] = 1
        codecs.encode_store(tiny,np.ones_like(tiny,dtype=bool),tiny_metadata,path,'separate_zstd',2)
        original = (path/'index.json').read_bytes()
        index = json.loads(original)
        index['metadata']['shape'] = [10**12, 10**12]
        index['shape'] = [10**12, 10**12]
        index['index_sha256'] = digest({k:v for k,v in index.items() if k != 'index_sha256'})
        (path/'index.json').write_text(json.dumps(index))
        reject('self-checksummed trillion-cell dimensions rejected before arrays', lambda: codecs.decode_store(path))
        (path/'index.json').write_bytes(original)
        index = json.loads(original)
        index['chunks'][0]['streams']['treecover2000']['raw_size'] = 10**12
        index['index_sha256'] = digest({k:v for k,v in index.items() if k != 'index_sha256'})
        (path/'index.json').write_text(json.dumps(index))
        reject('self-checksummed trillion-byte raw stream rejected', lambda: codecs.decode_store(path))
        (path/'index.json').write_bytes(original[:-1]+b',"version":1}')
        reject('duplicate JSON index key rejected', lambda: codecs.decode_store(path))
    report = {'scope':'synthetic only; bounded 180 cases + 6 native ULP/winding cases + 10 compressed/parser probes',
              'pass':not failures,'check_count':len(checks),'failures':failures,'checks':checks}
    (ROOT/'docs/lab/validator-adversarial.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='checks'},indent=2))
    return int(bool(failures))


if __name__ == '__main__':
    sys.exit(main())
