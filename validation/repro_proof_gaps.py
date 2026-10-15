"""Bounded repros for proof gates; writes only validation/repro-proof/ and report.

Exit 1 means an invalid evidence fixture was accepted. The fixtures are labelled
and kept outside canonical artifacts. No original source/store is modified.
"""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.codecs import encode_store
from engine.export import export
import engine.export as exporter
from engine.source import load_source, object_hash
from engine.verify import verify_artifact


def resign(artifact):
    for plot in artifact['plots']:
        receipt = plot['receipt']
        receipt['receipt_sha256'] = object_hash({k: v for k, v in receipt.items() if k != 'receipt_sha256'})
    artifact['content_sha256'] = object_hash({k: v for k, v in artifact.items() if k != 'content_sha256'})


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2)+'\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, default=ROOT/'validation/repro-proof')
    parser.add_argument('--report', type=Path, default=ROOT/'docs/lab/validator-proof-gaps.json')
    args = parser.parse_args()
    base = args.output_dir.resolve()
    base.mkdir(parents=True, exist_ok=True)
    actual = json.loads((ROOT/'artifacts/demo-v1.json').read_text())
    report = {'fixture_scope': 'deliberately invalid proof fixtures, no real observation claim', 'probes': []}
    def probe(label, fixture, expected):
        path = base/(label+'.json')
        resign(fixture)
        write(path, fixture)
        try:
            observed = verify_artifact(path)
        except (ValueError, OSError, KeyError, TypeError) as error:
            observed = {'valid': False, 'failures': [str(error)]}
        report['probes'].append({'label': label, 'expected': expected, 'actual': observed,
                                 'fixture': str(path.relative_to(ROOT))})
    benchmark = deepcopy(actual)
    benchmark['benchmark']['identity']['queries_sha256'] = '0'*64
    benchmark['benchmark']['identity']['source_metadata']['product'] = 'WRONG SOURCE VINTAGE — VALIDATOR FIXTURE'
    benchmark['benchmark']['baseline']['storage']['total_bytes'] = 1
    probe('wrong-benchmark', benchmark, 'valid=false: benchmark provenance/storage/registry binding differs')
    receipt = deepcopy(actual)
    for plot in receipt['plots']:
        plot['receipt']['query_version'] = 'wrong-query.v99'
        plot['receipt']['observed_periods'] = {'2021-2023': [2099, 2099]}
    receipt['summary']['selected_cell_count_sum'] = 1
    probe('wrong-receipt-period-summary', receipt, 'valid=false: executable query/period/summary claims differ')

    # A one-value, off-plot mutation preserves every 17-plot query while violating
    # the full source-pixel round-trip claim stored in each receipt.
    source = load_source()
    selected = {(f['properties']['row'], f['properties']['col']) for p in actual['plots'] for f in p['evidence']['features']}
    witness = next((r, c) for r in range(source.bands.shape[1]) for c in range(source.bands.shape[2]) if (r, c) not in selected)
    bands = source.bands.copy()
    r, c = witness
    old = int(bands[0, r, c])
    bands[0, r, c] = (old+1) % 101
    store = base/'one-wrong-pixel-store'
    encode_store(bands, source.masks, source.metadata, store, 'separate_zstd', chunk_size=256)
    files = [{'path': p.name, 'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(store.iterdir())]
    corrupted = deepcopy(actual)
    for plot in corrupted['plots']:
        plot['receipt']['compact_store'] = {'path': str(store.relative_to(ROOT)), 'files': files,
                                            'raw_bands_equal': True, 'band_masks_equal': True}
    probe('one-wrong-offplot-pixel', corrupted, 'valid=false: full raw-value fidelity false even though cohort query matches')
    report['mutated_native_cell'] = {'row': r, 'col': c, 'band': 'treecover2000', 'original': old, 'changed': int(bands[0, r, c]), 'in_any_plot': False}
    try:
        export(store, output=base/'must-not-export.json')
        export_result = 'accepted'
    except ValueError as error:
        export_result = str(error)
    report['normal_export_one_wrong_pixel'] = export_result

    # Test the upstream export gate separately with a wrong benchmark in an
    # owned fixture root. Source functions still read the unmodified real inputs.
    fixture_root = base/'export-root'
    (fixture_root/'artifacts').mkdir(parents=True, exist_ok=True)
    if not (fixture_root/'data').exists():
        (fixture_root/'data').symlink_to(ROOT/'data', target_is_directory=True)
    write(fixture_root/'artifacts/benchmark-v1.json', benchmark['benchmark'])
    saved_root = exporter.ROOT
    try:
        exporter.ROOT = fixture_root
        result = exporter.export(ROOT/actual['plots'][0]['receipt']['compact_store']['path'], fixture_root/'artifacts/demo-v1.json')
        report['wrong_benchmark_export'] = {'accepted': True, 'embedded_source_product': result['benchmark']['identity']['source_metadata']['product'], 'embedded_source_total_bytes': result['benchmark']['baseline']['storage']['total_bytes']}
    except (ValueError, OSError, KeyError) as error:
        report['wrong_benchmark_export'] = {'accepted': False, 'error': str(error)}
    finally:
        exporter.ROOT = saved_root
    write(args.report, report)
    print(json.dumps(report, indent=2))
    return int(any(p['actual']['valid'] for p in report['probes']) or report['wrong_benchmark_export']['accepted'])


if __name__ == '__main__':
    sys.exit(main())
