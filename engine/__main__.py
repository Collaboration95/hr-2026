"""Re-run one actual or custom plot locally, optionally against a compact store."""
import argparse
import json
from pathlib import Path
import sys
from .export import differing_fields
from .model import Dataset, QUERY_VERSION
from .query import evaluate
from .source import load_plots, load_source, object_hash


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument('--plot', help='exact supplied plot ID, for example P-0003')
    selection.add_argument('--geometry', type=Path, help='local Polygon/MultiPolygon GeoJSON geometry or Feature')
    parser.add_argument('--store', type=Path, help='compact store to compare against originals')
    parser.add_argument('--access', choices=('full', 'indexed'), default='full', help='full preload or original-grid indexed windows')
    args = parser.parse_args(argv)
    try:
        if args.plot:
            plots = {p['plot_id']: p for p in load_plots()}
            if args.plot not in plots:
                raise ValueError(f'unknown plot ID: {args.plot}')
            geometry = plots[args.plot]['geometry']
        else:
            geometry = json.loads(args.geometry.read_text())
            if geometry.get('type') == 'Feature':
                geometry = geometry['geometry']
        if args.access == 'indexed':
            from .indexed import SourceWindowReader, CompactWindowReader, evaluate_reader
            with SourceWindowReader() as reader:
                source_metadata = reader.metadata
                answer = evaluate_reader(reader, geometry)
        else:
            source = load_source()
            source_metadata = source.metadata
            answer = evaluate(source, geometry)
        result = {'query_version': QUERY_VERSION, 'plot_id': args.plot,
                  'geometry_sha256': object_hash(geometry),
                  'source_metadata_sha256': object_hash(source_metadata), 'source_result': answer,
                  'access_method': args.access,
                  'compact_result': None, 'equal': None, 'differing_fields': [],
                  'interpretation': 'Mapped forest-change observations; no legal/compliance conclusion.'}
        if args.store:
            if args.access == 'indexed':
                with CompactWindowReader(args.store) as reader:
                    if reader.metadata != source_metadata:
                        raise ValueError('compact store metadata does not match the current source')
                    result['compact_result'] = evaluate_reader(reader, geometry)
            else:
                from .codecs import decode_store
                bands, masks, metadata = decode_store(args.store)
                if metadata != source_metadata:
                    raise ValueError('compact store metadata does not match the current source')
                compact = Dataset(bands, masks, metadata).validate()
                result['compact_result'] = evaluate(compact, geometry)
            result['differing_fields'] = differing_fields(answer, result['compact_result'])
            result['equal'] = not result['differing_fields']
        print(json.dumps(result, indent=2, allow_nan=False))
        return 1 if result['equal'] is False else 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'error': type(exc).__name__, 'message': str(exc)}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
