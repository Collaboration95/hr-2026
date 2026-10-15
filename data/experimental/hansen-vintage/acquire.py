#!/usr/bin/env python3
"""Acquire only preregistered Hansen 2023 v1.11; never substitute a band."""
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import time
import urllib.request

import numpy as np
import rasterio
from rasterio.windows import Window, from_bounds

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RAW = HERE / 'raw'
BANDS = ('treecover2000', 'lossyear', 'datamask')
BASE = 'https://storage.googleapis.com/earthenginepartners-hansen/GFC-2023-v1.11/'
BUDGET = 500_000_000
START = time.monotonic()

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()

def log(event, **details):
    record = {'utc': now(), 'event': event, **details}
    with (HERE / 'chronology.jsonl').open('a') as f:
        f.write(json.dumps(record) + '\n')
    print(json.dumps(record), flush=True)

def request(url, method='GET'):
    return urllib.request.urlopen(urllib.request.Request(url, method=method,
        headers={'User-Agent': 'Plotline-bounded-source-vintage-study/1.0'}), timeout=45)

def main():
    prereg = json.loads((HERE / 'preregistration.json').read_text())
    assert prereg['historical_release'] == 'Hansen GFC 2023 v1.11'
    RAW.mkdir(exist_ok=True)
    manifest_path = HERE / 'acquisition.json'
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        assert manifest['status'] == 'complete'
        for item in manifest['layers']:
            for prefix in ('source', 'chip'):
                p = HERE / item[prefix + '_path']
                assert sha(p) == item[prefix + '_sha256']
        log('verified_existing_acquisition', manifest_sha256=sha(manifest_path))
        return
    downloaded = 0
    urls, headers = {}, {}
    try:
        # Verify official published URL lists before requesting any raster.
        for band in BANDS:
            list_url = BASE + band + '.txt'
            with request(list_url) as response:
                content = response.read(2_000_001)
                assert len(content) <= 2_000_000
                downloaded += len(content)
                (HERE / ('official-' + band + '-urls.txt')).write_bytes(content)
            matched = [u.strip() for u in content.decode().splitlines()
                       if u.strip().endswith(f'_{band}_10N_090E.tif')]
            assert len(matched) == 1, (band, matched)
            url = matched[0]
            assert url == BASE + f'Hansen_GFC-2023-v1.11_{band}_10N_090E.tif'
            urls[band] = url
            with request(url, 'HEAD') as response:
                headers[band] = dict(response.headers)
                assert response.status == 200
            log('official_archive_access_verified', band=band, url=url,
                size=int(headers[band]['Content-Length']), status=200)
        assert sum(int(h['Content-Length']) for h in headers.values()) + downloaded <= BUDGET
        sources = {}
        for band, url in urls.items():
            path = RAW / url.rsplit('/', 1)[-1]
            assert not path.exists(), 'Unexpected unmanifested cached tile'
            partial = path.with_suffix('.tif.part')
            expected = int(headers[band]['Content-Length'])
            log('download_started', band=band, expected_bytes=expected)
            with request(url) as response, partial.open('wb') as f:
                assert response.status == 200
                while chunk := response.read(1 << 20):
                    downloaded += len(chunk)
                    assert downloaded <= BUDGET, 'Total new download budget exceeded'
                    assert time.monotonic() - START < 600, 'Acquisition exceeded ten minutes'
                    f.write(chunk)
            assert partial.stat().st_size == expected, 'Incomplete tile'
            partial.rename(path)
            sources[band] = path
            log('download_completed', band=band, bytes=expected, sha256=sha(path))
        # Pixel inspection starts only after all three historical files arrived.
        log('historical_decode_started', all_three_source_files_acquired=True)
        current_prov = json.loads((ROOT / 'data/public/provenance.json').read_text())
        bbox = current_prov['plot_bounds_wgs84']
        layers, grids = [], []
        for band in BANDS:
            source = sources[band]
            chip = HERE / f'hansen_2023_v1_11_{band}_sample.tif'
            with rasterio.open(source) as src:
                assert src.count == 1 and src.dtypes == ('uint8',)
                assert str(src.crs) == 'EPSG:4326'
                floating = from_bounds(*bbox, transform=src.transform)
                col0, row0 = math.floor(floating.col_off), math.floor(floating.row_off)
                col1, row1 = math.ceil(floating.col_off + floating.width), math.ceil(floating.row_off + floating.height)
                win = Window(col0, row0, col1-col0, row1-row0)
                a, mask = src.read(1, window=win), src.read_masks(1, window=win)
                assert int(a.max()) <= {'treecover2000':100, 'lossyear':23, 'datamask':2}[band]
                profile = src.profile.copy()
                transform = src.window_transform(win)
                profile.update(width=a.shape[1], height=a.shape[0], transform=transform,
                               compress='deflate', tiled=True, blockxsize=256, blockysize=256)
                with rasterio.Env(GDAL_TIFF_INTERNAL_MASK=True):
                    with rasterio.open(chip, 'w', **profile) as dst:
                        dst.write(a, 1)
                        # Preserve validity even if the source contains an internal mask.
                        if not np.all(mask == 255):
                            dst.write_mask(mask)
                with rasterio.open(chip) as check:
                    assert np.array_equal(a, check.read(1))
                    assert np.array_equal(mask, check.read_masks(1))
                    assert check.transform == transform
                    bounds = list(check.bounds)
                    assert bounds[0] <= bbox[0] and bounds[1] <= bbox[1] and bounds[2] >= bbox[2] and bounds[3] >= bbox[3]
                grid = {'source_shape': [src.height, src.width], 'source_transform': list(src.transform)[:6],
                        'shape': list(a.shape), 'transform': list(transform)[:6], 'crs': str(src.crs),
                        'window_col_row_width_height': [col0,row0,col1-col0,row1-row0]}
                grids.append(grid)
                unique, counts = np.unique(a, return_counts=True)
                layers.append({'band':band, 'url':urls[band], 'http_headers':headers[band],
                    'source_path':str(source.relative_to(HERE)), 'source_bytes':source.stat().st_size,
                    'source_sha256':sha(source), 'chip_path':chip.name, 'chip_bytes':chip.stat().st_size,
                    'chip_sha256':sha(chip), 'grid':grid, 'bounds':bounds, 'nodata':src.nodata,
                    'source_block_shapes':src.block_shapes, 'source_mask_flags':[str(v) for v in src.mask_flag_enums[0]],
                    'source_window_raw_readback_equal':True, 'source_window_masks_readback_equal':True,
                    'mask_valid_cells':int((mask != 0).sum()), 'raw_value_counts':dict(zip(map(str,unique.tolist()),counts.tolist())),
                    'raw_array_sha256':hashlib.sha256(a.tobytes()).hexdigest(),
                    'mask_array_sha256':hashlib.sha256(mask.tobytes()).hexdigest()})
        assert all(g == grids[0] for g in grids)
        manifest = {'status':'complete', 'finished_at_utc':now(), 'preregistration_sha256':sha(HERE/'preregistration.json'),
            'product':'Hansen GFC 2023 v1.11', 'observation_end_year':2023, 'company_source_vintage':'unknown',
            'official_archive_page':BASE+'download.html',
            'official_catalog':'https://developers.google.com/earth-engine/datasets/catalog/UMD_hansen_global_forest_change_2023_v1_11',
            'license':'CC BY 4.0', 'license_url':'https://creativecommons.org/licenses/by/4.0/',
            'attribution':'Hansen/UMD/Google/USGS/NASA', 'citation_doi':'10.1126/science.1244693',
            'changes':'Native-grid bbox extraction and lossless recompression; no resampling or recoding.',
            'total_new_download_body_bytes':downloaded, 'all_three_historical_bands':True,
            'same_grid_across_historical_bands':True, 'bbox':bbox, 'layers':layers,
            'documentation_discrepancies':['Archive prose says lossyear 1–20 while naming 2001–2023; official catalog explicitly confirms 1–23.',
                'Nominal resolution wording differs; use measured native affine grid, never infer spacing from prose.']}
        manifest_path.write_text(json.dumps(manifest, indent=2)+'\n')
        log('acquisition_complete', total_new_download_body_bytes=downloaded)
    except Exception as exc:
        log('acquisition_blocked_or_partial', error=repr(exc), downloaded_bytes=downloaded)
        raise

if __name__ == '__main__':
    main()
