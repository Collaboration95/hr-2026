"""Read immutable acquired inputs and preserve their exact identity."""
from contextlib import ExitStack, contextmanager
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
import rasterio
from .model import BAND_NAMES, Dataset

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = Path('data/company-sample/2026-10-12')
CSV_NAME = '200001-17plots-valid_2025-08-02T09_11_12Z.csv'
GEOJSON_NAME = '200001-17plots-valid.geojson'


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def object_hash(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


@contextmanager
def open_sources(root=None):
    """Verify identity/grid and keep three immutable TIFF readers open.

    Header and hash validation do not decode full raster arrays. Callers own
    their reads only inside this context; all handles close on error or exit.
    """
    root = Path(root) if root is not None else ROOT
    provenance = json.loads((root / 'data/public/provenance.json').read_text())
    acquired = {layer['band']: layer for layer in provenance['layers']}
    metadata, sources, readers = None, [], []
    with ExitStack() as stack:
        for name in BAND_NAMES:
            rel = Path('data/public') / f'hansen_{name}_sample.tif'
            path = root / rel
            digest = sha256_file(path)
            expected = acquired[name]
            if digest != expected['chip_sha256'] or path.stat().st_size != expected['chip_bytes']:
                raise ValueError(f'{name} chip differs from acquisition provenance')
            src = stack.enter_context(rasterio.open(path))
            grid = {'shape': [src.height, src.width],
                    'transform': list(src.transform)[:6], 'crs': str(src.crs)}
            if (grid['shape'] != expected['decoded_shape'] or grid['transform'] != expected['chip_transform']
                    or grid['crs'] != expected['native_crs'] or not expected['source_window_readback_equal']):
                raise ValueError(f'{name} native grid/readback differs from acquisition provenance')
            if metadata is not None and any(grid[k] != metadata[k] for k in grid):
                raise ValueError('source grids differ; resampling is not authorized')
            if src.count != 1 or src.dtypes != ('uint8',):
                raise ValueError('source must have one uint8 band')
            metadata = grid
            sources.append({'band': name, 'path': str(rel), 'sha256': digest,
                            'bytes': path.stat().st_size, 'nodata': src.nodata,
                            'compression': src.compression.value if src.compression else None})
            readers.append(src)
        metadata.update({'product': 'Hansen Global Forest Change 2025 v1.13',
                         'sources': sources,
                         'source_url': 'https://developers.google.com/earth-engine/datasets/catalog/UMD_hansen_global_forest_change_2025_v1_13',
                         'license': 'CC BY 4.0',
                         'band_names': list(BAND_NAMES)})
        yield readers, metadata


def load_source(root=None):
    with open_sources(root) as (readers, metadata):
        bands = np.stack([src.read(1) for src in readers])
        masks = np.stack([src.read_masks(1) != 0 for src in readers])
    return Dataset(bands, masks, metadata).validate()


def load_plots(root=None):
    root = Path(root) if root is not None else ROOT
    with (root / SAMPLE / CSV_NAME).open(newline='', encoding='utf-8-sig') as stream:
        rows = list(csv.DictReader(stream))
    features = json.loads((root / SAMPLE / GEOJSON_NAME).read_text())['features']
    by_id = {}
    for feature in features:
        plot_id = feature['properties']['ProductionPlace']
        if plot_id in by_id:
            raise ValueError(f'duplicate geometry ID: {plot_id}')
        by_id[plot_id] = feature
    row_ids = [r['a3_plot_id'] for r in rows]
    if len(row_ids) != len(set(row_ids)) or set(row_ids) != set(by_id):
        raise ValueError('supplier/geometry IDs must match one-to-one')
    return [{'plot_id': row['a3_plot_id'], 'geometry': by_id[row['a3_plot_id']]['geometry'],
             'supplier': row, 'geometry_properties': by_id[row['a3_plot_id']]['properties']}
            for row in rows]
