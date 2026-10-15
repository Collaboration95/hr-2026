"""Layer analysis, whole-tile scale run and cost estimate for the decision layers.

Three independent jobs, all reading the pinned originals and reusing the pinned
semantics in engine/decision.py (derive_screen_codes, project_decision,
nested_offsets) rather than re-implementing them:

--analysis  Attribute bytes to each attribute on the AOI chip, tie each to the
            contract question that needs it and to the EUDR definition, and
            measure how much the JRC 3x3 -> centre-cell simplification matters.
--scale     Stream one real 10x10 degree tile (Hansen 2025 v1.13 x3 bands plus
            the JRC GFC2020 v4 tile) in strips of Hansen rows, derive the screen
            and decision codes with derive_screen_codes, and sum compressed bytes.
--read-timing  Single-process, uncontended wall time to read the four tile files in strips.
--cost      List-price storage and re-check compute estimate built on --scale. Per-plot
            microseconds come from artifacts/decision/benchmark-v1.json (so they cannot
            drift) and the tile read time from --read-timing.

Outputs go to artifacts/decision/. Compressed sizes are one consistent yardstick
(zstd level 19 of the raw row-major planes), not a proposed container format.
Outputs are mapped observations, never legal findings.
"""
import argparse
import concurrent.futures as futures
import json
import lzma
import math
import multiprocessing
import multiprocessing.util
import os
import platform
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import MaskFlags
from rasterio.windows import Window
from compression import zstd

from .decision import (CODE_COUNT, CUTOFF_LOSSYEAR, DECISION_VERSION, FOREST_STATES, LAND, POST_YEARS,
                       UNKNOWN, WATER, derive_screen_codes, nested_offsets,
                       project_decision, summarize_selection)
from .decision_store import MAX_CELLS, MAX_DIMENSION
from .jrc import JrcDataset, PINS, load_jrc
from .model import Dataset
from .query import select_cells
from .source import load_plots, load_source, sha256_file

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/decision'
ANALYSIS_PATH = OUT / 'layer-analysis-v1.json'
SCALE_PATH = OUT / 'scale-v1.json'
COST_PATH = OUT / 'cost-v1.json'
BENCHMARK_PATH = OUT / 'benchmark-v1.json'
READ_TIMING_PATH = OUT / 'tile-read-v1.json'
AS_OF = '2026-10-15'
ZSTD_LEVEL = 19
XZ_PRESET = 9 | lzma.PRESET_EXTREME
HANSEN_RAW = 'data/public/raw/Hansen_GFC-2025-v1.13_{}_10N_090E.tif'
HANSEN_BANDS = ('treecover2000', 'lossyear', 'datamask')
JRC_TILE = 'data/experimental/jrc/JRC_GFC2020_V4_N10_E90.tif'
JRC_CHIP_WINDOW = (17017, 105269, 1809, 3695)  # provenance: row, col, height, width in the JRC tile
CODE_LABELS = (['unknown', 'water'] +
               [f'land/{state}/{"no post-2020 loss" if i == 0 else f"loss {2020 + i}"}'
                for state in FOREST_STATES for i in range(6)])
CONTRACT_QUESTIONS = {
    'Q1': 'forest at the 31 Dec 2020 cut-off',
    'Q2': 'deforestation since the cut-off (mapped loss on 2020 forest)',
    'Q3': "supplier's own Hansen 2021-23 check (and the 2024-25 continuation)",
}


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def _flat(array):
    return np.ascontiguousarray(array).reshape(-1)


def z19(array):
    return len(zstd.compress(_flat(array), level=ZSTD_LEVEL))


def xz(array):
    return len(lzma.compress(_flat(array), format=lzma.FORMAT_XZ, preset=XZ_PRESET))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def percent(part, whole):
    return round(100.0 * part / whole, 4) if whole else None


def decompose(codes):
    """(post-year index, forest state) for land codes; -1 elsewhere. Mirrors land_code()."""
    c = codes.astype(np.int16)
    land = c >= LAND
    return np.where(land, (c - LAND) % 6, -1), np.where(land, (c - LAND) // 6, -1)


def sample_forest_plane(hansen_metadata, jrc):
    """Forest state 0/1/2 (nonforest/forest/unknown) on the Hansen grid via the pinned nesting.

    Same indexing as derive_screen_codes, but it covers every Hansen cell (also
    water and no-data) so the plane can be sized as a layer of its own.
    """
    height, width = hansen_metadata['shape']
    k, row_offset, col_offset = nested_offsets(hansen_metadata, jrc.metadata)
    jrows = k * np.arange(height) + row_offset
    jcols = k * np.arange(width) + col_offset
    rows_ok = (jrows >= 0) & (jrows < jrc.values.shape[0])
    cols_ok = (jcols >= 0) & (jcols < jrc.values.shape[1])
    plane = np.full((height, width), 2, np.uint8)
    sampled = np.ix_(jrows[rows_ok], jcols[cols_ok])
    plane[np.ix_(rows_ok, cols_ok)] = np.where(jrc.mask[sampled], jrc.values[sampled], 2)
    return plane


def presampled_jrc(hansen_metadata, forest_plane):
    """A JRC dataset already on the Hansen grid (ratio 1, offset 0); state 2 becomes invalid."""
    values = np.where(forest_plane == 2, 0, forest_plane).astype(np.uint8)
    return JrcDataset(values, forest_plane != 2,
                      {'shape': list(forest_plane.shape), 'transform': list(hansen_metadata['transform']),
                       'crs': hansen_metadata['crs']})


def strip_codes(bands, masks, hansen_metadata, jrc_values, jrc_mask, jrc_metadata):
    """Pinned screen codes and the sampled forest plane for one strip of Hansen rows.

    The strip transforms must keep the exact nesting (nested_offsets refuses otherwise).
    """
    hansen = Dataset(bands, masks, hansen_metadata)
    jrc = JrcDataset(jrc_values, jrc_mask, jrc_metadata)
    return derive_screen_codes(hansen, jrc), sample_forest_plane(hansen_metadata, jrc)


def derived_planes(bands, codes, forest_plane):
    """Every separable plane used in the attribution table, keyed by name."""
    loss = bands[1]
    decision = project_decision(codes)
    rotation = np.where((codes > LAND) & (codes < LAND + 6), codes - LAND, 0).astype(np.uint8)
    return {
        'treecover2000_exact': bands[0],
        'lossyear_full': loss,
        'lossyear_2001_2020': np.where(loss <= CUTOFF_LOSSYEAR, loss, 0).astype(np.uint8),
        'lossyear_2021_2025': (np.maximum(loss, CUTOFF_LOSSYEAR) - CUTOFF_LOSSYEAR).astype(np.uint8),
        'datamask': bands[2],
        'jrc_sampled_at_hansen_centres': forest_plane,
        'post2020_loss_on_jrc_nonforest': rotation,
        'screen_codes_L1': codes,
        'decision_codes_L2': decision,
    }


def cell_hectares(lat_degrees, step_degrees):
    """Approximate WGS84 cell area in hectares for a square-degree cell at a latitude."""
    phi = math.radians(lat_degrees)
    metres_lat = 111132.954 - 559.822 * math.cos(2 * phi) + 1.175 * math.cos(4 * phi)
    metres_lon = 111412.84 * math.cos(phi) - 93.5 * math.cos(3 * phi) + 0.118 * math.cos(5 * phi)
    return metres_lat * step_degrees * metres_lon * step_degrees / 10000.0


# ---------------------------------------------------------------------------
# 1. layer analysis on the AOI chip
# ---------------------------------------------------------------------------

PLANE_DOC = {
    'treecover2000_exact': dict(
        label='treecover2000, exact canopy %', needed_for=[], verdict='drop',
        kept_in=['L0'],
        why='JRC 2020 supplies forest at the cut-off, so no contract question reads the exact percentage. '
            'Only if Hansen alone had to supply the baseline would a single canopy >10% bit be needed.',
        grounding='EUDR canopy cover >10% is a threshold, not a percentage. Hansen treecover2000 measures canopy '
                  'of vegetation taller than 5 m in 2000, so it would be the layer for that test; JRC embeds it.'),
    'lossyear_full': dict(
        label='lossyear, full (2001-2025)', needed_for=['Q2', 'Q3'], verdict='split',
        kept_in=['L0'],
        why='Full plane for reference; the pre-2021 and post-2020 parts are separated below.',
        grounding='Loss years after 2020 fall after the cut-off; years up to 2020 fall before it.'),
    'lossyear_2001_2020': dict(
        label='lossyear detail 2001-2020', needed_for=[], verdict='drop',
        kept_in=['L0'],
        why='Loss before the cut-off does not change forest at the cut-off once JRC 2020 is the baseline. '
            'It would matter only for a Hansen-only baseline (canopy >10% and no loss up to 2020).',
        grounding='Cut-off 31 Dec 2020: events before it are not deforestation under the regulation.'),
    'lossyear_2021_2025': dict(
        label='lossyear 2021-2025', needed_for=['Q2', 'Q3'], verdict='keep',
        kept_in=['L0', 'L1', 'L2'],
        why='The only attribute that dates change after the cut-off.',
        grounding='Deforestation after 31 Dec 2020. Annual resolution only: loss during 2020 cannot be told '
                  'from loss on 31 Dec 2020.'),
    'datamask': dict(
        label='datamask (land / water / no data)', needed_for=['Q1', 'Q2', 'Q3'], verdict='keep',
        kept_in=['L0', 'L1', 'L2'],
        why='Separates land from water from no data, so an unmapped cell stays "unknown", never "no loss".',
        grounding='Only land can carry forest or deforestation; unknown must not read as compliant.'),
    'jrc_native_9m': dict(
        label='JRC 2020 forest, native ~9 m', needed_for=['Q1'], verdict='reduce',
        kept_in=['L0'],
        why='The contract reads one JRC cell per Hansen cell (the centre of the nested 3x3 block); '
            '8 of every 9 JRC cells are never read.',
        grounding='JRC states its forest class follows the EUDR definition and excludes rubber, oil palm and '
                  'other agricultural plantations; this is its own claim, its technical report is pending.'),
    'jrc_sampled_at_hansen_centres': dict(
        label='JRC 2020 forest sampled at Hansen centres', needed_for=['Q1', 'Q2'], verdict='keep',
        kept_in=['L1', 'L2'],
        why='Forest at the cut-off on the grid the decision is evaluated on.',
        grounding='Forest in 2020 is the baseline against which later loss counts as deforestation.'),
    'post2020_loss_on_jrc_nonforest': dict(
        label='post-2020 loss on JRC non-forest land', needed_for=['Q3'], verdict='L1 only',
        kept_in=['L1'],
        why='Rotation harvests on land that was not forest in 2020. Needed only to reproduce the supplier\'s '
            'Hansen-only check; EUDR deforestation needs forest at the cut-off, so L2 forgets it.',
        grounding='Loss on land that was predominantly agricultural (e.g. rubber, oil palm) in 2020 is not '
                  'conversion of forest.'),
    'screen_codes_L1': dict(
        label='screen codes (eudr-screen.v1)', needed_for=['Q1', 'Q2', 'Q3'], verdict='ship',
        kept_in=['L1'], why='One uint8 code per Hansen cell answers all three questions.',
        grounding='Combines the 2020 forest baseline with annual loss after the cut-off.'),
    'decision_codes_L2': dict(
        label='decision codes (eudr-decision.v1)', needed_for=['Q1', 'Q2'], verdict='ship',
        kept_in=['L2'], why='Forest at the cut-off and deforestation since, nothing else.',
        grounding='The two regulatory questions only; the supplier-specific check is dropped.'),
}

EUDR_DEFINITION = [
    {'element': 'forest: land spanning more than 0.5 ha',
     'captured': 'no',
     'note': 'No layer or step here applies a contiguity or minimum-area test. The unit is one cell '
             '({hansen_ha:.3f} ha Hansen, {jrc_ha:.4f} ha JRC at the chip latitude); 0.5 ha is about '
             '{hansen_cells:.1f} Hansen cells or {jrc_cells:.0f} JRC cells. JRC says its map follows the '
             'definition; that is unverified here.'},
    {'element': 'trees higher than 5 m',
     'captured': 'partly',
     'note': 'Hansen treecover2000 is canopy closure of vegetation taller than 5 m (dropped from L1/L2). '
             'JRC states the same threshold for its class. The decision layers carry no height information.'},
    {'element': 'canopy cover above 10%',
     'captured': 'partly',
     'note': 'Hansen treecover2000 > 10 would test it directly (a one-bit plane). The pipeline instead relies on '
             'the JRC class, so the threshold is applied only inside JRC, not by this code.'},
    {'element': 'or trees able to reach those thresholds in situ',
     'captured': 'no',
     'note': 'Young, recently cleared or regrowing stands are not distinguishable in a single-date map; '
             'Hansen gain is not used.'},
    {'element': 'excluding land predominantly under agricultural or urban use (agricultural plantations such as rubber and oil palm)',
     'captured': 'only through JRC',
     'note': 'JRC states it excludes plantations of relevant commodities other than wood. Hansen treats rubber '
             'and oil palm as tree cover, which is why Hansen loss alone fires on rotation harvests.'},
    {'element': 'cut-off 31 December 2020',
     'captured': 'at year resolution',
     'note': 'Hansen lossyear 21+ is after the cut-off; JRC is a 2020 reference year. Neither dates events '
             'within a year.'},
    {'element': 'deforestation = conversion of forest to agricultural use',
     'captured': 'proxy',
     'note': 'The count is mapped tree-cover loss on mapped 2020 forest. Hansen loss includes fire, logging and '
             'natural disturbance and says nothing about what the land becomes next.'},
    {'element': 'forest degradation, legality, protected areas',
     'captured': 'no',
     'note': 'Out of scope for these layers.'},
]


def block_forest(hansen_metadata, jrc):
    """Forest count and validity over the exactly nested k x k JRC block of every Hansen cell."""
    height, width = hansen_metadata['shape']
    k, row_offset, col_offset = nested_offsets(hansen_metadata, jrc.metadata)
    half = k // 2
    jrows = k * np.arange(height) + row_offset
    jcols = k * np.arange(width) + col_offset
    rows_ok = (jrows - half >= 0) & (jrows + half < jrc.values.shape[0])
    cols_ok = (jcols - half >= 0) & (jcols + half < jrc.values.shape[1])
    count = np.zeros((height, width), np.uint8)
    valid = np.zeros((height, width), np.uint8)
    inside = np.ix_(rows_ok, cols_ok)
    for dr in range(-half, half + 1):
        for dc in range(-half, half + 1):
            at = np.ix_(jrows[rows_ok] + dr, jcols[cols_ok] + dc)
            ok = jrc.mask[at]
            count[inside] += np.where(ok, jrc.values[at], 0).astype(np.uint8)
            valid[inside] += ok.astype(np.uint8)
    return count, valid == k * k, k


def variant_summary(codes, universe):
    post, state = decompose(codes)
    land = state >= 0
    in_u = land & universe
    deforested = in_u & (state == 1) & (post > 0)
    return {'land_cells': int(in_u.sum()),
            'forest_cells': int((in_u & (state == 1)).sum()),
            'nonforest_cells': int((in_u & (state == 0)).sum()),
            'unknown_forest_cells': int((in_u & (state == 2)).sum()),
            'forest_share_of_land_percent': percent(int((in_u & (state == 1)).sum()), int(in_u.sum())),
            'deforested_cells': int(deforested.sum()),
            'deforested_by_year': {str(y): int((deforested & (post == i + 1)).sum())
                                   for i, y in enumerate(POST_YEARS)}}


def aggregation_sensitivity(hansen, jrc, plots, screen_codes):
    """Centre cell (pinned) vs any-forest vs majority over the nested 3x3 JRC block."""
    meta = hansen.metadata
    count, full_valid, k = block_forest(meta, jrc)
    centre_plane = sample_forest_plane(meta, jrc)
    majority_min = (k * k) // 2 + 1
    planes = {
        'centre_cell': np.where(full_valid, centre_plane, 2).astype(np.uint8),
        'any_forest_in_block': np.where(full_valid, (count >= 1).astype(np.uint8), 2),
        'majority_forest_in_block': np.where(full_valid, (count >= majority_min).astype(np.uint8), 2),
    }
    codes = {name: derive_screen_codes(hansen, presampled_jrc(meta, plane)) for name, plane in planes.items()}
    # The pre-sampled trick must reproduce the pinned centre path wherever the block is fully inside.
    state_b = decompose(screen_codes)[1]
    trick_equal = bool(np.array_equal(codes['centre_cell'][full_valid], screen_codes[full_valid]))

    land_all = state_b >= 0
    universe = full_valid & land_all
    regional = {name: variant_summary(c, full_valid) for name, c in codes.items()}
    regional['pinned_L1_centre_all_cells'] = variant_summary(screen_codes, np.ones_like(full_valid))
    centre_state = decompose(codes['centre_cell'])[1]
    flips = {}
    for name in ('any_forest_in_block', 'majority_forest_in_block'):
        other = decompose(codes[name])[1]
        flips[name] = {'nonforest_to_forest_cells': int((universe & (centre_state == 0) & (other == 1)).sum()),
                       'forest_to_nonforest_cells': int((universe & (centre_state == 1) & (other == 0)).sum())}
    block_hist = np.bincount(count[universe], minlength=k * k + 1)
    loss_cells = universe & (decompose(codes['centre_cell'])[0] > 0)
    loss_block_hist = np.bincount(count[loss_cells], minlength=k * k + 1)

    per_plot, changes, plot_cells_unknown = [], [], 0
    for plot in plots:
        rows, cols = select_cells(meta, plot['geometry'])
        h, w = meta['shape']
        inside_rows = (rows >= 0) & (rows < h) & (cols >= 0) & (cols < w)
        plot_cells_unknown += int((~full_valid[rows[inside_rows], cols[inside_rows]]).sum())
        record = {'plot_id': plot['plot_id'], 'selected_cells': int(rows.size)}
        outputs = {}
        for name, c in codes.items():
            out = summarize_selection(c, rows, cols, DECISION_VERSION)
            outputs[name] = out
            record[name] = {
                'forest_cells': out['forest_2020']['cell_counts']['forest'] if out['forest_2020']['cell_counts'] else None,
                'forest_2020_present': out['forest_2020']['present'],
                'deforested_cells': out['deforestation_after_2020']['cell_count'],
                'deforestation_present': out['deforestation_after_2020']['present']}
        pinned = summarize_selection(screen_codes, rows, cols, DECISION_VERSION)
        record['pinned_L1_centre_matches_centre_variant'] = (
            pinned['forest_2020'] == outputs['centre_cell']['forest_2020']
            and pinned['deforestation_after_2020'] == outputs['centre_cell']['deforestation_after_2020'])
        for name in ('any_forest_in_block', 'majority_forest_in_block'):
            for field, key in (('forest_2020_present', 'forest_2020_present'),
                               ('deforestation_present', 'deforestation_present')):
                a, b = record['centre_cell'][field], record[name][key]
                if a != b:
                    changes.append({'plot_id': plot['plot_id'], 'variant': name, 'field': field,
                                    'centre_cell': a, 'variant_value': b})
        per_plot.append(record)
    plot_cell_changes = [
        {'plot_id': r['plot_id'], 'variant': name,
         'forest_cells_centre': r['centre_cell']['forest_cells'], 'forest_cells_variant': r[name]['forest_cells'],
         'deforested_cells_centre': r['centre_cell']['deforested_cells'],
         'deforested_cells_variant': r[name]['deforested_cells']}
        for r in per_plot for name in ('any_forest_in_block', 'majority_forest_in_block')
        if (r['centre_cell']['forest_cells'], r['centre_cell']['deforested_cells'])
        != (r[name]['forest_cells'], r[name]['deforested_cells'])]
    return {
        'rule': 'JRC read at the Hansen cell centre = middle cell of each exactly nested 3x3 block '
                '(pinned; engine.decision.nested_offsets). Variants read the whole block.',
        'variants': {'centre_cell': 'forest iff the middle JRC cell is forest (the shipped rule)',
                     'any_forest_in_block': 'forest iff at least 1 of the 9 JRC cells is forest',
                     'majority_forest_in_block': f'forest iff at least {majority_min} of the 9 JRC cells are forest'},
        'universe': {'rule': 'Hansen cells whose whole 3x3 JRC block lies inside the JRC chip; the other '
                             'cells (chip edge) are unknown in all block variants and excluded from the totals',
                     'hansen_cells': int(full_valid.size), 'cells_in_universe': int(full_valid.sum()),
                     'plot_cells_outside_universe': plot_cells_unknown},
        'pre_sampled_trick_equals_pinned_centre_path': trick_equal,
        'region': regional,
        'cell_flips_vs_centre': flips,
        'block_forest_count_histogram_land_cells': [int(v) for v in block_hist],
        'block_forest_count_histogram_post2020_loss_cells': [int(v) for v in loss_block_hist],
        'plots': per_plot,
        'plot_decision_changes': changes,
        'plot_cell_count_changes': plot_cell_changes,
        'plot_decisions_changed': bool(changes),
    }


def analyse_layers(root=ROOT):
    root = Path(root)
    hansen = load_source(root)
    jrc = load_jrc(root)
    plots = load_plots(root)
    meta = hansen.metadata
    h, w = meta['shape']
    k, row_offset, col_offset = nested_offsets(meta, jrc.metadata)
    codes = derive_screen_codes(hansen, jrc)
    decision = project_decision(codes)
    forest_plane = sample_forest_plane(meta, jrc)
    trick_codes = derive_screen_codes(hansen, presampled_jrc(meta, forest_plane))
    planes = derived_planes(hansen.bands, codes, forest_plane)
    planes['jrc_native_9m'] = jrc.values

    files = {s['band']: s['bytes'] for s in meta['sources']}
    jrc_chip_bytes = jrc.metadata['required_inputs'][0]['bytes']
    file_bytes = {'treecover2000_exact': files['treecover2000'], 'lossyear_full': files['lossyear'],
                  'datamask': files['datamask'], 'jrc_native_9m': jrc_chip_bytes}
    order = ['treecover2000_exact', 'lossyear_full', 'lossyear_2001_2020', 'lossyear_2021_2025', 'datamask',
             'jrc_native_9m', 'jrc_sampled_at_hansen_centres', 'post2020_loss_on_jrc_nonforest',
             'screen_codes_L1', 'decision_codes_L2']
    table = []
    for name in order:
        plane = planes[name]
        doc = PLANE_DOC[name]
        z = z19(plane)
        table.append({
            'plane': name, 'label': doc['label'], 'shape': list(plane.shape), 'cells': int(plane.size),
            'raw_bytes': int(plane.size), 'zstd19_bytes': z, 'xz_bytes': xz(plane),
            'zstd19_bits_per_cell': round(8.0 * z / plane.size, 4),
            'geotiff_file_bytes': file_bytes.get(name),
            'needed_for': [{'id': q, 'question': CONTRACT_QUESTIONS[q]} for q in doc['needed_for']],
            'needed_by_no_contract_question': not doc['needed_for'],
            'verdict': doc['verdict'], 'kept_in': doc['kept_in'],
            'reason': doc['why'], 'eudr_grounding': doc['grounding']})
    by = {r['plane']: r for r in table}
    originals = ('treecover2000_exact', 'lossyear_full', 'datamask', 'jrc_native_9m')
    totals = {
        'original_geotiff_bytes_hansen3': sum(files.values()),
        'original_geotiff_bytes_hansen3_plus_jrc': sum(files.values()) + jrc_chip_bytes,
        'original_layers_zstd19_bytes_hansen3_plus_jrc': sum(by[n]['zstd19_bytes'] for n in originals),
        'original_layers_zstd19_bytes_hansen3': sum(by[n]['zstd19_bytes'] for n in originals[:3]),
        'screen_L1_zstd19_bytes': by['screen_codes_L1']['zstd19_bytes'],
        'decision_L2_zstd19_bytes': by['decision_codes_L2']['zstd19_bytes'],
        'retained_v1_lossless_store_bytes_cited_by_plan': 535012,
    }
    plain = totals['original_layers_zstd19_bytes_hansen3_plus_jrc']
    totals['L1_vs_original_geotiff_percent_smaller'] = round(
        100 * (1 - totals['screen_L1_zstd19_bytes'] / totals['original_geotiff_bytes_hansen3_plus_jrc']), 2)
    totals['L2_vs_original_geotiff_percent_smaller'] = round(
        100 * (1 - totals['decision_L2_zstd19_bytes'] / totals['original_geotiff_bytes_hansen3_plus_jrc']), 2)
    totals['L1_vs_zstd19_yardstick_percent_smaller'] = round(100 * (1 - totals['screen_L1_zstd19_bytes'] / plain), 2)
    totals['L2_vs_zstd19_yardstick_percent_smaller'] = round(100 * (1 - totals['decision_L2_zstd19_bytes'] / plain), 2)
    totals['share_of_hansen3_zstd19_bytes'] = {
        n: round(100 * by[n]['zstd19_bytes'] / totals['original_layers_zstd19_bytes_hansen3'], 2) for n in originals[:3]}

    post, state = decompose(codes)
    land = state >= 0
    n_land = int(land.sum())
    loss = hansen.bands[1]
    post_loss = land & (post > 0)
    tc = hansen.bands[0]
    hansen_proxy_forest = land & (tc > 10) & ((loss == 0) | (loss > CUTOFF_LOSSYEAR))
    lat_mid = meta['transform'][5] + meta['transform'][4] * h / 2
    hansen_ha = cell_hectares(lat_mid, meta['transform'][0])
    jrc_ha = cell_hectares(lat_mid, jrc.metadata['transform'][0])
    region = {
        'hansen_cells': h * w, 'land_cells': n_land, 'water_cells': int((codes == WATER).sum()),
        'unknown_cells': int((codes == UNKNOWN).sum()),
        'land_cells_with_any_hansen_loss': int((land & (loss > 0)).sum()),
        'land_cells_with_any_hansen_loss_percent': percent(int((land & (loss > 0)).sum()), n_land),
        'post2020_loss_cells': int(post_loss.sum()),
        'post2020_loss_percent_of_land': percent(int(post_loss.sum()), n_land),
        'post2020_loss_on_jrc_forest_cells_deforested': int((post_loss & (state == 1)).sum()),
        'post2020_loss_on_jrc_nonforest_cells': int((post_loss & (state == 0)).sum()),
        'post2020_loss_on_unknown_forest_state_cells': int((post_loss & (state == 2)).sum()),
        'deforested_share_of_post2020_loss_percent': percent(int((post_loss & (state == 1)).sum()), int(post_loss.sum())),
        'deforested_by_year': {str(y): int((post_loss & (state == 1) & (post == i + 1)).sum())
                               for i, y in enumerate(POST_YEARS)},
        'post2020_loss_by_year_all_land': {str(y): int((land & (post == i + 1)).sum()) for i, y in enumerate(POST_YEARS)},
        'jrc_native_forest_share_percent': percent(int((jrc.values == 1).sum()), int(jrc.values.size)),
        'jrc_forest_cells_at_hansen_centres_on_land': int((land & (state == 1)).sum()),
        'jrc_forest_share_of_land_percent': percent(int((land & (state == 1)).sum()), n_land),
        'land_cells_with_unknown_forest_state': int((land & (state == 2)).sum()),
        'unknown_forest_state_note': 'JRC chip is the company bbox chip and is slightly smaller than the Hansen '
                                     'chip; the edge cells have no JRC value and stay unknown',
        'hansen_only_proxy_forest_2020': {
            'rule': 'land, treecover2000 > 10, no loss up to 2020 (no plantation exclusion; a proxy, not EUDR forest)',
            'cells': int(hansen_proxy_forest.sum()),
            'share_of_land_percent': percent(int(hansen_proxy_forest.sum()), n_land),
            'post2020_loss_cells_on_proxy_forest': int((hansen_proxy_forest & (post > 0)).sum()),
            'overlap_with_jrc_forest_cells': int((hansen_proxy_forest & (state == 1)).sum())},
        'cell_area_hectares_at_chip_centre': {'hansen': round(hansen_ha, 4), 'jrc': round(jrc_ha, 5),
                                              'half_hectare_in_hansen_cells': round(0.5 / hansen_ha, 2),
                                              'half_hectare_in_jrc_cells': round(0.5 / jrc_ha, 1)},
        'forest_state_by_code_histogram': {CODE_LABELS[i]: int(v) for i, v in enumerate(np.bincount(codes.ravel(), minlength=CODE_COUNT))},
    }
    definition = [dict(item, note=item['note'].format(
        hansen_ha=hansen_ha, jrc_ha=jrc_ha, hansen_cells=0.5 / hansen_ha, jrc_cells=0.5 / jrc_ha)) for item in EUDR_DEFINITION]
    return {
        'schema': 'plotline.decision-layer-analysis.v1',
        'as_of': AS_OF,
        'inputs': {'hansen_chip': {s['band']: {'bytes': s['bytes'], 'sha256': s['sha256']} for s in meta['sources']},
                   'jrc_chip': {'bytes': jrc_chip_bytes, 'sha256': jrc.metadata['chip_sha256']},
                   'hansen_shape': [h, w], 'jrc_shape': list(jrc.values.shape),
                   'nesting': {'ratio': k, 'row_offset': row_offset, 'col_offset': col_offset,
                               'note': 'Hansen centre (r, c) is the middle of JRC cell (3r+row_offset, 3c+col_offset)'}},
        'yardstick': f'zstd level {ZSTD_LEVEL} and xz preset 9e of the raw row-major uint8 plane (whole plane, '
                     'no chunking, no header); not a container format. geotiff_file_bytes are the source files.',
        'contract_questions': CONTRACT_QUESTIONS,
        'attribution': table,
        'totals': totals,
        'sampled_centre_trick_equals_pinned_codes': bool(np.array_equal(trick_codes, codes)),
        'L2_equals_projection_of_L1': bool(np.array_equal(decision, project_decision(codes))),
        'region_facts': region,
        'eudr_definition_coverage': definition,
        'eudr_sources': 'Forest, cut-off and plantation wording follows the JRC GFC2020 v4 metadata pinned in the repo '
                        '(data/experimental/lead/jrc-semantics/JRC_GFC2020_V4.xml), which restates Regulation (EU) '
                        '2023/1115; verify against the regulation text before quoting. Hansen thresholds are from '
                        'the Hansen et al. 2013 product description.',
        'aggregation_sensitivity': aggregation_sensitivity(hansen, jrc, plots, codes),
        'limitations': [
            'Sizes are of this 744,732-cell chip only. Whole-tile numbers are in scale-v1.json.',
            'Marginal byte costs of separable planes are not additive: compressing a plane together with another '
            'would share structure.',
            'Counts are mapped cells under the centre rule, not hectares and not a legal finding.',
        ],
    }


# ---------------------------------------------------------------------------
# 2. whole-tile scale run
# ---------------------------------------------------------------------------

_STATE = {}


def tile_paths(root=ROOT):
    root = Path(root)
    return [root / HANSEN_RAW.format(name) for name in HANSEN_BANDS], root / JRC_TILE


def _valid_mask(src, window):
    if MaskFlags.all_valid in src.mask_flag_enums[0]:
        return np.broadcast_to(True, (int(window.height), int(window.width)))
    return src.read_masks(1, window=window) != 0


def _close_worker():
    for reader in _STATE.pop('hansen', []) + [_STATE.pop('jrc', None)]:
        if reader is not None:
            reader.close()


def _init_worker(root):
    hansen_paths, jrc_path = tile_paths(root)
    _STATE['hansen'] = [rasterio.open(p) for p in hansen_paths]
    _STATE['jrc'] = rasterio.open(jrc_path)
    # close the GDAL handles before interpreter teardown (otherwise workers print sys.excepthook noise)
    multiprocessing.util.Finalize(None, _close_worker, exitpriority=10)


def _grid(src, window):
    return {'shape': [int(window.height), int(window.width)],
            'transform': list(src.window_transform(window))[:6], 'crs': str(src.crs)}


def read_strip(hansen_readers, jrc_reader, r0, nrows, k=3):
    """Read Hansen rows [r0, r0+nrows) and the k times larger JRC window; return arrays and grids."""
    width = hansen_readers[0].width
    hw = Window(0, r0, width, nrows)
    jw = Window(0, k * r0, jrc_reader.width, k * nrows)
    bands = np.stack([r.read(1, window=hw) for r in hansen_readers])
    masks = np.stack([_valid_mask(r, hw) for r in hansen_readers])
    jvalues = jrc_reader.read(1, window=jw)
    return (bands, masks, _grid(hansen_readers[0], hw), jvalues, _valid_mask(jrc_reader, jw), _grid(jrc_reader, jw))


def process_strip(task):
    r0, nrows, do_xz, do_decode, aoi = task
    hansen, jrc_reader = _STATE['hansen'], _STATE['jrc']
    t = time.perf_counter()
    bands, masks, hmeta, jvalues, jmask, jmeta = read_strip(hansen, jrc_reader, r0, nrows)
    read_s = time.perf_counter() - t

    t = time.perf_counter()
    k, row_offset, col_offset = nested_offsets(hmeta, jmeta)
    codes, forest_plane = strip_codes(bands, masks, hmeta, jvalues, jmask, jmeta)
    # self-check: the sampled plane, fed back as a ratio-1 JRC grid, reproduces the pinned codes exactly
    presampled_equal = bool(np.array_equal(
        derive_screen_codes(Dataset(bands, masks, hmeta), presampled_jrc(hmeta, forest_plane)), codes))
    planes = derived_planes(bands, codes, forest_plane)
    derive_s = time.perf_counter() - t

    land = codes >= LAND
    post, state = decompose(codes)
    jrc_hist = np.bincount(jvalues.reshape(-1), minlength=256)
    sizes = {}
    frames = {}
    t = time.perf_counter()
    for name, plane in planes.items():
        frames[name] = zstd.compress(_flat(plane), level=ZSTD_LEVEL)
        sizes[name] = len(frames[name])
    sizes['jrc_native_9m'] = z19(jvalues)
    zstd_s = time.perf_counter() - t

    xz_sizes, xz_s = None, 0.0
    if do_xz:
        t = time.perf_counter()
        xz_sizes = {name: xz(planes[name]) for name in
                    ('treecover2000_exact', 'lossyear_full', 'datamask', 'screen_codes_L1', 'decision_codes_L2')}
        xz_s = time.perf_counter() - t

    decode_s = None
    if do_decode:
        decode_s = {}
        for name in ('treecover2000_exact', 'lossyear_full', 'datamask', 'screen_codes_L1', 'decision_codes_L2'):
            t = time.perf_counter()
            zstd.decompress(frames[name])
            decode_s[name] = time.perf_counter() - t

    cutout = None
    if aoi is not None:
        a0, a1, c0, c1 = aoi  # absolute Hansen rows and columns of the AOI chip
        lo, hi = max(a0, r0), min(a1, r0 + nrows)
        if lo < hi:
            cutout = {'row0': lo, 'rows': hi - lo, 'cols': c1 - c0,
                      'data': codes[lo - r0:hi - r0, c0:c1].tolist()}

    return {
        'r0': r0, 'rows': nrows, 'offsets': [k, row_offset, col_offset],
        'presampled_equal': presampled_equal,
        'max_values': [int(b.max()) for b in bands],
        'code_hist': np.bincount(codes.reshape(-1), minlength=CODE_COUNT).tolist(),
        'datamask_hist': np.bincount(bands[2].reshape(-1), minlength=3).tolist(),
        'land_lossyear_hist': np.bincount(bands[1][land], minlength=26).tolist(),
        'land_treecover_gt10': int((bands[0][land] > 10).sum()),
        'land_treecover_hist': np.bincount(bands[0][land], minlength=101).tolist(),
        'jrc_native_hist': jrc_hist[:2].tolist(), 'jrc_native_other_values': int(jrc_hist[2:].sum()),
        'sampled_state_hist_all_cells': np.bincount(forest_plane.reshape(-1), minlength=3).tolist(),
        'sizes': sizes, 'xz_sizes': xz_sizes,
        'seconds': {'read': read_s, 'derive': derive_s, 'zstd': zstd_s, 'xz': xz_s},
        'decode_seconds': decode_s, 'aoi': cutout,
        'raw_cells': int(codes.size),
    }


def tile_geometry(root=ROOT):
    """Verify the tile grids, hash the files and prove the exact nesting for the whole tile."""
    hansen_paths, jrc_path = tile_paths(root)
    out = {'files': {}, 'hansen': None, 'jrc': None}
    metas = []
    for path in hansen_paths + [jrc_path]:
        with rasterio.open(path) as src:
            meta = {'shape': [src.height, src.width], 'transform': list(src.transform)[:6], 'crs': str(src.crs),
                    'dtype': src.dtypes[0], 'nodata': src.nodata, 'count': src.count,
                    'mask_all_valid': MaskFlags.all_valid in src.mask_flag_enums[0],
                    'compression': src.compression.value if src.compression else None,
                    'block_shape': list(src.block_shapes[0]),
                    'bounds': [src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top]}
        out['files'][path.name] = {'bytes': path.stat().st_size, 'sha256': sha256_file(path), **meta}
        metas.append(meta)
    hansen_metas, jrc_meta = metas[:3], metas[3]
    if any(m['shape'] != hansen_metas[0]['shape'] or m['transform'] != hansen_metas[0]['transform']
           for m in hansen_metas):
        raise ValueError('Hansen tile bands differ in grid')
    if not all(m['mask_all_valid'] and m['nodata'] is None for m in metas):
        raise ValueError('tile has nodata or masks; the all-valid fast path does not apply')
    pinned = out['files'][jrc_path.name]['sha256'] == PINS['data/experimental/jrc/JRC_GFC2020_V4_N10_E90.tif']
    k, row_offset, col_offset = nested_offsets(hansen_metas[0], jrc_meta)
    h, w = hansen_metas[0]['shape']
    out['hansen'], out['jrc'] = hansen_metas[0], jrc_meta
    out['jrc_source_matches_pinned_sha256'] = pinned
    out['nesting'] = {
        'ratio': k, 'row_offset': row_offset, 'col_offset': col_offset,
        'same_bounds': hansen_metas[0]['bounds'] == jrc_meta['bounds'],
        'jrc_shape_is_ratio_times_hansen_shape': jrc_meta['shape'] == [k * h, k * w],
        'all_centres_inside_jrc': bool(row_offset >= 0 and k * (h - 1) + row_offset < jrc_meta['shape'][0]
                                       and col_offset >= 0 and k * (w - 1) + col_offset < jrc_meta['shape'][1]),
        'note': 'Hansen centre (r, c) is the middle of JRC cell (3r+row_offset, 3c+col_offset)'}
    return out


def locate_chip(root, tile):
    """Where the AOI chip sits in the tile, from transforms, and whether its pixels match the tile."""
    hansen = load_source(root)
    jrc = load_jrc(root)
    ta, _, tc, _, te, tf = tile['hansen']['transform']
    a, _, c, _, e, f = hansen.metadata['transform']
    col0, row0 = (c - tc) / ta, (f - tf) / te
    if abs(col0 - round(col0)) > 1e-6 or abs(row0 - round(row0)) > 1e-6:
        raise ValueError('chip is not aligned to the tile lattice')
    col0, row0 = round(col0), round(row0)
    h, w = hansen.metadata['shape']
    hansen_paths, jrc_path = tile_paths(root)
    equal = {}
    for i, name in enumerate(HANSEN_BANDS):
        with rasterio.open(hansen_paths[i]) as src:
            equal[name] = bool(np.array_equal(src.read(1, window=Window(col0, row0, w, h)), hansen.bands[i]))
    jta, _, jtc, _, jte, jtf = tile['jrc']['transform']
    ja, _, jc, _, je, jf = jrc.metadata['transform']
    jcol0, jrow0 = round((jc - jtc) / jta), round((jf - jtf) / jte)
    jh, jw = jrc.metadata['shape']
    with rasterio.open(jrc_path) as src:
        equal['jrc'] = bool(np.array_equal(src.read(1, window=Window(jcol0, jrow0, jw, jh)), jrc.values))
    return {'hansen_window_row_col_height_width': [row0, col0, h, w],
            'jrc_window_row_col_height_width': [jrow0, jcol0, jh, jw],
            'jrc_window_matches_provenance': [jrow0, jcol0, jh, jw] == list(JRC_CHIP_WINDOW),
            'chip_pixels_equal_tile_window': equal}, hansen, jrc, (row0, col0)


def check_aoi(cutouts, hansen, jrc, chip_origin):
    """Strip-pipeline codes over the AOI window vs derive_screen_codes on the chips."""
    row0, col0 = chip_origin
    h, w = hansen.metadata['shape']
    tile_codes = np.full((h, w), 255, np.uint8)
    for cut in cutouts:
        r = cut['row0'] - row0
        tile_codes[r:r + cut['rows']] = np.array(cut['data'], np.uint8)
    chip_codes = derive_screen_codes(hansen, jrc)
    k, row_offset, col_offset = nested_offsets(hansen.metadata, jrc.metadata)
    jrows = k * np.arange(h) + row_offset
    jcols = k * np.arange(w) + col_offset
    in_range = ((jrows >= 0) & (jrows < jrc.values.shape[0]))[:, None] & ((jcols >= 0) & (jcols < jrc.values.shape[1]))[None, :]
    covered = bool((tile_codes != 255).all())
    equal_cells = tile_codes == chip_codes
    post_t, state_t = decompose(tile_codes)
    post_c, state_c = decompose(chip_codes)
    edge = ~in_range
    # chip edge cells: JRC chip has no value, so the chip says forest-unknown where the tile knows the state
    edge_consistent = (post_t == post_c) & ((state_t >= 0) == (state_c >= 0)) & ((state_c == 2) | (state_c < 0))
    return {
        'aoi_cells': int(h * w), 'cells_covered_by_strips': covered,
        'cells_with_jrc_chip_coverage': int(in_range.sum()),
        'identical_on_cells_with_jrc_chip_coverage': bool(equal_cells[in_range].all()),
        'differing_cells_with_jrc_chip_coverage': int((~equal_cells[in_range]).sum()),
        'chip_edge_cells_without_jrc_value': int(edge.sum()),
        'chip_edge_cells_differing': int((~equal_cells[edge]).sum()),
        'chip_edge_difference_is_only_forest_state_unknown_in_chip': bool(edge_consistent[edge & ~equal_cells].all()),
        'exact_equal_percent_of_all_cells': percent(int(equal_cells.sum()), int(equal_cells.size)),
        'explanation': 'The JRC chip is the company bbox chip and is smaller than the Hansen chip, so a one-row, '
                       'two-column fringe has no JRC value and derive_screen_codes marks forest unknown there. '
                       'The tile has JRC everywhere, so the strip pipeline resolves those cells.'}


def check_decimation(root, tile, rows_list, nrows):
    """Decimated out_shape read of the JRC strip vs explicit pinned indexing, on a few strips."""
    hansen_paths, jrc_path = tile_paths(root)
    hansen = [rasterio.open(p) for p in hansen_paths]
    jrc_src = rasterio.open(jrc_path)
    results = []
    try:
        for r0 in rows_list:
            bands, masks, hmeta, jvalues, jmask, jmeta = read_strip(hansen, jrc_src, r0, nrows)
            explicit, plane = strip_codes(bands, masks, hmeta, jvalues, jmask, jmeta)
            decimated = jrc_src.read(1, window=Window(0, 3 * r0, jrc_src.width, 3 * nrows),
                                     out_shape=(nrows, hansen[0].width))
            via_decimation = derive_screen_codes(Dataset(bands, masks, hmeta),
                                                 presampled_jrc(hmeta, decimated))
            results.append({'hansen_row_start': r0, 'rows': nrows,
                            'decimated_plane_equals_explicit_indexing': bool(np.array_equal(decimated, plane)),
                            'codes_equal': bool(np.array_equal(via_decimation, explicit))})
    finally:
        for r in hansen + [jrc_src]:
            r.close()
    return results


def run_scale(workers=8, strip_rows=250, xz_every=1, decode_every=8, root=ROOT, log=print):
    t_start = time.perf_counter()
    tile = tile_geometry(root)
    h, w = tile['hansen']['shape']
    log(f'tile verified: Hansen {h}x{w}, JRC {tile["jrc"]["shape"]}, nesting {tile["nesting"]}')
    chip, hansen_chip, jrc_chip, origin = locate_chip(root, tile)
    log(f'AOI chip at Hansen row/col {origin}; chip pixels equal tile: {chip["chip_pixels_equal_tile_window"]}')
    aoi = (origin[0], origin[0] + hansen_chip.metadata['shape'][0], origin[1], origin[1] + hansen_chip.metadata['shape'][1])
    starts = list(range(0, h, strip_rows))
    tasks = [(r0, min(strip_rows, h - r0), xz_every > 0 and i % xz_every == 0, decode_every > 0 and i % decode_every == 0, aoi)
             for i, r0 in enumerate(starts)]
    results = {}
    t_pool = time.perf_counter()
    ctx = multiprocessing.get_context('spawn')
    with futures.ProcessPoolExecutor(max_workers=workers, mp_context=ctx, initializer=_init_worker,
                                     initargs=(str(root),)) as pool:
        pending = {pool.submit(process_strip, t): t[0] for t in tasks}
        for done, fut in enumerate(futures.as_completed(pending), 1):
            results[pending[fut]] = fut.result()
            if done % 10 == 0 or done == len(tasks):
                log(f'  {done}/{len(tasks)} strips, {time.perf_counter() - t_pool:.0f}s elapsed')
    pool_s = time.perf_counter() - t_pool
    strips = [results[r0] for r0 in starts]

    if any(s['max_values'][0] > 100 or s['max_values'][1] > 25 or s['max_values'][2] > 2 for s in strips):
        raise ValueError('Hansen value outside the documented range')
    if any(s['jrc_native_other_values'] for s in strips):
        raise ValueError('JRC value outside 0/1')
    aoi_check = check_aoi([s['aoi'] for s in strips if s['aoi']], hansen_chip, jrc_chip, origin)
    mid = starts[origin[0] // strip_rows]
    decimation = check_decimation(root, tile, [starts[0], mid, starts[-1]], min(strip_rows, 100))
    log(f'AOI check: {aoi_check["identical_on_cells_with_jrc_chip_coverage"]}; decimation: {decimation}')

    def total(key):
        return sum(s['sizes'][key] for s in strips)

    hist = np.sum([s['code_hist'] for s in strips], axis=0)
    post_idx = np.array([(c - LAND) % 6 if c >= LAND else -1 for c in range(CODE_COUNT)])
    state_idx = np.array([(c - LAND) // 6 if c >= LAND else -1 for c in range(CODE_COUNT)])
    land_cells = int(hist[LAND:].sum())
    loss_hist = np.sum([s['land_lossyear_hist'] for s in strips], axis=0)
    dm = np.sum([s['datamask_hist'] for s in strips], axis=0)
    tc_hist = np.sum([s['land_treecover_hist'] for s in strips], axis=0)
    jrc_native = np.sum([s['jrc_native_hist'] for s in strips], axis=0)
    sampled = np.sum([s['sampled_state_hist_all_cells'] for s in strips], axis=0)
    deforested = {str(y): int(hist[(state_idx == 1) & (post_idx == i + 1)].sum()) for i, y in enumerate(POST_YEARS)}
    loss_all = {str(y): int(hist[(post_idx == i + 1)].sum()) for i, y in enumerate(POST_YEARS)}
    post_loss = int(hist[post_idx > 0].sum())

    plane_names = ['treecover2000_exact', 'lossyear_full', 'lossyear_2001_2020', 'lossyear_2021_2025', 'datamask',
                   'jrc_native_9m', 'jrc_sampled_at_hansen_centres', 'post2020_loss_on_jrc_nonforest',
                   'screen_codes_L1', 'decision_codes_L2']
    planes = {n: {'zstd19_bytes': total(n), 'bits_per_hansen_cell': round(8.0 * total(n) / (h * w), 5)} for n in plane_names}
    originals = {n: tile['files'][Path(p).name]['bytes'] for n, p in
                 zip(HANSEN_BANDS, [HANSEN_RAW.format(b) for b in HANSEN_BANDS])}
    jrc_bytes = tile['files'][Path(JRC_TILE).name]['bytes']
    original_total = sum(originals.values()) + jrc_bytes
    l0_hansen = sum(planes[n]['zstd19_bytes'] for n in ('treecover2000_exact', 'lossyear_full', 'datamask'))
    l0_all = l0_hansen + planes['jrc_native_9m']['zstd19_bytes']
    l1, l2 = planes['screen_codes_L1']['zstd19_bytes'], planes['decision_codes_L2']['zstd19_bytes']

    xz_strips = [s for s in strips if s['xz_sizes']]
    xz_block = None
    if xz_strips:
        keys = ('treecover2000_exact', 'lossyear_full', 'datamask', 'screen_codes_L1', 'decision_codes_L2')
        xz_sum = {k: sum(s['xz_sizes'][k] for s in xz_strips) for k in keys}
        z_sum = {k: sum(s['sizes'][k] for s in xz_strips) for k in keys}
        full = len(xz_strips) == len(strips)
        xz_block = {
            'strips_measured': len(xz_strips), 'strips_total': len(strips), 'all_strips_measured': full,
            'preset': 'xz preset 9 extreme',
            'xz_bytes_on_measured_strips': xz_sum, 'zstd19_bytes_on_the_same_strips': z_sum,
            'xz_over_zstd19_ratio': {k: round(xz_sum[k] / z_sum[k], 4) for k in keys},
            'tile_xz_bytes': {k: int(round(xz_sum[k] * (total(k) / z_sum[k]))) if not full else xz_sum[k] for k in keys},
            'tile_xz_method': 'measured on every strip' if full else
            'xz on a sample of evenly spaced strips, scaled by that sample\'s xz/zstd ratio onto the full-tile zstd bytes'}
    decode_strips = [s for s in strips if s['decode_seconds']]
    decode_block = None
    if decode_strips:
        keys = ('treecover2000_exact', 'lossyear_full', 'datamask', 'screen_codes_L1', 'decision_codes_L2')
        scale_up = len(strips) / len(decode_strips)
        decode_block = {'strips_measured': len(decode_strips), 'strips_total': len(strips),
                        'method': 'zstd decompress of the level-19 frame, single thread, warm cache; sample sum '
                                  'scaled by strips_total/strips_measured',
                        'tile_seconds_estimate': {k: round(sum(s['decode_seconds'][k] for s in decode_strips) * scale_up, 3) for k in keys}}
    read_seconds = sum(s['seconds']['read'] for s in strips)
    wall = time.perf_counter() - t_start
    return {
        'schema': 'plotline.decision-scale.v1',
        'as_of': AS_OF,
        'tile': {'name': 'Hansen 10N_090E (0-10N, 90-100E) and JRC GFC2020 v4 N10_E90', 'grid': tile,
                 'hansen_cells': h * w, 'land_cell_hectares_note': 'cells of about 0.076 ha (Hansen) and 0.0085 ha (JRC) at 8.5N'},
        'method': {
            'strip_rows_hansen': strip_rows, 'strips': len(strips), 'jrc_rows_per_strip': 3 * strip_rows,
            'processed': 'all strips' if len(strips) == len(starts) else 'subset',
            'codes': 'engine.decision.derive_screen_codes on a per-strip Dataset/JrcDataset built from windowed reads; '
                     'strip transforms come from rasterio window_transform so nested_offsets verifies the nesting per strip',
            'compression': f'zstd level {ZSTD_LEVEL} per strip per plane (row-major, no chunk index or header overhead), '
                           'sizes summed; xz preset 9e on strips as listed under xz',
            'yardstick_note': 'L0 yardstick = zstd-19 of the 3 raw Hansen bands per strip. It is a size yardstick for '
                              'lossless storage, not the retained v1 container (1,024-cell chunks plus index).',
            'workers': workers, 'extrapolated': False,
            'per_strip_nesting_offsets': sorted({tuple(s['offsets']) for s in strips}),
            'every_strip_presampled_codes_equal_pinned_codes': all(s['presampled_equal'] for s in strips)},
        'runtime': {'wall_seconds_total': round(wall, 2), 'pool_seconds': round(pool_s, 2),
                    'cpu_seconds_by_phase_summed_over_workers': {
                        k: round(sum(s['seconds'][k] for s in strips), 2) for k in ('read', 'derive', 'zstd', 'xz')},
                    'python': sys.version.split()[0], 'numpy': np.__version__, 'rasterio': rasterio.__version__,
                    'machine': f'{platform.machine()} {platform.system()} {os.cpu_count()} cores'},
        'sizes_bytes': {
            'original_geotiff': {**originals, 'jrc': jrc_bytes, 'hansen3': sum(originals.values()), 'total': original_total,
                                 'compression': 'LZW, 1-row blocks'},
            'zstd19_planes': planes,
            'L0_yardstick_hansen3_zstd19': l0_hansen,
            'L0_yardstick_hansen3_plus_jrc_native_zstd19': l0_all,
            'L1_screen_zstd19': l1,
            'L2_decision_zstd19': l2},
        'ratios': {
            'L0_yardstick_hansen3_vs_original_hansen3': round(l0_hansen / sum(originals.values()), 4),
            'L0_yardstick_hansen3_plus_jrc_vs_original_total': round(l0_all / original_total, 4),
            'L1_vs_original_total': round(l1 / original_total, 5),
            'L2_vs_original_total': round(l2 / original_total, 5),
            'L1_vs_L0_yardstick_hansen3_plus_jrc': round(l1 / l0_all, 5),
            'L2_vs_L0_yardstick_hansen3_plus_jrc': round(l2 / l0_all, 5),
            'L2_vs_L1': round(l2 / l1, 4),
            'L1_percent_smaller_than_original_total': round(100 * (1 - l1 / original_total), 2),
            'L2_percent_smaller_than_original_total': round(100 * (1 - l2 / original_total), 2),
            'L1_percent_smaller_than_zstd19_yardstick': round(100 * (1 - l1 / l0_all), 2),
            'L2_percent_smaller_than_zstd19_yardstick': round(100 * (1 - l2 / l0_all), 2)},
        'xz': xz_block,
        'decode_timing': decode_block,
        'gdal_read_seconds_all_strips_summed': round(read_seconds, 2),
        'histograms': {
            'datamask_all_cells': {'0_no_data': int(dm[0]), '1_land': int(dm[1]), '2_water': int(dm[2])},
            'land_cells': land_cells,
            'land_fraction_of_tile_percent': percent(land_cells, h * w),
            'code_counts': {CODE_LABELS[i]: int(v) for i, v in enumerate(hist)},
            'forest_state_land_cells': {name: int(hist[state_idx == i].sum()) for i, name in enumerate(FOREST_STATES)},
            'jrc_forest_share_of_land_at_hansen_centres_percent': percent(int(hist[state_idx == 1].sum()), land_cells),
            'jrc_native_cells': {'nonforest': int(jrc_native[0]), 'forest': int(jrc_native[1]),
                                 'forest_percent': percent(int(jrc_native[1]), int(jrc_native.sum()))},
            'sampled_forest_state_all_cells': {'nonforest': int(sampled[0]), 'forest': int(sampled[1]), 'unknown': int(sampled[2])},
            'land_cells_with_any_hansen_loss': int(loss_hist[1:].sum()),
            'land_cells_with_any_hansen_loss_percent': percent(int(loss_hist[1:].sum()), land_cells),
            'land_cells_treecover_gt_10': int(tc_hist[11:].sum()),
            'post2020_loss_cells': post_loss,
            'post2020_loss_by_year_all_land': loss_all,
            'deforested_cells_by_year': deforested,
            'deforested_cells_total': int(sum(deforested.values())),
            'deforested_share_of_post2020_loss_percent': percent(int(sum(deforested.values())), post_loss),
            'post2020_loss_on_jrc_nonforest_cells': int(hist[(state_idx == 0) & (post_idx > 0)].sum()),
            'post2020_loss_on_unknown_forest_cells': int(hist[(state_idx == 2) & (post_idx > 0)].sum()),
            'land_lossyear_histogram_0_to_25': [int(v) for v in loss_hist]},
        'validation': {'aoi_chip_in_tile': chip, 'aoi_codes': aoi_check, 'decimated_read_vs_explicit_indexing': decimation},
        'strips_table': {'columns': ['hansen_row_start', 'rows', 'L1_zstd19', 'L2_zstd19', 'treecover_zstd19',
                                      'lossyear_zstd19', 'datamask_zstd19', 'jrc_native_zstd19', 'land_cells'],
                         'rows': [[s['r0'], s['rows'], s['sizes']['screen_codes_L1'], s['sizes']['decision_codes_L2'],
                                   s['sizes']['treecover2000_exact'], s['sizes']['lossyear_full'], s['sizes']['datamask'],
                                   s['sizes']['jrc_native_9m'], int(sum(s['code_hist'][LAND:]))] for s in strips]},
    }


# ---------------------------------------------------------------------------
# 3. cost estimate
# ---------------------------------------------------------------------------

PRICE_LABEL = 'list price assumption, verify before quoting'


def read_timing(root=ROOT, strip_rows=250, passes=3):
    """Wall seconds for one process to read all four tile files fully, in the strips --scale uses.

    One thread, no other work, the files read through GDAL exactly as read_strip does (Hansen
    strip_rows rows of 3 bands, the 3x larger JRC window). Passes run back to back, so every pass
    after the first reads from a warm OS cache; the median is the figure the cost model uses.
    """
    hansen_paths, jrc_path = tile_paths(root)
    readers = [rasterio.open(p) for p in hansen_paths] + [rasterio.open(jrc_path)]
    try:
        h, w = readers[0].height, readers[0].width
        k = readers[3].width // w
        seconds, cells = [], 0
        for _ in range(passes):
            cells, started = 0, time.perf_counter()
            for r0 in range(0, h, strip_rows):
                n = min(strip_rows, h - r0)
                cells += sum(r.read(1, window=Window(0, r0, w, n)).size for r in readers[:3])
                cells += readers[3].read(1, window=Window(0, k * r0, readers[3].width, k * n)).size
            seconds.append(time.perf_counter() - started)
    finally:
        for reader in readers:
            reader.close()
    return {'schema': 'plotline.decision-tile-read.v1', 'as_of': AS_OF,
            'method': f'single process, no worker pool; {len(readers)} files read fully through GDAL in strips of '
                      f'{strip_rows} Hansen rows (read_strip geometry); {passes} back-to-back passes',
            'files': [str(Path(p).relative_to(root)) for p in [*hansen_paths, jrc_path]],
            'cells_read': cells, 'pass_seconds': [round(v, 3) for v in seconds],
            'single_process_tile_read_seconds': round(sorted(seconds)[len(seconds) // 2], 3),
            'machine': f'{platform.machine()} {platform.system()} {os.cpu_count()} cores',
            'rasterio': rasterio.__version__, 'gdal': rasterio.__gdal_version__}


def benchmark_inputs(path=BENCHMARK_PATH):
    """(per-plot microseconds, source labels) from a measured benchmark result's cost_inputs, or None if absent."""
    path = Path(path)
    if not path.is_file():
        return None
    result = json.loads(path.read_text())
    if result.get('status') != 'measured':
        raise ValueError(f'{path.name} is not a measured full benchmark (status {result.get("status")!r})')
    inputs = result['cost_inputs']
    where = f'{path.relative_to(ROOT) if ROOT in path.parents else path}'
    sources = {key: f'{where} cost_inputs.{field}: {inputs["source"]}'
               for key, field in (('original', 'original_us'), ('registry', 'registry_us'), ('new_polygon', 'new_polygon_us'))}
    return {'original': inputs['original_us'], 'registry': inputs['registry_us'],
            'new_polygon': inputs['new_polygon_us']}, sources


def price(value, unit):
    return {'value': value, 'unit': unit, 'label': PRICE_LABEL, 'as_of': AS_OF}


def cost_model(scale, original_us_per_plot, decision_registry_us_per_plot, decision_new_polygon_us_per_plot,
               per_plot_sources=None, tile_read=None, plots=10_000_000, belt_tiles=100, global_tiles=280,
               lambda_memory_gb=1.0, get_range_bytes=8 * 2**20, versions=(1, 5)):
    """Storage and re-check cost from measured tile bytes; every input is a parameter.

    The three per-plot microsecond figures are hot-path figures and have no defaults, so none can go
    stale: original_us_per_plot (original layers), decision_registry_us_per_plot (registered plot) and
    decision_new_polygon_us_per_plot (unregistered polygon). per_plot_sources maps original / registry /
    new_polygon to a label naming where each figure came from; it is recorded as given.
    tile_read, if given, is {'seconds': float, 'source': str} for one single-process read of the four
    tile files; otherwise the 8-worker CPU sum in scale-v1.json is used and labelled as such.
    """
    per_plot_sources = {'original': 'caller-supplied parameter', 'registry': 'caller-supplied parameter',
                        'new_polygon': 'caller-supplied parameter', **(per_plot_sources or {})}
    new_polygon_us = decision_new_polygon_us_per_plot
    if tile_read is None:
        tile_read = {'seconds': scale['gdal_read_seconds_all_strips_summed'],
                     'source': 'scale-v1.json gdal_read_seconds_all_strips_summed: the sum of per-strip read seconds over '
                               'the scale run\'s 8 worker processes, not one uncontended process; it overstates the '
                               'single-process time (run --read-timing for that)'}
    prices = {
        's3_standard_storage': price(0.023, 'USD per GB-month'),
        's3_get_requests': price(0.0004, 'USD per 1,000 GET requests'),
        'lambda_compute': price(0.0000166667, 'USD per GB-second'),
        'lambda_requests': price(0.20, 'USD per 1,000,000 invocations'),
        'egress': {'value': 0, 'unit': 'ignored', 'label': 'assumed same-region, not charged', 'as_of': AS_OF}}
    gb = 2**30
    sizes = scale['sizes_bytes']
    reps = {
        'original_layers_geotiff': {'bytes': sizes['original_geotiff']['total'],
                                    'what': 'Hansen 3 bands + JRC tile, as downloaded (LZW GeoTIFF)'},
        'L0_yardstick_zstd19': {'bytes': sizes['L0_yardstick_hansen3_plus_jrc_native_zstd19'],
                                'what': 'same layers, lossless, zstd-19 yardstick'},
        'L1_screen': {'bytes': sizes['L1_screen_zstd19'], 'what': 'eudr-screen.v1 codes, zstd-19'},
        'L2_decision': {'bytes': sizes['L2_decision_zstd19'], 'what': 'eudr-decision.v1 codes, zstd-19'}}
    decode = (scale.get('decode_timing') or {}).get('tile_seconds_estimate') or {}
    decode_s = {
        'original_layers_geotiff': tile_read['seconds'],
        'L0_yardstick_zstd19': None,
        'L1_screen': decode.get('screen_codes_L1'),
        'L2_decision': decode.get('decision_codes_L2')}
    if all(k in decode for k in ('treecover2000_exact', 'lossyear_full', 'datamask')):
        decode_s['L0_yardstick_zstd19'] = round(sum(decode[k] for k in ('treecover2000_exact', 'lossyear_full', 'datamask')), 3)
    per_plot_us = {'original_layers_geotiff': original_us_per_plot, 'L0_yardstick_zstd19': original_us_per_plot,
                   'L1_screen': decision_registry_us_per_plot, 'L2_decision': decision_registry_us_per_plot}
    land_fraction = scale['histograms']['land_cells'] / scale['tile']['hansen_cells']
    cells = scale['tile']['hansen_cells']
    land_cells = scale['histograms']['land_cells']

    # Land content drives compressed size. The measured tile is only 13.7% land, so three bases bracket the
    # estimate: the tile as measured, an assumed half-land tile, and a tile whose every cell is land like this one.
    bases = {'measured_tile': 1.0,
             'half_land_assumption': 0.5 * cells / land_cells,
             'all_land_scenario': cells / land_cells}

    def storage(nbytes, tiles, n_versions):
        gigabytes = nbytes * tiles * n_versions / gb
        return {'gb': round(gigabytes, 4), 'usd_per_month': round(gigabytes * prices['s3_standard_storage']['value'], 4)}

    out_reps = {}
    for name, rep in reps.items():
        nbytes = rep['bytes']
        out_reps[name] = {
            'what': rep['what'], 'bytes_per_tile_measured': nbytes, 'mb_per_tile_measured': round(nbytes / 1e6, 3),
            'bytes_per_land_cell': round(nbytes / land_cells, 4),
            'percent_of_original': round(100 * nbytes / reps['original_layers_geotiff']['bytes'], 3),
            'ranged_gets_to_read_one_measured_tile': math.ceil(nbytes / get_range_bytes),
            'storage_by_basis': {
                basis: {'bytes_per_tile': int(nbytes * factor),
                        'one_tile': {f'versions_{v}': storage(nbytes * factor, 1, v) for v in versions},
                        'tropical_belt': {f'versions_{v}': storage(nbytes * factor, belt_tiles, v) for v in versions},
                        'global_land': {f'versions_{v}': storage(nbytes * factor, global_tiles, v) for v in versions}}
                for basis, factor in bases.items()}}

    def recheck(name, tiles, factor, us=None):
        rep = reps[name]
        per_plot_s = plots * (per_plot_us[name] if us is None else us) / 1e6
        dec = decode_s[name]
        tile_s = None if dec is None else tiles * dec * factor
        compute_s = per_plot_s + (tile_s or 0.0)
        gets = tiles * math.ceil(rep['bytes'] * factor / get_range_bytes)
        lam = compute_s * lambda_memory_gb * prices['lambda_compute']['value'] + tiles * prices['lambda_requests']['value'] / 1e6
        get_cost = gets / 1000 * prices['s3_get_requests']['value']
        return {'per_plot_compute_seconds': round(per_plot_s, 2), 'tile_decode_seconds': None if tile_s is None else round(tile_s, 2),
                'total_compute_seconds': round(compute_s, 2), 'gets': gets, 'lambda_usd': round(lam, 5),
                'get_usd': round(get_cost, 6), 'total_usd': round(lam + get_cost, 5)}

    def recheck_scopes(name, us=None):
        return {basis: {'tropical_belt': recheck(name, belt_tiles, factor, us),
                        'global_land': recheck(name, global_tiles, factor, us)} for basis, factor in bases.items()}

    recheck_out = {n: recheck_scopes(n) for n in reps}
    recheck_out['L2_decision_new_polygons'] = {
        'note': 'L2 codes but the polygon cells are selected on demand (not a registered plot): per-plot time is the '
                f'decision_new_polygon figure ({per_plot_sources["new_polygon"]})',
        'per_plot_us': new_polygon_us,
        **recheck_scopes('L2_decision', new_polygon_us)}
    p = prices
    return {
        'schema': 'plotline.decision-cost.v1',
        'as_of': AS_OF,
        'status': 'estimate; every price is a list price assumption (no web lookup), verify before quoting',
        'assumptions': {
            'prices': p,
            'gb_definition': f'1 GB = 2^30 bytes (S3 billing convention); decimal MB shown only for readability',
            'tiles': {'grid_cells_between_30N_and_30S': 36 * 6,
                      'grid_cells_method': '36 longitude columns x 6 ten-degree latitude bands (30N-20N ... 20S-30S)',
                      'tropical_belt_land_tiles': belt_tiles,
                      'tropical_belt_method': 'assumption, not a count: about 100 of the 216 grid cells hold substantial land. '
                                              'No land-mask dataset was used.',
                      'global_land_tiles': global_tiles, 'global_method': 'assumption (~280 Hansen land tiles)',
                      'scaling': 'linear in tile count. The measured tile is 13.7% land, so storage and re-check '
                                 'are shown on three bases: measured_tile (bytes as measured), half_land_assumption '
                                 '(bytes per land cell x 50% land) and all_land_scenario (bytes per land cell x every '
                                 'cell; a rough ceiling that assumes all land is as complex as this tile\'s)'},
            'measured_tile': {'name': scale['tile']['name'], 'land_fraction_percent': round(100 * land_fraction, 2)},
            'versions_kept_rows': list(versions),
            'registered_plots': plots,
            'per_plot_microseconds': {
                'original_v1': original_us_per_plot, 'original_v1_source': per_plot_sources['original'],
                'decision_registry': decision_registry_us_per_plot,
                'decision_registry_source': per_plot_sources['registry'],
                'decision_new_polygon': new_polygon_us, 'decision_new_polygon_source': per_plot_sources['new_polygon']},
            'lambda': {'memory_gb': lambda_memory_gb, 'note': 'same memory for every representation (no credit '
                       'taken for the smaller working set)', 'one_invocation_per_tile': True},
            'get_request_range_bytes': get_range_bytes,
            'tile_decode_seconds': {'source': f'original layers: {tile_read["source"]}. L0/L1/L2: scale-v1.json '
                                              'decode_timing (zstd decompress of the level-19 frames, single thread, '
                                              'warm cache, sampled strips scaled up)',
                                    'caveat': 'warm-cache decode only: cold object-store latency and network time are '
                                              'not modelled; the original path would also need the JRC sampling step',
                                    'values': decode_s},
            'container': {'assumption': 'ranged GETs and per-strip working memory assume a strip-indexed container that is '
                                        f'NOT implemented. The shipped store (engine.decision_store) holds at most {MAX_DIMENSION:,} '
                                        f'cells per side and {MAX_CELLS:,} cells, far below this tile\'s '
                                        f'{scale["tile"]["hansen_cells"]:,} cells; tile sizes here are '
                                        'zstd-19 per-strip sums (a yardstick) and ranged_gets_to_read_one_measured_tile is '
                                        'ceil(bytes / get_request_range_bytes), valid only for such a container.',
                          'store_max_dimension': MAX_DIMENSION, 'store_max_cells': MAX_CELLS},
            'plots_per_tile': 'the same 10 million plots are re-checked in both scopes; every tile in scope is read '
                              'once per re-check (upper bound on tiles touched)'},
        'formulas': {
            'basis_factor': 'measured_tile 1; half_land_assumption 0.5 * tile_cells / land_cells; '
                            'all_land_scenario tile_cells / land_cells (bytes_per_tile = measured bytes * factor)',
            'storage_usd_per_month': 'bytes_per_tile * tiles * versions / 2^30 * s3_standard_storage',
            'recheck_per_plot_seconds': 'plots * per_plot_microseconds / 1e6',
            'recheck_lambda_usd': '(per_plot_seconds + tiles * tile_decode_seconds * factor) * memory_gb * '
                                  'lambda_per_gb_second + tiles * lambda_per_invocation',
            'recheck_get_usd': 'tiles * ceil(bytes_per_tile / get_range_bytes) / 1000 * s3_get_per_1000'},
        'inputs_from_scale': {'path': str(SCALE_PATH.relative_to(ROOT)), 'tile_land_cells': land_cells,
                              'tile_cells': cells},
        'representations': out_reps,
        'recheck_10m_plots': recheck_out,
        'notes': [
            'At these list prices the figures are cents to a few tens of dollars a month: the layer-size saving is '
            'large in proportion and small in absolute cost. The bigger operational gain is time to answer and '
            'memory per worker, which this table does not price.',
            'The ocean-heavy measured tile flatters every representation; the all_land_scenario row is the ceiling.',
            'Storage assumes one copy of the layers; versions_5 keeps five annual layer vintages.',
            'Per-plot compute is a hot-path argument. Reading data, cold start and polygon selection for new '
            'geometries are separate; the new-polygon row shows that selection dominates once the plot is unregistered.',
            'Prices are widely known historical list prices assumed for 2026-10-15; no live pricing was consulted.'],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--analysis', action='store_true', help='AOI layer analysis and JRC aggregation sensitivity')
    parser.add_argument('--scale', action='store_true', help='whole-tile strip run (needs the cached full tiles)')
    parser.add_argument('--read-timing', action='store_true', help='single-process tile read time -> tile-read-v1.json')
    parser.add_argument('--cost', action='store_true', help='cost estimate from artifacts/decision/scale-v1.json')
    parser.add_argument('--workers', type=int, default=8, help='scale worker processes (default 8)')
    parser.add_argument('--strip-rows', type=int, default=250, help='Hansen rows per strip (default 250)')
    parser.add_argument('--xz-every', type=int, default=1, help='xz every Nth strip; 0 disables (default 1 = all)')
    parser.add_argument('--original-us', type=float, help='override: original-layers hot microseconds per plot')
    parser.add_argument('--registry-us', type=float, help='override: decision registry microseconds per plot')
    parser.add_argument('--new-polygon-us', type=float, help='override: decision new-polygon microseconds per plot')
    args = parser.parse_args(argv)
    if not (args.analysis or args.scale or args.read_timing or args.cost):
        args.analysis = args.scale = args.read_timing = args.cost = True
    if args.analysis:
        result = analyse_layers()
        write_json(ANALYSIS_PATH, result)
        print(f'wrote {ANALYSIS_PATH}')
    if args.scale:
        result = run_scale(workers=min(max(args.workers, 1), 8), strip_rows=args.strip_rows, xz_every=args.xz_every)
        write_json(SCALE_PATH, result)
        print(f'wrote {SCALE_PATH} in {result["runtime"]["wall_seconds_total"]} s')
    if args.read_timing:
        result = read_timing()
        write_json(READ_TIMING_PATH, result)
        print(f'wrote {READ_TIMING_PATH}: {result["single_process_tile_read_seconds"]} s per tile, passes {result["pass_seconds"]}')
    if args.cost:
        scale = json.loads(SCALE_PATH.read_text())
        found = benchmark_inputs()
        values, sources = found if found else ({}, {})
        for key, value, flag in (('original', args.original_us, '--original-us'), ('registry', args.registry_us, '--registry-us'),
                                 ('new_polygon', args.new_polygon_us, '--new-polygon-us')):
            if value is not None:
                values[key], sources[key] = value, f'command line {flag}'
            elif key not in values:
                parser.error(f'{BENCHMARK_PATH.name} is absent: run engine.decision_benchmark or pass {flag}')
        tile_read = None
        if READ_TIMING_PATH.is_file():
            measured = json.loads(READ_TIMING_PATH.read_text())
            tile_read = {'seconds': measured['single_process_tile_read_seconds'],
                         'source': f'{READ_TIMING_PATH.relative_to(ROOT)} single_process_tile_read_seconds: median of '
                                   f'{len(measured["pass_seconds"])} back-to-back single-process GDAL passes over the four tile '
                                   f'files ({measured["as_of"]}, {measured["machine"]})'}
        result = cost_model(scale, values['original'], values['registry'], values['new_polygon'],
                            per_plot_sources=sources, tile_read=tile_read)
        write_json(COST_PATH, result)
        print(f'wrote {COST_PATH}')


if __name__ == '__main__':
    main()
