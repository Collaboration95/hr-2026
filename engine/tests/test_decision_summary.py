"""summarize_counts unpacks the 20-code layout by name; pin it to the generic reducer it replaced."""
import json
import random
import unittest

import numpy as np

from engine.decision_summary import (CODE_COUNT, FOREST_STATES, LAND, LEVELS, PERIODS, POST_YEARS, SCREEN_VERSION,
                                     UNKNOWN, WATER, summarize_counts, summarize_ints)

_YEAR_KEYS = tuple(str(y) for y in POST_YEARS)
_PERIOD_SLICES = tuple((key, slice(lo - POST_YEARS[0], hi - POST_YEARS[0] + 1)) for key, (lo, hi) in PERIODS.items())


def reference(counts, selected_count, outside_count, level):
    """The reducer before the 15 Oct night pass, verbatim apart from its name."""
    if level not in LEVELS:
        raise ValueError('unknown contract level')
    if getattr(getattr(counts, 'dtype', None), 'kind', None) in ('i', 'u'):
        counts = counts.tolist()
    else:
        counts = [int(v) for v in counts]
    if len(counts) != CODE_COUNT or selected_count != sum(counts) + outside_count or outside_count < 0:
        raise ValueError('code histogram accounting mismatch')
    s0, s1, s2 = counts[LAND:LAND + 6], counts[LAND + 6:LAND + 12], counts[LAND + 12:LAND + 18]
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
    out['support'] = ('none' if selected_count == 0 or land == 0 else
                      'partial' if unknown or funk else 'complete')
    return out


def _run(fn, *args):
    try:
        out = fn(*args)
    except Exception as exc:  # the same exception type and message is part of the contract
        return 'raise', type(exc).__name__, str(exc)
    return 'ok', json.dumps(out), [list(v) if isinstance(v, dict) else None for v in [out, *out.values()]]


class SummarizeCountsTest(unittest.TestCase):
    def test_equals_generic_reducer(self):
        rng = random.Random(20261015)
        for _ in range(40_000):
            counts = [0] * CODE_COUNT
            if rng.random() < 0.4:  # sparse: reaches the None and False branches
                for _ in range(rng.randint(0, 3)):
                    counts[rng.randrange(CODE_COUNT)] = rng.choice([1, 2, 40])
            else:
                counts = [rng.choice([0, 0, 0, 1, 3, 50]) for _ in range(CODE_COUNT)]
            outside = rng.choice([0, 0, 0, 1, 7, -1] if rng.random() < 0.05 else [0, 0, 0, 1, 7])
            selected = sum(counts) + outside + (rng.choice([1, -1]) if rng.random() < 0.03 else 0)
            level = rng.choice([*LEVELS, 'bogus'] if rng.random() < 0.02 else LEVELS)
            form = rng.random()
            if form < 0.25:
                counts = np.array(counts, rng.choice([np.int64, np.uint16, np.int32]))
            elif form < 0.3:
                counts = [float(v) for v in counts]
            elif form < 0.33:
                counts = counts[:-1] if rng.random() < 0.5 else counts + [0]
            elif form < 0.36:
                counts = tuple(bool(v) for v in counts)
            args = (counts, selected, outside, level)
            self.assertEqual(_run(summarize_counts, *args), _run(reference, *args), args)

    def test_trusted_entry_equals_summarize_counts_on_lists_of_ints(self):
        """summarize_ints skips only the coercion: same results, key order, and exception type and message."""
        rng = random.Random(20261016)
        seen = {'ok': 0, 'length': 0, 'accounting': 0, 'negative_outside': 0, 'level': 0}
        for _ in range(20_000):
            if rng.random() < 0.4:  # sparse: reaches the None and False branches
                counts = [0] * CODE_COUNT
                for _ in range(rng.randint(0, 3)):
                    counts[rng.randrange(CODE_COUNT)] = rng.choice([1, 2, 40])
            else:
                counts = [rng.choice([0, 0, 0, 1, 3, 50]) for _ in range(CODE_COUNT)]
            outside = rng.choice([0, 0, 0, 1, 7])
            selected = sum(counts) + outside
            level = rng.choice(LEVELS)
            case = rng.random()
            if case < 0.1:  # wrong length, with accounting otherwise consistent or not
                counts = counts[:-1] if rng.random() < 0.5 else counts + [rng.choice([0, 4])]
            elif case < 0.2:  # accounting mismatch
                selected += rng.choice([1, -1, 5])
            elif case < 0.3:  # negative outside, accounted for so only that check can fail
                outside = -rng.choice([1, 2, 9])
                selected = sum(counts) + outside
            elif case < 0.35:  # a bad level on top of a valid or an invalid histogram: the level is checked first
                level = rng.choice(['bogus', '', None, SCREEN_VERSION + 'x'])
                selected += rng.choice([0, 0, 1])
            elif case < 0.4:  # two failures at once
                counts, selected, outside = counts[:-1], selected + 1, -1
            args = (counts, selected, outside, level)
            want, got, ref = _run(summarize_counts, *args), _run(summarize_ints, *args), _run(reference, *args)
            self.assertEqual(got, want, args)
            self.assertEqual(got, ref, args)
            if got[0] == 'ok':
                self.assertEqual(list(summarize_ints(*args)), list(summarize_counts(*args)))  # key order
                seen['ok'] += 1
            elif level not in LEVELS:
                seen['level'] += 1
            elif len(counts) != CODE_COUNT:
                seen['length'] += 1
            elif outside < 0:
                seen['negative_outside'] += 1
            else:
                seen['accounting'] += 1
        self.assertTrue(all(seen.values()), seen)  # every branch of the entry was exercised

    def test_trusted_entry_checks_the_level_before_the_histogram(self):
        zeros = [0] * CODE_COUNT
        for entry in (summarize_ints, summarize_counts):
            with self.assertRaisesRegex(ValueError, '^unknown contract level$'):
                entry(zeros[:-1], 1, -1, 'bogus')
            with self.assertRaisesRegex(ValueError, '^code histogram accounting mismatch$'):
                entry(zeros[:-1], 1, -1, SCREEN_VERSION)


if __name__ == '__main__':
    unittest.main()
