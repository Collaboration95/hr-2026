"""Research-only one-bit GeoTIFF control; no production adapter."""
import hashlib
import json
from pathlib import Path
import sys
from compression import zstd
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import numpy as np
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import Affine
from engine.codecs import _metadata, _pairs, _invalid_constant, _decompress, _unpack_bits
from engine.jrc import JrcDataset
from engine.source import canonical_bytes

MAX_MANIFEST = 256*1024
MAX_FILE = 32*1024*1024
FORMAT = 'research.jrc-onebit-geotiff.v1'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def bounded(path, maximum):
    path = Path(path)
    require(not path.is_symlink() and path.is_file(), 'unsafe or missing file')
    with path.open('rb') as f:
        raw = f.read(maximum+1)
    require(len(raw) <= maximum, 'file exceeds allocation limit')
    return raw


def record(path):
    raw = bounded(path, MAX_FILE)
    return {'path': Path(path).name, 'bytes': len(raw), 'sha256': digest(raw)}


def metadata_check(metadata):
    h, w = _metadata(metadata)
    t = metadata['transform']
    require(t[0] > 0 and t[4] < 0 and t[1] == 0 and t[3] == 0
            and metadata['crs'] == 'EPSG:4326', 'invalid native JRC grid')
    require('nodata' in metadata and metadata['nodata'] is None, 'JRC nodata must be explicit null')
    return h, w


def settings(level):
    require(type(level) is int and level in (3, 19), 'only fixed levels3/19 allowed')
    return {'driver': 'GTiff', 'compression': 'ZSTD', 'level': level, 'predictor': 1,
            'block': 1024, 'nbits': 1, 'dtype': 'uint8', 'bands': 1, 'threads': 1}


def seal(manifest):
    body = {k: v for k, v in manifest.items() if k != 'manifest_sha256'}
    return dict(body, manifest_sha256=digest(canonical_bytes(body)))


def encode(dataset, path, level=19):
    h, w = metadata_check(dataset.metadata)
    dataset.validate()
    cfg = settings(level)
    path = Path(path)
    require(not path.exists() and not path.is_symlink(), 'encoder requires a new directory')
    require(len(canonical_bytes(dataset.metadata)) < MAX_MANIFEST//2, 'metadata too large')
    path.mkdir(parents=True)
    with rasterio.open(path/'values.tif', 'w', driver='GTiff', width=w, height=h,
                       count=1, dtype='uint8', crs=dataset.metadata['crs'],
                       transform=Affine(*dataset.metadata['transform']), nodata=None,
                       tiled=True, blockxsize=1024, blockysize=1024, compress='ZSTD',
                       zstd_level=level, predictor=1, nbits=1, num_threads=1) as dst:
        dst.write(dataset.values, 1)
    invalid = int((~dataset.mask).sum())
    mode = 'all_valid' if invalid == 0 else 'packed_little_zstd3'
    files = [record(path/'values.tif')]
    if invalid:
        (path/'mask.bin').write_bytes(zstd.compress(np.packbits(dataset.mask.reshape(-1), bitorder='little').tobytes(), level=3))
        files.append(record(path/'mask.bin'))
    manifest = seal({'format': FORMAT, 'metadata': dataset.metadata, 'settings': cfg,
                     'mask_mode': mode, 'invalid_cells': invalid, 'files': files})
    raw = canonical_bytes(manifest)
    require(len(raw) <= MAX_MANIFEST, 'manifest too large')
    (path/'manifest.json').write_bytes(raw)
    return storage(path)


def read_manifest(path):
    path = Path(path)
    require(not path.is_symlink(), 'unsafe store directory')
    try:
        x = json.loads(bounded(path/'manifest.json', MAX_MANIFEST), object_pairs_hook=_pairs,
                       parse_constant=_invalid_constant)
        require(type(x) is dict and set(x) == {'format','metadata','settings','mask_mode','invalid_cells','files','manifest_sha256'},
                'invalid manifest fields')
        require(x == seal(x), 'manifest checksum mismatch')
        require(x['format'] == FORMAT, 'unknown format')
        h, w = metadata_check(x['metadata'])
        require(canonical_bytes(x['settings']) == canonical_bytes(settings(x['settings']['level'])), 'contradictory codec settings')
        require(type(x['invalid_cells']) is int and 0 <= x['invalid_cells'] <= h*w, 'invalid mask count')
        mode = x['mask_mode']
        require(mode in ('all_valid', 'packed_little_zstd3'), 'unknown mask mode')
        require((mode == 'all_valid') == (x['invalid_cells'] == 0), 'contradictory mask mode')
        names = ['values.tif'] + (['mask.bin'] if x['invalid_cells'] else [])
        require(type(x['files']) is list and len(x['files']) == len(names), 'file count mismatch')
        require({p.name for p in path.iterdir()} == set(names + ['manifest.json']), 'unaccounted/missing store files')
        for f, name in zip(x['files'], names):
            require(type(f) is dict and set(f) == {'path','bytes','sha256'} and f['path'] == name, 'unsafe manifest path/fields')
            require(type(f['bytes']) is int and 0 < f['bytes'] <= MAX_FILE, 'invalid file length')
            require(type(f['sha256']) is str and len(f['sha256']) == 64, 'invalid file digest')
        return x
    except (KeyError, TypeError, RecursionError, OverflowError, UnicodeError) as exc:
        raise ValueError('malformed manifest') from exc


def decode(path):
    path = Path(path)
    x = read_manifest(path)
    h, w = x['metadata']['shape']
    blobs = {}
    for f in x['files']:
        raw = bounded(path/f['path'], MAX_FILE)
        require(len(raw) == f['bytes'] and digest(raw) == f['sha256'], 'file integrity mismatch')
        blobs[f['path']] = raw
    # MemoryFile binds the bytes checked above and prevents uncounted sidecars.
    with MemoryFile(blobs['values.tif']) as mem, mem.open() as src:
        require(src.driver == 'GTiff' and src.shape == (h,w) and src.count == 1
                and src.dtypes == ('uint8',) and src.nodata is None, 'contradictory TIFF shape/type/nodata')
        require(list(src.transform)[:6] == x['metadata']['transform'] and str(src.crs) == x['metadata']['crs'], 'TIFF grid mismatch')
        require(src.block_shapes == [(1024,1024)] and src.compression.value == 'ZSTD'
                and src.tags(1, ns='IMAGE_STRUCTURE').get('NBITS') == '1'
                and src.tags(ns='IMAGE_STRUCTURE').get('PREDICTOR', '1') == '1', 'TIFF codec layout mismatch')
        values = src.read(1)
        require(bool((src.read_masks(1) == 255).all()), 'TIFF internal mask contradicts independent mask mode')
    if x['mask_mode'] == 'all_valid':
        mask = np.ones((h,w), dtype=bool)
    else:
        raw = _decompress(blobs['mask.bin'], (h*w+7)//8)
        mask = _unpack_bits(raw, h*w).astype(bool).reshape(h,w)
    require(int((~mask).sum()) == x['invalid_cells'], 'decoded mask count mismatch')
    return JrcDataset(values, mask, x['metadata']).validate()


def storage(path):
    path = Path(path)
    x = read_manifest(path)
    files = [record(path/f['path']) for f in x['files']] + [record(path/'manifest.json')]
    require(files[:-1] == x['files'], 'storage differs from manifest')
    return {'files': files, 'payload_bytes': files[0]['bytes'], 'manifest_bytes': files[-1]['bytes'],
            'mask_bytes': sum(f['bytes'] for f in files if f['path'] == 'mask.bin'),
            'total_bytes': sum(f['bytes'] for f in files)}
