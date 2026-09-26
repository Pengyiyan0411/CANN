"""Offline design checks only. Does not compile or execute an Ascend kernel."""
from pathlib import Path
import hashlib
import itertools
import json
import math

ROOT = Path(__file__).resolve().parent
DTYPES = ('float16', 'bfloat16')
LAYOUTS = tuple(itertools.product((False, True), repeat=2))
REGULAR = [
    ('dot', (1, 1, 1, 32)), ('resident', (2, 4, 8, 64)),
    ('native_control', (1, 64, 128, 128)), ('dense_k256', (1, 64, 128, 256)),
    ('dense_k1024', (1, 64, 128, 1024)), ('small_output', (1, 8, 8, 8192)),
    ('n1', (1, 65, 1, 128)), ('m1', (1, 1, 65, 128)),
]
GENERAL = [
    ('tail_k40', (1, 17, 33, 40)), ('tail_k72', (2, 63, 129, 72)),
    ('tail_k136', (1, 65, 257, 136)), ('low_occupancy', (1, 16, 16, 4096)),
    ('small_output_border', (1, 32, 64, 1024)), ('batch3', (3, 192, 768, 128)),
    ('batch20', (20, 64, 128, 256)), ('batch21', (21, 64, 128, 256)),
    ('batch64', (64, 1, 1, 32)), ('max_m', (1, 8192, 16, 32)),
    ('max_n', (1, 16, 8192, 32)), ('input_limit_dense', (1, 8192, 8192, 8192)),
    ('input_limit_batch', (64, 128, 128, 8192)), ('long_m1', (1, 1, 8192, 256)),
    ('long_n1', (1, 8192, 1, 256)), ('split_k_tail', (1, 7, 9, 8184)),
]
PATTERNS = [
    ('all_negative', (1, 17, 33, 40)), ('all_zero', (1, 17, 33, 40)),
    ('equal_max', (1, 17, 33, 40)), ('near_tie', (1, 17, 33, 40)),
    ('dot_rounding_loss', (1, 8192, 16, 256)), ('n_split_crossing', (1, 2, 2, 32)),
    ('k_split_crossing', (1, 2, 2, 64)), ('normalized_random', (2, 31, 65, 136)),
]
PERF = [
    ('native_control', (1, 512, 1024, 128)), ('dense_medium_k', (1, 512, 1024, 256)),
    ('dense_large_k', (1, 512, 1024, 1024)), ('dense_very_large_k', (1, 128, 256, 4096)),
    ('wide_low_batch', (1, 64, 4096, 256)), ('tail_dense', (1, 257, 513, 264)),
    ('small_output_large_k', (1, 8, 8, 8192)), ('strided_gemv', (1, 1, 4096, 1024)),
]


def write_json(name, value):
    (ROOT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def legal(shape):
    b, m, n, k = shape
    return (1 <= b <= 64 and 1 <= m <= 8192 and 1 <= n <= 8192
            and 32 <= k <= 8192 and k % 8 == 0 and b*m*k <= 2**26 and b*n*k <= 2**26)


def expand(entries, category):
    out = []
    for name, shape in entries:
        assert legal(shape), shape
        b, m, n, k = shape
        for dtype in DTYPES:
            for ta, tb in LAYOUTS:
                out.append(dict(id=f'{category}_{name}_{dtype}_{int(ta)}{int(tb)}',
                    category=category, family=name, logical_shape=list(shape), dtype=dtype,
                    transpose_x1=ta, transpose_x2=tb,
                    x1_storage=[b, k, m] if ta else [b, m, k],
                    x2_storage=[b, n, k] if tb else [b, k, n],
                    pattern=name if category == 'pattern' else 'signed_random', seed=20260926,
                    stress_only=b*m*k > 2**23 or b*n*k > 2**23,
                    device_status='NOT_RUN'))
    return out


def jsonl(name, rows):
    (ROOT / name).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')


def resources():
    capacities = dict(L1=512*1024, L0A=64*1024, L0B=64*1024, L0C=128*1024, UB=192*1024)
    # M/N equality is required by v1.4.0 Pingpong. L0C is SINGLE buffered.
    configs = [(32,64,128,32), (64,128,256,64), (128,128,128,64),
               (64,256,128,64), (128,256,128,64), (64,128,512,64)]
    rows = []
    for m, n, k1, k0 in configs:
        v = m//2
        # Conservative: two input tiles, scratch tile, three full-M merge arrays,
        # row vectors + 8 KiB API scratch reserve, and aligned scalar output.
        ub = 2*v*n*4 + v*n*4 + 3*8192*4 + 2*m*4 + 8192 + 32
        live = dict(L1=2*(m+n)*k1*2, L0A=2*m*k0*2,
                    L0B=2*n*k0*2, L0C=m*n*4, UB=ub)
        violations = [p for p in live if live[p] > capacities[p]]
        rows.append(dict(L1_shape=[m,n,k1], L0_shape=[m,n,k0], stages_L1_AB=2,
            stages_L0_AB=2, stages_L0C=1, live_bytes=live,
            capacity_bytes=capacities, violations=violations,
            raw_resource_fit=not violations,
            note='Arithmetic only; API scratch/alignment and compiler allocation still require verification.'))
    write_json('resource_candidates.json', rows)
    return rows


def partitions():
    count = 0
    for mtiles in (1,2,3,5,7,8,16,31,64,128):
        for ntiles in (1,2,3,4,7,16,32,64):
            for pm in range(1, min(mtiles,20)+1):
                for pn in range(1, min(ntiles,20)+1):
                    ms = [(s*mtiles//pm,(s+1)*mtiles//pm) for s in range(pm)]
                    ns = [(s*ntiles//pn,(s+1)*ntiles//pn) for s in range(pn)]
                    assert all(e > s for s,e in ms+ns)
                    assert sum(e-s for s,e in ms) == mtiles
                    assert sum(e-s for s,e in ns) == ntiles
                    assert all(ms[i][1] == ms[i+1][0] for i in range(pm-1))
                    assert all(ns[i][1] == ns[i+1][0] for i in range(pn-1))
                    count += 1
    return count


def main():
    cases = expand(REGULAR, 'regular') + expand(GENERAL, 'general') + expand(PATTERNS, 'pattern')
    perf = expand(PERF, 'perf')
    # A small contrast set, not a replacement for 4-layout validation.
    screen = [r for r in perf if (r['dtype'],r['transpose_x1'],r['transpose_x2']) in
              [('float16',False,False),('bfloat16',True,True)]]
    smoke_names = {'dense_k256','tail_k40','small_output','all_negative'}
    smoke = [r for r in cases if r['family'] in smoke_names]
    assert len({r['id'] for r in cases}) == len(cases)
    for r in cases + perf:
        b,m,n,k = r['logical_shape']
        x,z = r['x1_storage'],r['x2_storage']
        assert (x[0], x[2] if r['transpose_x1'] else x[1],
                x[1] if r['transpose_x1'] else x[2]) == (b,m,k)
        assert (z[0], z[2] if r['transpose_x2'] else z[1],
                z[1] if r['transpose_x2'] else z[2]) == (b,k,n)
    jsonl('precision_cases.jsonl', cases)
    jsonl('smoke_cases.jsonl', smoke)
    jsonl('perf_cases.jsonl', perf)
    jsonl('perf_screen.jsonl', screen)
    resource_rows = resources()
    result = dict(status='OFFLINE_DESIGN_CHECKS_ONLY', device_tests=0, kernel_compilations=0,
                  precision_cases=len(cases), smoke_cases=len(smoke), perf_cases=len(perf),
                  perf_screen_cases=len(screen), shape_contract_checks=len(cases)+len(perf),
                  partition_configurations=partitions(), resource_candidates=len(resource_rows),
                  raw_resource_fit=sum(r['raw_resource_fit'] for r in resource_rows))
    historical = json.loads((ROOT.parent/'next_stage/c01_judge_result/result.json').read_text(encoding='utf-8-sig'))
    rows = historical['rows']
    def score(ts):
        return sum(100/(1+math.log(t/r['historical_best_us'],1.5)) for t,r in zip(ts,rows))/len(rows)
    p01 = [r['p01_us'] for r in rows]
    scenarios = dict(P01=score(p01), C01=score([r['latency_us'] for r in rows]),
        restore_case15_v7_only=score(p01[:-1]+[29.38]),
        hypothetical_all_20_percent_faster=score([max(t*0.8,r['historical_best_us']) for t,r in zip(p01,rows)]))
    write_json('score_scenarios.json', dict(note='Frozen historical T; scenarios are arithmetic, not predictions.', values=scenarios))
    write_json('offline_checks.json',result)
    # Freeze inputs for eventual on-device A/B.
    paths = ['precision_cases.jsonl','smoke_cases.jsonl','perf_cases.jsonl','perf_screen.jsonl','resource_candidates.json']
    hashes = {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
    hashes['../next_stage/C00_P01_CONTROL.asc'] = hashlib.sha256((ROOT.parent/'next_stage/C00_P01_CONTROL.asc').read_bytes()).hexdigest()
    write_json('manifest.json',hashes)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(scenarios,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
