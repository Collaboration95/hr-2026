"""The EUDR decision contract's code space and its pure reducer, stdlib only.

Split out of engine.decision so a numpy-free path (engine.decision_lite) can share the one reducer.
engine.decision re-exports every name here.
"""
SCREEN_VERSION = 'eudr-screen.v1'
DECISION_VERSION = 'eudr-decision.v1'
LEVELS = (SCREEN_VERSION, DECISION_VERSION)
POST_YEARS = tuple(range(2021, 2026))
PERIODS = {'2021-2023': (2021, 2023), '2024-2025': (2024, 2025)}
FOREST_STATES = ('nonforest', 'forest', 'unknown')
UNKNOWN, WATER, LAND = 0, 1, 2
CODE_COUNT = LAND + 6 * len(FOREST_STATES)  # 20 codes: 0..19


_YEAR_KEYS = tuple(str(y) for y in POST_YEARS)
_PERIOD_SLICES = tuple((key, slice(lo - POST_YEARS[0], hi - POST_YEARS[0] + 1)) for key, (lo, hi) in PERIODS.items())


def summarize_counts(counts, selected_count, outside_count, level):
    """Contract outputs from a 20-bin code histogram plus out-of-chip selections."""
    if level not in LEVELS:
        raise ValueError('unknown contract level')
    if getattr(getattr(counts, 'dtype', None), 'kind', None) in ('i', 'u'):  # an integer ndarray
        counts = counts.tolist()
    else:
        counts = [int(v) for v in counts]
    if len(counts) != CODE_COUNT or selected_count != sum(counts) + outside_count or outside_count < 0:
        raise ValueError('code histogram accounting mismatch')
    s0, s1, s2 = counts[LAND:LAND + 6], counts[LAND + 6:LAND + 12], counts[LAND + 12:LAND + 18]  # per JRC forest state
    nonforest, forest, funk = sum(s0), sum(s1), sum(s2)
    land = nonforest + forest + funk
    unknown = outside_count + counts[UNKNOWN]
    analytical = land > 0
    forest_counts = dict(zip(FOREST_STATES, (nonforest, forest, funk)))
    deforested = dict(zip(_YEAR_KEYS, s1[1:]))
    total = sum(s1[1:])

    def tri(count, blockers):
        if not analytical:
            return None
        return True if count > 0 else (False if blockers == 0 else None)

    out = {'contract': level, 'selected_cell_count': selected_count,
           'out_of_coverage_cell_count': outside_count, 'valid_land_cell_count': land,
           'water_cell_count': counts[WATER], 'unknown_cell_count': unknown,
           'forest_2020': {'cell_counts': forest_counts if analytical else None,
                           'present': tri(forest, unknown + funk)},
           'deforestation_after_2020': {
               'yearly_cell_counts': deforested if analytical else None,
               'cell_count': total if analytical else None,
               'present': tri(total, unknown + sum(s2[1:]))}}
    if level == SCREEN_VERSION:
        loss = [x + y + z for x, y, z in zip(s0[1:], s1[1:], s2[1:])]
        periods = {}
        for key, sl in _PERIOD_SLICES:
            n = sum(loss[sl])
            periods[key] = {'observed_loss_cell_count': n if analytical else None,
                            'mapped_loss_present': tri(n, unknown)}
        out['hansen_loss_after_2020'] = {
            'yearly_cell_counts': dict(zip(_YEAR_KEYS, loss)) if analytical else None, 'periods': periods}
    # Support covers both layers: a land cell without a JRC 2020 class is partial.
    out['support'] = ('none' if selected_count == 0 or land == 0 else
                      'partial' if unknown or funk else 'complete')
    return out
