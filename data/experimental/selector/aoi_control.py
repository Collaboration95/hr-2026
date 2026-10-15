#!/usr/bin/env python3
"""Separate, seen-AOI GeoTIFF audit. This is NOT an additional holdout cohort."""
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window

import study


def main():
    before = study.guard()
    provenance = study.read(study.ROOT / 'data/public/provenance.json')
    selection_path = study.ROOT / 'artifacts/experiments/retained-choice.json'
    selection_hash = study.filehash(selection_path)
    choice = study.read(selection_path)['smallest_encoded']
    baseline_path = study.ROOT / choice['store_path']
    baseline_files = study.files(baseline_path)
    rb, rm, meta = study.codecs.decode_store(baseline_path)
    bands, masks = [], []
    for layer in provenance['layers']:
        col, row, width, height = layer['window']
        source = study.ROOT / 'data/public/raw' / Path(layer['url']).name
        if study.filehash(source) != layer['source_tile_sha256']:
            raise ValueError('source hash differs')
        with rasterio.open(source) as ds:
            win = Window(col, row, width, height)
            bands.append(ds.read(1, window=win))
            masks.append(ds.read_masks(1, window=win) != 0)
    b, m = np.stack(bands), np.stack(masks)
    if not (np.array_equal(b, rb) and np.array_equal(m, rm)):
        raise ValueError('raw tile window differs from retained source store')
    if not m.all():
        raise ValueError('this AOI audit requires verified implicit all-valid masks')
    results = []
    shape = b.shape[1:]
    query = (240, 272, 480, 512)
    for level in (3, 19):
        for predictor in (1, 2):
            for side in (256, 512, 1024):
                cid = f'gtiff_l{level}_p{predictor}_{side}'
                target = study.HERE / 'aoi-controls' / cid
                target.mkdir(parents=True, exist_ok=True)
                def encode():
                    with rasterio.open(target / 'bands.tif', 'w', driver='GTiff',
                                       height=shape[0], width=shape[1], count=3, dtype='uint8',
                                       crs=meta['crs'], transform=rasterio.Affine(*meta['transform']),
                                       tiled=True, blockxsize=side, blockysize=side,
                                       compress='ZSTD', zstd_level=level, predictor=predictor,
                                       interleave='band', photometric='MINISBLACK', num_threads=1) as ds:
                        ds.write(b)
                        for i, name in enumerate(study.NAMES, 1):
                            ds.set_band_description(i, name)
                    study.write(target / 'metadata.json', meta)
                _, encoding = study.timed(encode)
                (db, dm, dmeta), decoding = study.timed(lambda: study.tiff_read(target))
                if not (np.array_equal(db, b) and np.array_equal(dm, m) and dmeta == meta):
                    raise AssertionError('AOI control raw/mask/metadata roundtrip failed')
                samples = []
                for _ in range(5):
                    (wb, wm, _), timing = study.timed(lambda: study.tiff_read(target, query))
                    if not (np.array_equal(wb, b[:, query[0]:query[1], query[2]:query[3]]) and
                            np.array_equal(wm, m[:, query[0]:query[1], query[2]:query[3]])):
                        raise AssertionError('AOI control window mismatch')
                    samples.append(timing)
                listing = study.files(target)
                results.append({'config': cid, 'level': level, 'predictor': predictor, 'chunk': side,
                                'files': listing, 'decode_required_bytes': sum(f['bytes'] for f in listing),
                                'encode': encoding, 'full_decode': decoding,
                                'window_samples': samples, 'roundtrip': True, 'window_exact': True})
    # Match levels/chunks/metadata directly, remeasure preprocessing here rather
    # than borrowing the earlier canonical benchmark's timings.
    engine_results = []
    for candidate in ('separate_zstd', 'separate_zstd_l19'):
        for side in (256, 512, 1024):
            cid = f'{candidate}_{side}'
            target = study.HERE / 'aoi-controls' / cid
            _, encoding = study.timed(lambda: study.codecs.encode_store(b, m, meta, target, candidate, side))
            (db, dm, dmeta), decoding = study.timed(lambda: study.codecs.decode_store(target))
            if not (np.array_equal(db, b) and np.array_equal(dm, m) and dmeta == meta):
                raise AssertionError('AOI engine control roundtrip failed')
            samples = []
            for _ in range(5):
                (wb, wm, _), timing = study.timed(lambda: study.codecs.read_window(target, *query))
                if not (np.array_equal(wb, b[:, query[0]:query[1], query[2]:query[3]]) and
                        np.array_equal(wm, m[:, query[0]:query[1], query[2]:query[3]])):
                    raise AssertionError('AOI engine window mismatch')
                samples.append(timing)
            listing = study.files(target)
            engine_results.append({'config': cid, 'level': study.codecs.CANDIDATE_LEVELS[candidate],
                                   'chunk': side, 'files': listing,
                                   'decode_required_bytes': sum(f['bytes'] for f in listing),
                                   'encode': encoding, 'full_decode': decoding, 'window_samples': samples,
                                   'roundtrip': True, 'window_exact': True})
    smallest = min(results, key=lambda r: r['decode_required_bytes'])
    # Symmetric review evidence: original acquisition manifest retained for both.
    common = (study.ROOT / 'data/public/provenance.json').stat().st_size
    baseline_bytes = sum(f['bytes'] for f in study.files(baseline_path))
    out = {'completed_utc': study.now(), 'study_type': 'seen-AOI audit, not generalization',
           'source': {'tile': provenance['tile'], 'window': [row, col, height, width],
                      'raw_bands_sha256': study.digest(b.tobytes()), 'raw_masks_sha256': study.digest(m.tobytes())},
           'metadata_sha256': study.digest(study.canonical(meta)), 'metadata_bytes': len(study.canonical(meta)),
           'baseline': {'store_path': choice['store_path'], 'files': study.files(baseline_path),
                        'decode_required_bytes': baseline_bytes,
                        'with_common_provenance_bytes': baseline_bytes+common},
           'best_control': smallest,
           'best_control_with_common_provenance_bytes': smallest['decode_required_bytes']+common,
           'delta_control_minus_retained_bytes': smallest['decode_required_bytes']-baseline_bytes,
           'percent_control_smaller_than_retained': (1-smallest['decode_required_bytes']/baseline_bytes)*100,
           'common_provenance_bytes': common, 'measurements': results,
           'matching_engine_controls': engine_results, 'guard': before,
           'script_sha256': study.filehash(Path(__file__)),
           'retained_choice_sha256_readonly': selection_hash,
           'limitations': ['single seen AOI; settings selected by audit minima, not heldout learning',
                           'GeoTIFF has no per-stream SHA checks in timed reads; masks are implicit true only after all-valid verification',
                           'one encode/full-decode sample; five warm-OS window samples; no polygon or cold-process claims',
                           'no canonical benchmark/store/retention change; engine lead must review and rerun its proof protocol']}
    if (study.guard() != before or study.filehash(selection_path) != selection_hash
            or study.files(baseline_path) != baseline_files):
        raise ValueError('read-only baseline/implementation changed during audit')
    old = study.HERE / 'aoi-control-results.json'
    if old.exists():
        archive = study.HERE / ('aoi-control-results-prior-' + study.filehash(old) + '.json')
        if not archive.exists():
            archive.write_bytes(old.read_bytes())
    study.write(study.HERE / 'aoi-control-results.json', out)
    print(json.dumps({'best': smallest['config'], 'control_required_bytes': smallest['decode_required_bytes'],
                      'retained_required_bytes': baseline_bytes,
                      'control_minus_retained_bytes': out['delta_control_minus_retained_bytes'],
                      'encode_ms': smallest['encode']['wall_ms']}))


if __name__ == '__main__':
    main()
