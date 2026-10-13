"""Additive standard GeoTIFF control; never modifies accepted engine artifacts.

The required manifest preserves exact reconstruction metadata and checksums.
Validity is implicit only after all three masks are checked; otherwise a packed
independent three-band mask stream preserves every mask and raw masked value.
This is bounded local-file validation, not a malicious-GeoTIFF certification.
"""
from compression import zstd
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import rasterio
from rasterio.enums import MaskFlags
from rasterio.windows import Window

from .codecs import _metadata, _decompress
from .model import BAND_NAMES, Dataset
from .source import canonical_bytes, sha256_file

FORMAT = 'plotline.geotiff-control.v1'
MAX_MANIFEST = 256 * 1024
MAX_FILE = 128 * 1024 * 1024
KNOWN_FILES = {'manifest.json', 'bands.tif', 'masks.zst'}


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _grid(metadata):
    h, w = _metadata(metadata)  # Existing bounded JSON/dimension validation.
    a, b, _, d, e, _ = metadata['transform']
    if metadata['crs'] != 'EPSG:4326' or a <= 0 or e >= 0 or b != 0 or d != 0:
        raise ValueError('control requires native north-up EPSG:4326')
    if 'band_names' in metadata and metadata['band_names'] != list(BAND_NAMES):
        raise ValueError('band_names differ from the three required bands')
    return h, w


def _settings(block):
    if type(block) is not int or block not in (256, 512):
        raise ValueError('control block_size must be 256 or 512')
    return {'compression': 'zstd', 'level': 19, 'predictor': 1,
            'block_size': block, 'interleave': 'band', 'dtype': 'uint8', 'bands': 3}


def _record(path):
    return {'path': path.name, 'bytes': path.stat().st_size, 'sha256': sha256_file(path)}


def storage_info(path):
    path = Path(path)
    files = [_record(p) for p in sorted(path.iterdir()) if p.is_file()]
    if any(f['path'] not in KNOWN_FILES for f in files):
        raise ValueError('unaccounted control file')
    sizes = {f['path']: f['bytes'] for f in files}
    return {'total_bytes': sum(sizes.values()), 'raster_bytes': sizes.get('bands.tif', 0),
            'mask_bytes': sizes.get('masks.zst', 0), 'manifest_bytes': sizes.get('manifest.json', 0),
            'files': files}


def encode_control(dataset, path, block_size=256):
    """Write one new dedicated store; refuse replacement of existing evidence."""
    started, cpu = time.perf_counter_ns(), time.process_time_ns()
    if (not isinstance(dataset, Dataset) or not isinstance(dataset.bands, np.ndarray)
            or not isinstance(dataset.masks, np.ndarray) or np.ma.isMaskedArray(dataset.bands)
            or np.ma.isMaskedArray(dataset.masks)):
        raise ValueError('control requires Dataset with numpy band/mask arrays')
    h, w = _grid(dataset.metadata)
    dataset.validate()
    settings = _settings(block_size)
    if len(canonical_bytes(dataset.metadata)) > MAX_MANIFEST // 2:
        raise ValueError('reconstruction metadata exceeds control limit')
    path = Path(path)
    if path.exists() or path.is_symlink():
        raise ValueError('control destination already exists; choose a new content-addressed store')
    path.mkdir(parents=True)
    try:
        with rasterio.open(path / 'bands.tif', 'w', driver='GTiff', height=h, width=w,
                           count=3, dtype='uint8', crs=dataset.metadata['crs'],
                           transform=rasterio.Affine(*dataset.metadata['transform']),
                           tiled=True, blockxsize=block_size, blockysize=block_size,
                           compress='ZSTD', zstd_level=19, predictor=1, interleave='band',
                           photometric='MINISBLACK', num_threads=1) as dst:
            dst.write(dataset.bands)
            for i, name in enumerate(BAND_NAMES, 1):
                dst.set_band_description(i, name)
        invalid = [int(np.count_nonzero(~m)) for m in dataset.masks]
        masks = {'mode': 'implicit_all_valid', 'invalid_counts': invalid}
        if any(invalid):
            raw = np.packbits(dataset.masks.reshape(-1), bitorder='little').tobytes()
            (path / 'masks.zst').write_bytes(zstd.compress(raw, level=3))
            masks.update(mode='independent_bitpack_zstd', raw_bytes=len(raw),
                         raw_sha256=hashlib.sha256(raw).hexdigest(), level=3, bitorder='little')
        manifest = {'format': FORMAT, 'version': 1,
                    'candidate': f'gtiff_zstd19_p1_b{block_size}', 'settings': settings,
                    'metadata': dataset.metadata, 'masks': masks,
                    'files': [_record(p) for p in sorted(path.iterdir())]}
        manifest['manifest_sha256'] = digest(manifest)
        encoded = canonical_bytes(manifest)
        if len(encoded) > MAX_MANIFEST or any(f['bytes'] > MAX_FILE for f in manifest['files']):
            raise ValueError('encoded control exceeds bounded file limits')
        (path / 'manifest.json').write_bytes(encoded)
    except Exception:
        # Only a newly created owned directory is cleaned; never an existing store.
        for child in path.iterdir():
            if child.name in KNOWN_FILES and child.is_file():
                child.unlink()
        if not any(path.iterdir()):
            path.rmdir()
        raise
    return {'candidate': manifest['candidate'], 'settings': settings, **storage_info(path),
            'mask_mode': masks['mode'], 'encode_wall_ms': (time.perf_counter_ns()-started)/1e6,
            'encode_cpu_ms': (time.process_time_ns()-cpu)/1e6}


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate manifest key')
        result[key] = value
    return result


def _constant(value):
    raise ValueError('nonfinite manifest value')


def _load_manifest(path):
    if path.is_symlink() or not path.is_dir():
        raise ValueError('control must be a regular local directory')
    filename = path / 'manifest.json'
    if filename.is_symlink() or not filename.is_file():
        raise ValueError('required manifest missing or symlinked')
    if filename.stat().st_size > MAX_MANIFEST:
        raise ValueError('manifest exceeds bounded size')
    try:
        with filename.open('rb') as stream:
            raw = stream.read(MAX_MANIFEST + 1)
        if len(raw) > MAX_MANIFEST:
            raise ValueError('manifest exceeds bounded size')
        m = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant)
        if type(m) is not dict or set(m) != {'format', 'version', 'candidate', 'settings',
                                            'metadata', 'masks', 'files', 'manifest_sha256'}:
            raise ValueError('invalid manifest schema')
        unsigned = {k: v for k, v in m.items() if k != 'manifest_sha256'}
        if m['manifest_sha256'] != digest(unsigned):
            raise ValueError('manifest checksum mismatch')
        if m['format'] != FORMAT or type(m['version']) is not int or m['version'] != 1:
            raise ValueError('unsupported control format/version')
        h, w = _grid(m['metadata'])  # Caps before any raster/mask allocation.
        expected = _settings(m['settings']['block_size'])
        if canonical_bytes(m['settings']) != canonical_bytes(expected):
            raise ValueError('unsupported control settings')
        if m['candidate'] != f'gtiff_zstd19_p1_b{expected["block_size"]}':
            raise ValueError('candidate/settings mismatch')
        masks = m['masks']
        counts = masks['invalid_counts']
        if (type(counts) is not list or len(counts) != 3 or
                any(type(n) is not int or not 0 <= n <= h*w for n in counts)):
            raise ValueError('invalid independent mask counts')
        names = {'bands.tif'}
        if masks['mode'] == 'implicit_all_valid':
            if masks != {'mode': 'implicit_all_valid', 'invalid_counts': [0, 0, 0]}:
                raise ValueError('implicit mask mode requires every band mask valid')
        elif masks['mode'] == 'independent_bitpack_zstd':
            if (set(masks) != {'mode', 'invalid_counts', 'raw_bytes', 'raw_sha256', 'level', 'bitorder'}
                    or not any(counts) or type(masks['raw_bytes']) is not int
                    or masks['raw_bytes'] != (3*h*w+7)//8 or type(masks['level']) is not int
                    or masks['level'] != 3 or masks['bitorder'] != 'little'):
                raise ValueError('invalid packed mask specification')
            names.add('masks.zst')
        else:
            raise ValueError('unsupported mask mode')
        if type(m['files']) is not list or len(m['files']) != len(names):
            raise ValueError('invalid file list')
        if {f['path'] for f in m['files']} != names:
            raise ValueError('only known fixed filenames allowed')
        if {p.name for p in path.iterdir()} != names | {'manifest.json'}:
            raise ValueError('unexpected/missing control files or mask mode mismatch')
        for entry in m['files']:
            if set(entry) != {'path', 'bytes', 'sha256'}:
                raise ValueError('invalid file record')
            f = path / entry['path']
            if entry['path'] == 'masks.zst' and (type(entry['bytes']) is not int or
                    entry['bytes'] > masks['raw_bytes'] + masks['raw_bytes']//128 + 1024):
                raise ValueError('mask stream exceeds bounded compressed size')
            if (type(entry['bytes']) is not int or not 0 < entry['bytes'] <= MAX_FILE
                    or f.is_symlink() or not f.is_file() or f.stat().st_size != entry['bytes']
                    or sha256_file(f) != entry['sha256']):
                raise ValueError('control file bytes/hash mismatch')
        return m
    except (KeyError, TypeError, UnicodeError, RecursionError, OverflowError) as exc:
        raise ValueError('malformed control manifest') from exc


class ControlWindowReader:
    """Whole files verified at initialization; original lattice metadata retained.

    GDAL block cache may warm. Unlike the custom codec, subsequent reads do not
    perform per-chunk SHA checks. Size/mtime/identity changes are rejected; caller
    race guards additionally rehash all files before/after measurements.
    """
    def __init__(self, path):
        self.path = Path(path)
        self._closed = False
        self.manifest = _load_manifest(self.path)
        self.metadata = self.manifest['metadata']
        self._shape = tuple(self.metadata['shape'])
        self._files = [self.path / name for name in sorted(KNOWN_FILES) if (self.path / name).exists()]
        self._stats = [self._stat(p) for p in self._files]
        self._src = rasterio.open(self.path / 'bands.tif')
        try:
            src, block = self._src, self.manifest['settings']['block_size']
            if (src.driver != 'GTiff' or src.count != 3 or src.dtypes != ('uint8',)*3
                    or src.shape != self._shape or str(src.crs) != self.metadata['crs']
                    or list(src.transform)[:6] != self.metadata['transform']
                    or src.compression is None or src.compression.value.lower() != 'zstd'
                    or src.profile.get('tiled') is not True
                    or src.block_shapes != [(block, block)]*3
                    or src.profile.get('interleave') != 'band'
                    or src.tags(ns='IMAGE_STRUCTURE').get('PREDICTOR', '1') != '1'
                    or src.descriptions != BAND_NAMES or src.nodatavals != (None,)*3
                    or any(flags != [MaskFlags.all_valid] for flags in src.mask_flag_enums)):
                raise ValueError('GeoTIFF header/grid/type/mask differs from manifest contract')
            self._masks = None
            spec = self.manifest['masks']
            if spec['mode'] != 'implicit_all_valid':
                entry = next(f for f in self.manifest['files'] if f['path'] == 'masks.zst')
                with (self.path / 'masks.zst').open('rb') as stream:
                    compressed = stream.read(entry['bytes'] + 1)
                if len(compressed) != entry['bytes'] or hashlib.sha256(compressed).hexdigest() != entry['sha256']:
                    raise ValueError('mask stream changed during initialization')
                raw = _decompress(compressed, spec['raw_bytes'])
                n = 3*self._shape[0]*self._shape[1]
                if hashlib.sha256(raw).hexdigest() != spec['raw_sha256'] or (n % 8 and raw[-1] >> (n % 8)):
                    raise ValueError('packed mask raw hash/padding mismatch')
                self._masks = np.unpackbits(np.frombuffer(raw, dtype=np.uint8), bitorder='little',
                                            count=n).astype(bool).reshape(3, *self._shape)
                if [int(np.count_nonzero(~m)) for m in self._masks] != spec['invalid_counts']:
                    raise ValueError('independent mask counts differ')
        except Exception:
            self._src.close()
            raise

    @staticmethod
    def _stat(path):
        s = path.stat()
        return (s.st_size, s.st_mtime_ns, s.st_ino)

    def read_window(self, r0, r1, c0, c1):
        if self._closed:
            raise ValueError('control reader closed')
        if ([self._stat(p) for p in self._files] != self._stats):
            raise ValueError('control files changed after initialization')
        h, w = self._shape
        if (any(type(n) is not int for n in (r0, r1, c0, c1)) or
                not 0 <= r0 < r1 <= h or not 0 <= c0 < c1 <= w):
            raise ValueError('window must use in-coverage nonempty integer bounds')
        bands = self._src.read(window=Window(c0, r0, c1-c0, r1-r0))
        masks = (np.ones(bands.shape, dtype=bool) if self._masks is None else
                 self._masks[:, r0:r1, c0:c1].copy())
        Dataset(bands, masks, dict(self.metadata, shape=[r1-r0, c1-c0])).validate()
        return bands, masks

    def close(self):
        if not self._closed:
            self._src.close()
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def decode_control(path):
    with ControlWindowReader(path) as reader:
        bands, masks = reader.read_window(0, reader.metadata['shape'][0], 0, reader.metadata['shape'][1])
        return Dataset(bands, masks, reader.metadata).validate()


def main():
    from .strong_baseline_measure import main as run
    run()


if __name__ == '__main__':
    main()
