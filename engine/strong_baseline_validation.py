"""Strict JSON contracts for the additive control proof; no accepted-core writes."""
import math
import re
import sys
from .source import canonical_bytes
from .benchmark import summarize


def same(actual, expected, label):
    """JSON identity distinguishes bool/int/float and rejects extra/missing keys."""
    try:
        ok = canonical_bytes(actual) == canonical_bytes(expected)
    except (ValueError, TypeError, OverflowError, RecursionError) as exc:
        raise ValueError(label + ': invalid JSON types') from exc
    if not ok:
        raise ValueError(label)


def fields(value, names, label):
    if type(value) is not dict or set(value) != set(names):
        raise ValueError(label + ': missing/unknown fields')


def integer(value, low, high, label):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(label + ': bounded integer required')
    return value


def number(value, label):
    try:
        ok = type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:
        ok = False
    if not ok:
        raise ValueError(label + ': finite nonnegative number required')
    return value


def sha(value, label):
    if type(value) is not str or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise ValueError(label + ': SHA256 required')
    return value


def settings(value):
    fields(value, ('block_sizes','level','predictor','interleave','repetitions','warmups'), 'settings')
    blocks = value['block_sizes']
    if type(blocks) is not list or not blocks or len(blocks) > 2:
        raise ValueError('settings: nonempty bounded block list required')
    if any(type(b) is not int or b not in (256,512) for b in blocks) or len(set(blocks)) != len(blocks):
        raise ValueError('settings: unique supported integer blocks required')
    repetitions = integer(value['repetitions'],1,100,'repetitions')
    warmups = integer(value['warmups'],0,100,'warmups')
    same(value, {'block_sizes':blocks,'level':19,'predictor':1,'interleave':'band',
                 'repetitions':repetitions,'warmups':warmups}, 'unsupported constant settings')
    return blocks, repetitions, warmups


def timing(value, count):
    fields(value, ('samples','repetitions','min','median','p95'), 'timing summary')
    samples = value['samples']
    if type(samples) is not list or len(samples) != count:
        raise ValueError('timing sample count differs from settings')
    for sample in samples:
        number(sample,'timing sample')
    same(value, summarize(samples), 'timing summary differs from raw samples')


def rss(value):
    fields(value, ('native_value','native_unit','bytes','scope'), 'RSS')
    native = integer(value['native_value'],1,2**63-1,'RSS native value')
    unit = 'bytes' if sys.platform == 'darwin' else 'KiB'
    same(value, {'native_value':native, 'native_unit':unit,
                 'bytes':native if unit == 'bytes' else native*1024,
                 'scope':'child lifetime high-water mark including Python/imports, inputs and operation'},
         'RSS derived fields mismatch')


def measurements(value, count, answer):
    fields(value, ('full','indexed'), 'measurement modes')
    for mode, m in value.items():
        fields(m, ('hot','process_cold','process_cold_peak_rss','process_cold_answer_sha256',
                   'all_timed_answers_exact','expected_answer_sha256'), 'measurement '+mode)
        same(m['expected_answer_sha256'],answer,'measurement expected answer differs')
        same(m['all_timed_answers_exact'],True,'measurement exact flag differs')
        same(m['process_cold_answer_sha256'],[answer]*count,'process-cold sample answers differ')
        if type(m['process_cold_peak_rss']) is not list or len(m['process_cold_peak_rss']) != count:
            raise ValueError('process-cold RSS sample count differs')
        for record in m['process_cold_peak_rss']:
            rss(record)
        hot = m['hot']
        fields(hot, ('wall_ms','cpu_ms','initialization_ms_excluded','answer_sha256','peak_rss','subprocess_wall_ms'), 'hot measurement')
        same(hot['answer_sha256'],[answer],'hot sample answers differ')
        for k in ('wall_ms','cpu_ms'):
            timing(hot[k],count)
        for k in ('initialization_ms_excluded','subprocess_wall_ms'):
            number(hot[k],k)
        rss(hot['peak_rss'])
        cold = m['process_cold']
        fields(cold, ('wall_ms','cpu_ms','load_ms','load_cpu_ms','query_ms','query_cpu_ms','subprocess_wall_ms'), 'cold timing fields')
        for stat in cold.values():
            timing(stat,count)
        for total, load, query in (('wall_ms','load_ms','query_ms'),('cpu_ms','load_cpu_ms','query_cpu_ms')):
            same(cold[total]['samples'], [a+b for a,b in zip(cold[load]['samples'],cold[query]['samples'])],
                 'cold load/query sum differs')


def preprocessing(value, expected_report, custom=False):
    names = ['report','peak_rss','subprocess_wall_ms']
    if custom:
        names += ['remeasured','byte_identical_scratch_reproduction']
    fields(value,names,'preprocessing')
    if custom:
        same(value['remeasured'],True,'preprocessing remeasured flag')
        same(value['byte_identical_scratch_reproduction'],True,'preprocessing byte equality flag')
    rss(value['peak_rss'])
    number(value['subprocess_wall_ms'],'encode process wall')
    report = value['report']
    time_keys = ['encode_wall_ms','encode_cpu_ms'] + (['encode_ms'] if custom else [])
    fields(report,list(expected_report)+time_keys,'encoder report')
    for name in time_keys:
        number(report[name],name)
    same({k:v for k,v in report.items() if k not in time_keys}, expected_report,
         'encoder report derived fields mismatch')
