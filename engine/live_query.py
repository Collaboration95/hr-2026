"""Bounded, read-only temporary queries on a verified retained Hansen snapshot."""
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from time import perf_counter

import numpy as np
from shapely.geometry import shape

from .codecs import decode_store
from .export import differing_fields, evidence_cells
from .model import Dataset, PERIODS, QUERY_VERSION
from .proof import BOUNDARY_RULE, PARTIAL_RULE, VALID_LAND_RULE, validate_benchmark
from .query import evaluate
from .source import ROOT, canonical_bytes, load_plots, load_source, object_hash, sha256_file

LIMITS = {'max_body_bytes': 65536, 'max_vertices': 512, 'max_candidate_cells': 4096,
          'max_selected_cells': 4096, 'evidence_mode': 'all_selected_cells'}
LIVE_PERIODS = {key: [2000 + value[0], 2000 + value[1]] for key, value in PERIODS.items()}
IMPLEMENTATION_FILES = ('model.py', 'source.py', 'query.py', 'codecs.py', 'proof.py',
                        'export.py', 'live_query.py')
# Bind the modules imported by this process as well as the root used for input.
_IMPORTED_HASHES = {name: sha256_file(Path(__file__).parent / name) for name in IMPLEMENTATION_FILES}


class LiveError(ValueError):
    def __init__(self, status, code, message, request_id=None):
        super().__init__(message)
        self.status, self.code, self.message, self.request_id = status, code, message, request_id

    def envelope(self):
        return {'schema_version': 'plotline.live-error.v1', 'request_id': self.request_id,
                'error': {'code': self.code, 'message': self.message}}


def _no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def _no_constant(value):
    raise ValueError('nonfinite JSON constant')


def parse_request(body):
    """Parse the actual wire bytes; strict shape validation retains exact types."""
    if type(body) is not bytes:
        raise LiveError(400, 'INVALID_JSON', 'Request body must be UTF-8 JSON bytes.')
    if len(body) > LIMITS['max_body_bytes']:
        raise LiveError(413, 'BODY_TOO_LARGE', 'Request body exceeds 65536 bytes.')
    try:
        request = json.loads(body.decode('utf-8'), object_pairs_hook=_no_duplicates,
                             parse_constant=_no_constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise LiveError(400, 'INVALID_JSON', 'Request body must be valid UTF-8 JSON without duplicate keys or nonfinite constants.') from exc
    if type(request) is not dict:
        raise LiveError(400, 'INVALID_REQUEST', 'Request must be a JSON object.')
    request_id = request.get('request_id')
    if type(request_id) is not str or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', request_id):
        raise LiveError(400, 'INVALID_REQUEST', 'request_id must contain 1–64 ASCII letters, digits, underscores or hyphens.')
    if set(request) != {'schema_version', 'request_id', 'expected_snapshot_id', 'geometry'}:
        raise LiveError(400, 'INVALID_REQUEST', 'Request fields do not match the live request contract.', request_id)
    if request['schema_version'] != 'plotline.live-request.v1':
        raise LiveError(400, 'INVALID_REQUEST', 'Unsupported request schema.', request_id)
    snapshot_id = request['expected_snapshot_id']
    if type(snapshot_id) is not str or not re.fullmatch('[0-9a-f]{64}', snapshot_id):
        raise LiveError(400, 'INVALID_REQUEST', 'expected_snapshot_id must be a lowercase SHA-256 digest.', request_id)
    return request


def preflight_geometry(geometry, metadata, request_id=None):
    """Validate bounded geometry and reproduce the core's candidate rectangle.

    No grid arrays or native points are allocated here. Count the safety margin
    on the original affine, including outside-chip candidates; never clip.
    """
    def invalid(message):
        raise LiveError(422, 'INVALID_GEOMETRY', message, request_id)
    if type(geometry) is not dict or set(geometry) != {'type', 'coordinates'}:
        invalid('Use a bare geometry with exactly type and coordinates.')
    if geometry['type'] not in ('Polygon', 'MultiPolygon'):
        invalid('Only Polygon and MultiPolygon are supported.')
    polygons = [geometry['coordinates']] if geometry['type'] == 'Polygon' else geometry['coordinates']
    if type(polygons) is not list or not polygons:
        invalid('Geometry must contain nonempty polygons.')
    positions = []
    for rings in polygons:
        if type(rings) is not list or not rings:
            invalid('Each polygon requires an exterior ring.')
        for ring in rings:
            if type(ring) is not list or len(ring) < 4:
                invalid('Each ring requires at least four positions.')
            if len(positions) + len(ring) > LIMITS['max_vertices']:
                raise LiveError(422, 'QUERY_TOO_LARGE', 'Geometry exceeds 512 positions.', request_id)
            for point in ring:
                if type(point) is not list or len(point) != 2:
                    invalid('Positions require exactly two numeric coordinates.')
                try:
                    valid = all(type(v) in (int, float) and math.isfinite(v) for v in point)
                except OverflowError:
                    valid = False
                if not valid or not (-180 <= point[0] <= 180 and -90 <= point[1] <= 90):
                    invalid('Coordinates must be finite longitude [-180,180], latitude [-90,90]; booleans are not coordinates.')
                positions.append(point)
            if ring[0] != ring[-1]:
                invalid('Rings must be explicitly closed.')
    minx, maxx = min(p[0] for p in positions), max(p[0] for p in positions)
    miny, maxy = min(p[1] for p in positions), max(p[1] for p in positions)
    a, b, c, d, e, f = metadata['transform']
    if b != 0 or d != 0 or a <= 0 or e >= 0 or metadata['crs'] != 'EPSG:4326':
        raise LiveError(503, 'NOT_READY', 'Snapshot grid is unsupported.', request_id)
    extents = ((minx-c)/a-.5, (maxx-c)/a-.5, (maxy-f)/e-.5, (miny-f)/e-.5)
    if not all(math.isfinite(v) and abs(v) < 2**62 for v in extents):
        raise LiveError(422, 'QUERY_TOO_LARGE', 'Geometry exceeds the supported native lattice.', request_id)
    c0, c1 = math.floor(extents[0])-1, math.ceil(extents[1])+1
    r0, r1 = math.floor(extents[2])-1, math.ceil(extents[3])+1
    count = (r1-r0+1) * (c1-c0+1)
    if count > LIMITS['max_candidate_cells']:
        raise LiveError(422, 'QUERY_TOO_LARGE', 'Geometry exceeds 4096 candidate cells including the safety margin; use a smaller region.', request_id)
    try:
        polygon = shape(geometry)
        valid = not polygon.is_empty and polygon.is_valid
    except Exception as exc:
        raise LiveError(422, 'INVALID_GEOMETRY', 'Invalid polygon topology.', request_id) from exc
    if not valid:
        invalid('Geometry must have valid, nonempty polygon topology.')
    return {'row_start': r0, 'row_stop': r1+1, 'col_start': c0, 'col_stop': c1+1,
            'candidate_cell_count': count}


def _local(root, relative):
    if type(relative) is not str or Path(relative).is_absolute():
        raise ValueError('snapshot paths must be relative')
    path = root / relative
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('snapshot path escapes root')
    return path


def _file_state(root, benchmark):
    """Identity includes every file the retained proof checker consumes."""
    exp = benchmark['experiment_id']
    run = benchmark['registry']['run_id']
    if not re.fullmatch('exp-[0-9a-f]{64}', exp) or not re.fullmatch('run-[0-9a-f]{64}', run):
        raise ValueError('invalid retained identity')
    selection = benchmark['retained_selection']
    paths = set(benchmark['identity']['input_sha256'])
    paths.update('engine/' + name for name in benchmark['identity']['implementation_sha256'])
    paths.update('engine/' + name for name in IMPLEMENTATION_FILES)
    paths.update(('artifacts/benchmark-v1.json', 'artifacts/experiments/retained-choice.json',
                  f'artifacts/experiments/{exp}/identity.json', f'artifacts/experiments/{exp}/{run}.json',
                  f'artifacts/experiments/selections/choice-{object_hash(selection)}.json'))
    paths.update(item['path'] for item in benchmark['baseline']['storage']['files'])
    for candidate in benchmark['candidates']:
        if candidate.get('status') == 'measured':
            name = candidate['candidate']
            if not re.fullmatch('[a-z0-9_]+', name):
                raise ValueError('invalid candidate')
            paths.update(f'artifacts/stores/{exp}/{name}/{item["path"]}' for item in candidate['storage']['files'])
    return [{'path': name, 'bytes': _local(root, name).stat().st_size,
             'sha256': sha256_file(_local(root, name))} for name in sorted(paths)]


def _immutable_dataset(dataset):
    # Bytes-backed arrays cannot have WRITEABLE reenabled, unlike setflags alone.
    bands = np.frombuffer(dataset.bands.tobytes(), dtype=dataset.bands.dtype).reshape(dataset.bands.shape)
    masks = np.frombuffer(dataset.masks.tobytes(), dtype=dataset.masks.dtype).reshape(dataset.masks.shape)
    return Dataset(bands, masks, json.loads(canonical_bytes(dataset.metadata)))


@dataclass(frozen=True)
class LiveSnapshot:
    _source: Dataset
    _compact: Dataset
    _canonical: bytes

    @classmethod
    def load(cls, root=ROOT):
        """Verify current retained proof before/after full load; never remeasure."""
        root = Path(root)
        try:
            benchmark_bytes = (root / 'artifacts/benchmark-v1.json').read_bytes()
            benchmark = json.loads(benchmark_bytes)
            before = _file_state(root, benchmark)
            if sha256_file(root / 'artifacts/benchmark-v1.json') != hashlib.sha256(benchmark_bytes).hexdigest():
                raise ValueError('benchmark changed before load')
            code = {name: sha256_file(root / 'engine' / name) for name in IMPLEMENTATION_FILES}
            if code != _IMPORTED_HASHES:
                raise ValueError('loaded implementation differs from root')
            source, plots = load_source(root), load_plots(root)
            store = validate_benchmark(benchmark, source, plots, root=root)
            bands, masks, metadata = decode_store(store)
            compact = Dataset(bands, masks, metadata).validate()
            if (differing_fields(source.metadata, compact.metadata)
                    or not np.array_equal(source.bands, compact.bands)
                    or not np.array_equal(source.masks, compact.masks)):
                raise ValueError('full source/store raw, mask or metadata mismatch')
            validate_benchmark(benchmark, source, plots, store=store, root=root)
            after = _file_state(root, benchmark)
            if before != after:
                raise ValueError('snapshot files changed during load')
            chosen = benchmark['retained_selection']['smallest_encoded']
            descriptor = {
                'query_version': QUERY_VERSION, 'product': source.metadata['product'],
                'source_metadata_sha256': object_hash(source.metadata), 'sources': source.metadata['sources'],
                'grid': {key: source.metadata[key] for key in ('shape', 'crs', 'transform')},
                'retained': {'experiment_id': benchmark['experiment_id'], 'run_id': benchmark['registry']['run_id'],
                             'store_path': chosen['store_path'], 'candidate': chosen['candidate'],
                             'files': [entry for entry in before if entry['path'].startswith(chosen['store_path'] + '/')]},
                'query_implementation_sha256': code, 'verified_files': before,
                'full_raw_masks_equal': True,
            }
            return cls(_immutable_dataset(source), _immutable_dataset(compact), canonical_bytes(descriptor))
        except Exception as exc:
            raise LiveError(503, 'NOT_READY', 'Retained snapshot verification failed; restart after restoring verified inputs.') from exc

    @property
    def snapshot_id(self):
        return hashlib.sha256(self._canonical).hexdigest()

    def health(self):
        return {'schema_version': 'plotline.live-health.v1', 'status': 'ready',
                'snapshot_id': self.snapshot_id, 'snapshot': json.loads(self._canonical),
                'snapshot_canonical_json': self._canonical.decode('utf-8'), 'limits': dict(LIMITS),
                'periods': json.loads(canonical_bytes(LIVE_PERIODS)),
                'lifetime': 'immutable_loaded_snapshot_until_restart'}

    def query(self, request: dict, request_body: bytes) -> dict:
        start = perf_counter()
        parsed = parse_request(request_body)
        request_id = parsed['request_id']
        try:
            matches = not differing_fields(request, parsed)
        except (TypeError, ValueError, RecursionError):
            matches = False
        if not matches:
            raise LiveError(400, 'INVALID_REQUEST', 'Parsed request does not match the exact submitted body.', request_id)
        if parsed['expected_snapshot_id'] != self.snapshot_id:
            raise LiveError(409, 'SNAPSHOT_MISMATCH', 'Snapshot changed; fetch health and submit a new request.', request_id)
        geometry = parsed['geometry']
        preflight_geometry(geometry, self._source.metadata, request_id)
        t0 = perf_counter()
        source_result = evaluate(self._source, geometry)
        t1 = perf_counter()
        compact_result = evaluate(self._compact, geometry)
        t2 = perf_counter()
        if differing_fields(source_result, compact_result):
            raise LiveError(500, 'COMPARISON_MISMATCH', 'Source and compact results disagree; no agreement receipt was issued.', request_id)
        selected = source_result['selected_cell_count']
        if selected > LIMITS['max_selected_cells']:
            raise LiveError(422, 'QUERY_TOO_LARGE', 'Too many selected cells for complete evidence.', request_id)
        evidence_start = perf_counter()
        cells = evidence_cells(self._source, geometry)
        evidence = {'complete': True, 'selected_cell_count': selected,
                    'returned_cell_count': len(cells['features']), 'cells': cells}
        t3 = perf_counter()
        if evidence['returned_cell_count'] != selected:
            raise LiveError(500, 'INTERNAL_ERROR', 'Complete cell evidence could not be verified.', request_id)
        body_hash = hashlib.sha256(request_body).hexdigest()
        geometry_hash = object_hash(geometry)
        # Send the exact bytes used by each receipt digest. Browser clients can
        # hash UTF-8 strings without recreating Python float serialization.
        bound_bytes = {name: canonical_bytes(value) for name, value in (
            ('source_result', source_result), ('compact_result', compact_result), ('evidence', evidence))}
        payload = {'request_id': request_id, 'request_body_sha256': body_hash, 'snapshot_id': self.snapshot_id,
                   'query_version': QUERY_VERSION, 'geometry_sha256': geometry_hash,
                   **{name + '_sha256': hashlib.sha256(value).hexdigest() for name, value in bound_bytes.items()},
                   'boundary_rule': BOUNDARY_RULE,
                   'valid_land_rule': VALID_LAND_RULE, 'partial_support_rule': PARTIAL_RULE,
                   'periods': json.loads(canonical_bytes(LIVE_PERIODS))}
        receipt_bytes = canonical_bytes(payload)
        response = {'schema_version': 'plotline.live-query.v1', 'request_id': request_id,
                    'request_body_sha256': body_hash, 'snapshot_id': self.snapshot_id, 'query_version': QUERY_VERSION,
                    'region_kind': 'temporary_user_geometry', 'geometry': geometry, 'geometry_sha256': geometry_hash,
                    'source_result': source_result, 'compact_result': compact_result,
                    **{name + '_canonical_json': value.decode('utf-8') for name, value in bound_bytes.items()},
                    'comparison': {'equal': True, 'differing_fields': []},
                    'native_grid': {key: json.loads(canonical_bytes(self._source.metadata[key])) for key in ('shape', 'crs', 'transform')},
                    'evidence': evidence, 'receipt': {'payload': payload, 'canonical_json': receipt_bytes.decode('utf-8'),
                                                    'sha256': hashlib.sha256(receipt_bytes).hexdigest()},
                    'interpretation': 'Mapped observations for a temporary geometry on a frozen local snapshot; no supplier or legal finding.'}
        response['runtime'] = {'source_query_ms': (t1-t0)*1000, 'compact_query_ms': (t2-t1)*1000,
                               'evidence_ms': (t3-evidence_start)*1000, 'total_request_ms': (perf_counter()-start)*1000,
                               'scope': 'single_request_preloaded_arrays_no_network_or_UI', 'benchmark': False}
        return response
