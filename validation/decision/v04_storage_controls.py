"""Claim 4: storage accounting and a harder standard-format control.

(a) Recompute baselines from the files on disk and the store files' true byte sizes.
(b) Try smarter standard layouts than the project's controls: separate 1-bit/low-bit GeoTIFF planes
    (NBITS=1/2/3), sparse year layers, multi-band bit-plane files, PNG, and plain packbits + zstd/xz.
Prints sizes; writes validation/decision/out/v04.json. Single process, a few seconds.
"""
import io
import json
import lzma
import sys
import warnings
import zlib

import numpy as np
from compression import zstd
from rasterio.io import MemoryFile
from rasterio.transform import Affine

from _common import ART, OUT, ROOT, facts_to_codes, independent_facts, read_raw
from engine.decision_store import MAGIC, PREFIX, read_store

report = {}
# ---- (a) accounting --------------------------------------------------------------------------------------
stores = json.loads((ART / 'stores.json').read_text())
sizes = {}
for rel in ('data/public/hansen_treecover2000_sample.tif', 'data/public/hansen_lossyear_sample.tif',
            'data/public/hansen_datamask_sample.tif', 'data/experimental/jrc/JRC_GFC2020_V4_N10_E90_company-bbox.tif',
            'data/public/provenance.json', 'data/experimental/jrc/provenance.json',
            'data/experimental/lead/jrc-semantics/JRC_GFC2020_V4.qml', 'data/experimental/lead/jrc-semantics/JRC_GFC2020_V4.xml'):
    sizes[rel] = (ROOT / rel).stat().st_size
allt = sum(sizes[k] for k in list(sizes)[:4])
contract = sum(sizes[k] for k in list(sizes)[1:4])
report['baselines'] = {'recomputed_all_layers': allt, 'recorded': stores['baselines']['original_all_layers']['bytes'],
                       'recomputed_contract_inputs': contract, 'recorded_contract': stores['baselines']['original_contract_inputs']['bytes'],
                       'extra_files_the_original_pipeline_also_loads': {k: sizes[k] for k in list(sizes)[4:]},
                       'extra_total': sum(sizes[k] for k in list(sizes)[4:])}
for level, fn in (('eudr-screen.v1', 'screen.plds'), ('eudr-decision.v1', 'decision.plds')):
    data = (ART / fn).read_bytes()
    magic, ver, hl, crc = PREFIX.unpack_from(data)
    rec = stores['levels'][level]['store']
    report[f'store_{level}'] = {'on_disk': len(data), 'recorded_file_bytes': rec['file_bytes'],
                                'prefix': PREFIX.size, 'header': hl, 'payload': len(data) - PREFIX.size - hl,
                                'recorded_payload': rec['payload_bytes'],
                                'percent_smaller_vs_all_layers': round(100 * (1 - len(data) / allt), 3),
                                'percent_smaller_vs_contract_inputs': round(100 * (1 - len(data) / contract), 3),
                                'percent_smaller_vs_all_layers_plus_provenance_files': round(100 * (1 - len(data) / (allt + report['baselines']['extra_total'])), 3)}
    header = json.loads(data[PREFIX.size:PREFIX.size + hl])
    report[f'store_{level}']['header_keys'] = sorted(header)

# registered-plot sidecars (needed only for the registry/table paths)
report['sidecars'] = {'registry.bin': (ART / 'registry.bin').stat().st_size, 'table.json': (ART / 'table.json').stat().st_size,
                      'plan_estimate_for_table': '1-2 KB (docs/lab/decision-layer-plan.md, L4 row)'}

# ---- (b) harder controls ----------------------------------------------------------------------------------
raw = read_raw()
F = independent_facts(raw)
h, w = raw['lossyear']['shape']
transform = Affine(*raw['lossyear']['t'])
profile_base = dict(driver='GTiff', height=h, width=w, crs='EPSG:4326', transform=transform)


def tiff(planes, dtype='uint8', nbits=None, compress='ZSTD', predictor=None, tiled=False, interleave=None, level=22):
    planes = np.asarray(planes)
    if planes.ndim == 2:
        planes = planes[None]
    prof = dict(profile_base, count=planes.shape[0], dtype=dtype, compress=compress.lower())
    if compress == 'ZSTD':
        prof['zstd_level'] = level
    if compress == 'DEFLATE':
        prof['zlevel'] = 9
    if nbits:
        prof['nbits'] = nbits
    if predictor:
        prof['predictor'] = predictor
    if tiled:
        prof.update(tiled=True, blockxsize=256, blockysize=256)
    else:
        prof.update(tiled=False, blockysize=h)
    if interleave:
        prof['interleave'] = interleave
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        with MemoryFile() as mem:
            with mem.open(**prof) as dst:
                dst.write(planes)
            data = mem.read()
        with MemoryFile(data) as mem, mem.open() as src:
            ok = np.array_equal(src.read(), planes)
    assert ok
    return len(data)


def best_tiff(planes, **kw):
    best = None
    for compress in ('ZSTD', 'DEFLATE', 'LZW'):
        for predictor in (None, 2):
            for tiled in (False, True):
                for inter in (None,):
                    try:
                        n = tiff(planes, compress=compress, predictor=predictor, tiled=tiled, **kw)
                    except Exception:
                        continue
                    if best is None or n < best[0]:
                        best = (n, f'{compress} p={predictor} tiled={tiled}')
    return best


results = {}
for level in ('eudr-decision.v1', 'eudr-screen.v1'):
    codes = facts_to_codes(F, level)
    c = codes.astype(np.int16)
    land = c >= 2
    state = np.where(land, (c - 2) // 6, 0)
    year = np.where(land, (c - 2) % 6, 0)
    planes_bits = {'unknown': (c == 0), 'water': (c == 1), 'forest': (state == 1) & land, 'unknown_forest': (state == 2) & land}
    out = {}
    # 1. each bit plane as its own NBITS=1 GeoTIFF + year layer as uint8 / as 3-bit
    tot = 0
    detail = {}
    for name, p in planes_bits.items():
        if not p.any():
            detail[name] = 'empty (all-zero plane omitted, as the project does)'
            continue
        n, how = best_tiff(p.astype(np.uint8), nbits=1)
        detail[name] = (n, how)
        tot += n
    ny8 = best_tiff(year.astype(np.uint8))
    ny3 = best_tiff(year.astype(np.uint8), nbits=4)  # GDAL NBITS 3 is unsupported for some drivers; 4 is the next width
    out['A_separate_1bit_planes_plus_year_uint8'] = {'bit_planes': detail, 'bit_planes_total': tot, 'year_uint8': ny8,
                                                      'year_nbits4': ny3, 'total_with_uint8_year': tot + ny8[0],
                                                      'total_with_nbits4_year': tot + ny3[0]}
    # 2. year layer as 5 sparse 1-bit planes (one per year)
    yt = 0
    ydetail = {}
    for i in range(1, 6):
        p = (year == i)
        if not p.any():
            ydetail[2020 + i] = 0
            continue
        n, how = best_tiff(p.astype(np.uint8), nbits=1)
        ydetail[2020 + i] = (n, how)
        yt += n
    out['B_year_as_5_bitplanes'] = {'years': ydetail, 'total_years': yt, 'total_with_bit_planes': tot + yt}
    # 3. multi-band 1-bit file (all four planes in one GeoTIFF), plus year uint8 band file
    stack = np.stack([p.astype(np.uint8) for p in planes_bits.values()])
    keep = [i for i in range(4) if stack[i].any()]
    nmb = best_tiff(stack[keep], nbits=1)
    out['C_single_multiband_1bit_file'] = {'bands': keep, 'bytes': nmb, 'plus_year_uint8': nmb[0] + ny8[0]}
    # 4. recoded 'class' plane (unknown/water/nonforest/forest/unknown-forest, 3 bits) + sparse year file
    cls = np.zeros(c.shape, np.uint8)
    cls[c == 1] = 1
    cls[land & (state == 0)] = 2
    cls[land & (state == 1)] = 3
    cls[land & (state == 2)] = 4
    ncls = best_tiff(cls, nbits=4)
    ncls8 = best_tiff(cls)
    out['D_class_plane_plus_year_plane'] = {'class_nbits4': ncls, 'class_uint8': ncls8, 'year_uint8': ny8,
                                           'total_nbits4': ncls[0] + ny8[0], 'total_uint8': ncls8[0] + ny8[0]}
    # 5. non-GeoTIFF: PNG-like deflate on strips, plain row-major packbits + zstd22/xz for each plane (no georeferencing)
    rawplanes = 0
    for name, p in planes_bits.items():
        if p.any():
            pb = np.packbits(p.astype(np.uint8), axis=1).tobytes()
            rawplanes += min(len(zstd.compress(pb, level=22)), len(lzma.compress(pb, preset=9 | lzma.PRESET_EXTREME)))
    # sparse events COO (row delta, col, year) as bytes
    ev = np.argwhere(year > 0)
    flat = (ev[:, 0] * w + ev[:, 1]).astype(np.int64)
    gaps = np.diff(flat, prepend=-1)
    coo = b''.join(int(g).to_bytes(4, 'little') for g in gaps) + year[year > 0].astype(np.uint8).tobytes()
    coo_sz = min(len(zstd.compress(coo, level=22)), len(lzma.compress(coo, preset=9 | lzma.PRESET_EXTREME)))
    out['E_plain_rowmajor_packbits_plus_coo_events'] = {'bit_planes_rowmajor': rawplanes, 'events': int(len(ev)), 'coo_bytes': coo_sz,
                                                        'total_no_georef': rawplanes + coo_sz}
    out['project_store'] = {'file_bytes': stores['levels'][level]['store']['file_bytes'],
                            'payload_bytes': stores['levels'][level]['store']['payload_bytes'],
                            'project_best_control': stores['levels'][level]['best_control']}
    results[level] = out
report['controls'] = results
(OUT / 'v04.json').write_text(json.dumps(report, indent=1, default=str) + '\n')
print(json.dumps(report, indent=1, default=str))
