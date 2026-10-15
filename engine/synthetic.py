"""Small explicitly synthetic examples for unknown-state inspection, not real metrics."""
import numpy as np
from .export import atomic_json, evidence_cells
from .model import Dataset, QUERY_VERSION
from .query import evaluate
from .source import ROOT


def rectangle(west, south, east, north):
    return {'type': 'Polygon', 'coordinates': [[[west, north], [east, north], [east, south], [west, south], [west, north]]]}


def export_synthetic():
    bands = np.zeros((3, 4, 4), dtype=np.uint8)
    bands[0] = 80
    bands[2] = 1
    masks = np.ones_like(bands, dtype=bool)
    metadata = {'shape': [4, 4], 'transform': [1, 0, 0, 0, -1, 4], 'crs': 'EPSG:4326',
                'product': 'SYNTHETIC TEST GRID — not Hansen observations'}
    cases = []
    definitions = [('tiny_no_centers', rectangle(.01, .01, .1, .1), None, ()),
                   ('partial_absence_unknown', rectangle(-1, 0, 1, 2), None, ()),
                   ('partial_positive_known', rectangle(-1, 0, 1, 2), 'loss', ()),
                   ('water_only', rectangle(0, 0, 2, 2), 'water', ()),
                   ('nodata', rectangle(0, 0, 2, 2), 'nodata', ()),
                   ('missing_loss_band', rectangle(0, 0, 2, 2), None, ('lossyear',))]
    for name, geometry, mutation, missing in definitions:
        b = bands.copy()
        if mutation == 'loss':
            b[1, 2, 0] = 24
        elif mutation == 'water':
            b[2] = 2
        elif mutation == 'nodata':
            b[2, 2, 0] = 0
        dataset = Dataset(b, masks, metadata).validate()
        cases.append({'case_id': name, 'synthetic': True, 'geometry': geometry,
                      'missing_bands': list(missing), 'result': evaluate(dataset, geometry, missing),
                      'evidence': evidence_cells(dataset, geometry)})
    artifact = {'schema_version': 'plotline.synthetic.v1', 'query_version': QUERY_VERSION,
                'synthetic': True, 'dataset': metadata, 'cases': cases,
                'limitations': ['Artificial test cases. Never include in the 17-plot real cohort or source fidelity metrics.',
                                'Missing-band case retains stored fixture cells only to show what was intentionally disabled.']}
    atomic_json(ROOT / 'artifacts/synthetic-v1.json', artifact)
    return artifact


if __name__ == '__main__':
    result = export_synthetic()
    for case in result['cases']:
        print(case['case_id'], case['result']['support'], case['result']['periods'])
