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


# summarize_counts unpacks this exact layout by name: change it there too if any of these change.
if (POST_YEARS, tuple(PERIODS.items()), FOREST_STATES, (UNKNOWN, WATER, LAND)) != (
        (2021, 2022, 2023, 2024, 2025), (('2021-2023', (2021, 2023)), ('2024-2025', (2024, 2025))),
        ('nonforest', 'forest', 'unknown'), (0, 1, 2)):
    raise RuntimeError('decision code layout changed: update summarize_counts')


def summarize_counts(counts, selected_count, outside_count, level):
    """Contract outputs from a 20-bin code histogram plus out-of-chip selections."""
    if level not in LEVELS:
        raise ValueError('unknown contract level')
    if getattr(getattr(counts, 'dtype', None), 'kind', None) in ('i', 'u'):  # an integer ndarray
        counts = counts.tolist()
    else:
        counts = list(map(int, counts))
    if len(counts) != CODE_COUNT or selected_count != sum(counts) + outside_count or outside_count < 0:
        raise ValueError('code histogram accounting mismatch')
    # codes: 0 unknown, 1 water, then land 2 + 6 * JRC 2020 state (nonforest, forest, unknown) + post-2020 year 0..5
    _, water, n0, n1, n2, n3, n4, n5, f0, f1, f2, f3, f4, f5, u0, u1, u2, u3, u4, u5 = counts
    total = f1 + f2 + f3 + f4 + f5
    funk_post = u1 + u2 + u3 + u4 + u5
    nonforest, forest, funk = n0 + n1 + n2 + n3 + n4 + n5, f0 + total, u0 + funk_post
    land = nonforest + forest + funk
    unknown = outside_count + counts[0]
    if land > 0:  # analytical
        forest_present = True if forest > 0 else (False if unknown + funk == 0 else None)
        deforested_present = True if total > 0 else (False if unknown + funk_post == 0 else None)
        out = {'contract': level, 'selected_cell_count': selected_count,
               'out_of_coverage_cell_count': outside_count, 'valid_land_cell_count': land,
               'water_cell_count': water, 'unknown_cell_count': unknown,
               'forest_2020': {'cell_counts': {'nonforest': nonforest, 'forest': forest, 'unknown': funk},
                               'present': forest_present},
               'deforestation_after_2020': {
                   'yearly_cell_counts': {'2021': f1, '2022': f2, '2023': f3, '2024': f4, '2025': f5},
                   'cell_count': total, 'present': deforested_present}}
        if level == SCREEN_VERSION:
            l1, l2, l3, l4, l5 = n1 + f1 + u1, n2 + f2 + u2, n3 + f3 + u3, n4 + f4 + u4, n5 + f5 + u5
            early, late = l1 + l2 + l3, l4 + l5
            out['hansen_loss_after_2020'] = {
                'yearly_cell_counts': {'2021': l1, '2022': l2, '2023': l3, '2024': l4, '2025': l5},
                'periods': {'2021-2023': {'observed_loss_cell_count': early,
                                          'mapped_loss_present': True if early > 0 else (False if unknown == 0 else None)},
                            '2024-2025': {'observed_loss_cell_count': late,
                                          'mapped_loss_present': True if late > 0 else (False if unknown == 0 else None)}}}
    else:
        out = {'contract': level, 'selected_cell_count': selected_count,
               'out_of_coverage_cell_count': outside_count, 'valid_land_cell_count': land,
               'water_cell_count': water, 'unknown_cell_count': unknown,
               'forest_2020': {'cell_counts': None, 'present': None},
               'deforestation_after_2020': {'yearly_cell_counts': None, 'cell_count': None, 'present': None}}
        if level == SCREEN_VERSION:
            out['hansen_loss_after_2020'] = {
                'yearly_cell_counts': None,
                'periods': {'2021-2023': {'observed_loss_cell_count': None, 'mapped_loss_present': None},
                            '2024-2025': {'observed_loss_cell_count': None, 'mapped_loss_present': None}}}
    # Support covers both layers: a land cell without a JRC 2020 class is partial.
    out['support'] = ('none' if selected_count == 0 or land == 0 else
                      'partial' if unknown or funk else 'complete')
    return out
