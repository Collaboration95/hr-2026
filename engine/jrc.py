"""Separate native-grid JRC2020 v4 observations; never a legal determination."""
from dataclasses import dataclass
import argparse
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
import rasterio
from rasterio.windows import Window

from .query import select_cells
from .source import canonical_bytes, object_hash, sha256_file, load_plots

ROOT = Path(__file__).resolve().parents[1]
QUERY_VERSION = 'jrc2020-centers.v1'
SCHEMA = 'plotline.jrc-baseline.v1'
CHIP = 'data/experimental/jrc/JRC_GFC2020_V4_N10_E90_company-bbox.tif'
SOURCE = 'data/experimental/jrc/JRC_GFC2020_V4_N10_E90.tif'
PROVENANCE = 'data/experimental/jrc/provenance.json'
QML = 'data/experimental/lead/jrc-semantics/JRC_GFC2020_V4.qml'
XML = 'data/experimental/lead/jrc-semantics/JRC_GFC2020_V4.xml'
# Trusted local acquisition identities; never supplied by the artifact under test.
PINS = {
    CHIP: '3019c19bca064ac8f31747da856f40ce04146da6759c2f36dc30d0ff2e07e7c5',
    SOURCE: 'fbae885505a5ee7a481775401f27c23b1b8ef1e5451b69156a70c04aa42f38d7',
    PROVENANCE: 'c99d7780af8778be4c1ad7123c31fbee3b09401d3ff4d48e2eeece15ea434f7b',
    QML: 'd089a9d21a10537a13c77f206fd8ac844d364800b48580361893179d902080b0',
    XML: 'cdccfb393e306cf6775a2041263c09885a275a67b8098acde6536f06358a66b9',
}
QUERY_GRID = 'acquired JRC chip affine lattice; zero-based chip row/col; original centers before any window read'
LIMITATIONS = [
    'Mapped product classes are observations, not legal forest/compliance findings.',
    'Counts are native JRC cells, not hectares or whole-plot area; do not add/compare them as same-resolution Hansen counts.',
    'Reference year 2020 differs from version v4 publication year 2026; v3 remains unavailable.',
    'Pinned v4 XML has 2023 creation/publication and 2025 revision dates plus a v2 report DOI; these do not date the v4 release.',
    'Official v4 technical report was still expected in December 2026 at review on 2026-10-13.',
    'Source/compact equality proves representation preservation, not satellite-source accuracy.',
]


@dataclass
class JrcDataset:
    values: np.ndarray
    mask: np.ndarray
    metadata: dict

    def validate(self):
        if not isinstance(self.values, np.ndarray) or self.values.dtype != np.uint8 or self.values.ndim != 2:
            raise ValueError('JRC values must be uint8 [height,width]')
        if (not isinstance(self.mask, np.ndarray) or self.mask.dtype != np.bool_
                or self.mask.shape != self.values.shape):
            raise ValueError('JRC mask must be bool with the values shape')
        shape = self.metadata.get('shape') if type(self.metadata) is dict else None
        if (type(shape) is not list or len(shape) != 2 or any(type(v) is not int for v in shape)
                or min(self.values.shape) < 1 or shape != list(self.values.shape)):
            raise ValueError('JRC shape mismatch or empty grid')
        if np.any(self.values > 1):
            raise ValueError('JRC raw values must be 0 or 1, even under invalid masks')
        t = self.metadata.get('transform')
        try:
            finite = type(t) is list and len(t) == 6 and all(type(v) in (int, float) and math.isfinite(v) for v in t)
        except OverflowError:
            finite = False
        if (not finite
                or t[0] <= 0 or t[4] >= 0 or t[1] != 0 or t[3] != 0
                or self.metadata.get('crs') != 'EPSG:4326'):
            raise ValueError('JRC requires a finite north-up EPSG:4326 grid')
        return self


def file_record(relative, root=ROOT):
    path = Path(root) / relative
    return {'path': str(relative), 'bytes': path.stat().st_size, 'sha256': sha256_file(path)}


def load_jrc(root: Path | None = None) -> JrcDataset:
    root = ROOT if root is None else Path(root)
    records = {}
    for name in (CHIP, PROVENANCE, QML, XML):
        records[name] = file_record(name, root)
        if records[name]['sha256'] != PINS[name]:
            raise ValueError('JRC pinned input identity mismatch: ' + name)
    p = json.loads((root / PROVENANCE).read_text())
    if (p['version'] != 'v4' or p['source_sha256'] != PINS[SOURCE]
            or p['chip_sha256'] != PINS[CHIP] or p['chip_bytes'] != records[CHIP]['bytes']):
        raise ValueError('JRC provenance identity mismatch')
    labels = ET.fromstring((root / QML).read_bytes()).findall('.//colorrampshader/item')
    styles = {v.attrib['value']: {k: v.attrib[k] for k in ('label', 'alpha', 'color')} for v in labels}
    if {k: v['label'] for k, v in styles.items()} != {'0': 'Non-forest', '1': 'Forest'}:
        raise ValueError('JRC pinned QML class definitions mismatch')
    xml = ET.fromstring((root / XML).read_bytes())
    with rasterio.open(root / CHIP) as src:
        grid = {'shape': [src.height, src.width], 'transform': list(src.transform)[:6], 'crs': str(src.crs)}
        if (grid['shape'] != p['chip_dimensions_width_height'][::-1]
                or grid['transform'] != p['chip_transform'][:6] or grid['crs'] != p['chip_crs']
                or src.count != 1 or src.dtypes != ('uint8',) or src.nodata is not None):
            raise ValueError('JRC chip grid/type/nodata differs from pinned acquisition')
        values, mask = src.read(1), src.read_masks(1) != 0
        compression = src.compression.value
    grid.update({
        'product': p['product'], 'version': 'v4', 'reference_year': 2020,
        'publication_year': 2026, 'release_date': None,
        'source_http_last_modified': p['source_http_observation']['last_modified'],
        'query_grid': QUERY_GRID, 'classes': {k: v['label'] for k, v in styles.items()},
        'class_styles': styles, 'zero_is_valid_class': True, 'nodata': None,
        'class_label_source': {**records[QML], 'url': 'https://forobs.jrc.ec.europa.eu/GFC/download?output=qgis&type=symbology&version=v4'},
        'required_inputs': [records[n] for n in (CHIP, PROVENANCE, QML, XML)],
        'source': {'path': SOURCE, 'sha256': PINS[SOURCE], 'bytes': p['source_bytes'], 'url': p['source_url'],
                   'window_row_col_height_width': p['chip_window_source_row_col_height_width'], 'normal_runtime_required': False},
        'chip_sha256': PINS[CHIP], 'provenance_sha256': PINS[PROVENANCE], 'qml_sha256': PINS[QML],
        'xml_sha256': PINS[XML], 'compression': compression, 'citation': p['required_citation'],
        'xml_observations': {'title': xml.findtext('.//resTitle'), 'create_date': xml.findtext('.//createDate'),
                             'publication_date': xml.findtext('.//pubDate'), 'revision_date': xml.findtext('.//reviseDate'),
                             'linked_report': 'https://data.europa.eu/doi/10.2760/1975879'},
        'official_references': [p['provider_page'], p['official_band_catalog']],
        'limitations': LIMITATIONS,
    })
    return JrcDataset(values, mask, grid).validate()


def check_source_readback(root=ROOT, dataset=None):
    root = Path(root)
    ds = load_jrc(root) if dataset is None else dataset
    record = file_record(SOURCE, root)
    if record['sha256'] != PINS[SOURCE] or record['bytes'] != ds.metadata['source']['bytes']:
        raise ValueError('JRC full source hash/size mismatch')
    row, col, h, w = ds.metadata['source']['window_row_col_height_width']
    with rasterio.open(root / SOURCE) as src:
        win = Window(col, row, w, h)
        if list(src.window_transform(win))[:6] != ds.metadata['transform']:
            raise ValueError('JRC source window grid mismatch')
        values, mask = src.read(1, window=win), src.read_masks(1, window=win) != 0
    if not np.array_equal(values, ds.values) or not np.array_equal(mask, ds.mask):
        raise ValueError('JRC source window pixel/mask mismatch')
    return {'source': record, 'pixel_count': int(values.size), 'raw_values_equal': True, 'masks_equal': True,
            'window_row_col_height_width': [row, col, h, w], 'transform_equal': True}


def evaluate_jrc(dataset: JrcDataset, geometry: dict, missing_band=False) -> dict:
    if type(missing_band) is not bool:
        raise ValueError('missing_band must be bool')
    rows, cols = select_cells(dataset.metadata, geometry)
    h, w = dataset.metadata['shape']
    inside = (rows >= 0) & (rows < h) & (cols >= 0) & (cols < w)
    r, c = rows[inside], cols[inside]
    valid = dataset.mask[r, c] & (not missing_band)
    n, covered, count = len(rows), len(r), int(valid.sum())
    outside, invalid = n-covered, int((~valid).sum())
    unknown = n if missing_band else outside + invalid
    counts = {str(v): int((dataset.values[r[valid], c[valid]] == v).sum()) for v in (0, 1)} if count else None
    flag = (True if counts['1'] else False if unknown == 0 else None) if count else None
    reasons = []
    if not n: reasons.append('no_selected_cells')
    if outside: reasons.append('out_of_coverage')
    if invalid: reasons.append('band_mask_invalid')
    if n and not count: reasons.append('no_valid_cells')
    if missing_band: reasons.append('missing_band')
    return {'selected_cell_count': n, 'in_coverage_cell_count': covered, 'out_of_coverage_cell_count': outside,
            'valid_cell_count': count, 'unknown_cell_count': unknown, 'class_counts': counts,
            'mapped_forest_present': flag,
            'support': 'unavailable' if missing_band else 'none' if not count else 'partial' if unknown else 'complete',
            'unknown_reasons': reasons}


def evidence_jrc(dataset, geometry):
    rows, cols = select_cells(dataset.metadata, geometry)
    h, w = dataset.metadata['shape']
    return [{'row': int(r), 'col': int(c),
             'value': int(dataset.values[r, c]) if 0 <= r < h and 0 <= c < w else None,
             'valid': bool(dataset.mask[r, c]) if 0 <= r < h and 0 <= c < w else False}
            for r, c in zip(rows, cols)]


def export_jrc(*args, **kwargs):
    from .jrc_proof import export_jrc as export
    return export(*args, **kwargs)


def verify_jrc_artifact(*args, **kwargs):
    from .jrc_proof import verify_jrc_artifact as verify
    return verify(*args, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', type=Path)
    parser.add_argument('--measure', action='store_true', help='explicit new experiment; requires the optional full source tile')
    parser.add_argument('--output', type=Path, default=ROOT / 'artifacts/jrc-baseline-v1.json')
    args = parser.parse_args()
    if args.verify:
        if args.measure: parser.error('--verify and --measure are mutually exclusive')
        result = verify_jrc_artifact(args.verify)
        print(json.dumps(result, indent=2))
        raise SystemExit(0 if result['valid'] else 1)
    result = export_jrc(output=args.output, new_measurement=args.measure)
    print(json.dumps({'artifact': str(args.output), 'summary': result['summary'],
                      'storage_choice': result['benchmark']['overall_storage_choice']}, indent=2))


if __name__ == '__main__':
    main()
