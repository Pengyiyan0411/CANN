"""Offline BMMS models and numerical review: NOT an AscendC/NPU execution.

Run: python V9_impl/test_semantics.py
The JSON separates mathematical/address assertions, modeled precision results,
and known counterexamples. A successful exit never means a device kernel passed.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "V9_design"))
from blocked_oracle import golden

DTYPES = ("float16", "bfloat16")
SHAPES = (
    (1, 1, 1, 32), (2, 2, 3, 40), (1, 15, 17, 64),
    (1, 16, 16, 256), (2, 32, 48, 288), (1, 64, 128, 256),
    (1, 80, 144, 320), (3, 17, 33, 72), (1, 2, 2, 1024),
    (1, 3, 5, 8192), (64, 2, 3, 32), (1, 65, 129, 40),
    (1, 1, 257, 256), (1, 257, 1, 256),
)


def stored(x, dtype):
    x = np.asarray(x, dtype=np.float32)
    if dtype == "float16":
        return x.astype(np.float16)
    if dtype != "bfloat16":
        raise ValueError(dtype)
    bits = x.view(np.uint32).copy()
    bits += np.uint32(0x7fff) + ((bits >> 16) & np.uint32(1))
    return ((bits >> 16).astype(np.uint16).astype(np.uint32) << 16).view(np.float32)


def physical(a, b, ta, tb):
    return (np.ascontiguousarray(a.swapaxes(1, 2) if ta else a),
            np.ascontiguousarray(b.swapaxes(1, 2) if tb else b))


def address_decode(ap, bp, shape, ta, tb):
    """Use the explicit flat address formulas, independently of swapaxes."""
    batch, m, n, k = shape
    bb = np.arange(batch, dtype=np.int64)[:, None, None]
    mm = np.arange(m, dtype=np.int64)[None, :, None]
    kk = np.arange(k, dtype=np.int64)[None, None, :]
    ao = bb*m*k + (kk*m+mm if ta else mm*k+kk)
    kk2 = np.arange(k, dtype=np.int64)[None, :, None]
    nn = np.arange(n, dtype=np.int64)[None, None, :]
    bo = bb*k*n + (nn*k+kk2 if tb else kk2*n+nn)
    assert ao.min() >= 0 and ao.max() < ap.size
    assert bo.min() >= 0 and bo.max() < bp.size
    return ap.reshape(-1)[ao], bp.reshape(-1)[bo]


def cut(length, pieces, quantum=1):
    assert length % quantum == 0
    count = length // quantum
    pieces = min(pieces, count)
    bounds = [i*count//pieces*quantum for i in range(pieces+1)]
    assert bounds[0] == 0 and bounds[-1] == length
    assert all(x < y for x, y in zip(bounds, bounds[1:]))
    return list(zip(bounds, bounds[1:]))


def partition_model(a, b):
    """FP64 M/N shards and Split-K, with FULL K merged before row max."""
    batch, m, k = a.shape
    n = b.shape[2]
    full_rows = np.full((batch, m), -np.inf, np.float64)
    visited = np.zeros((m, n), np.int16)
    for m0, m1 in cut(m, 3):
        for n0, n1 in cut(n, 4):
            cc = np.zeros((batch, m1-m0, n1-n0), np.float64)
            for k0, k1 in cut(k, 3, quantum=8):
                cc += a[:, m0:m1, k0:k1].astype(np.float64) @ b[:, k0:k1, n0:n1].astype(np.float64)
            full_rows[:, m0:m1] = np.maximum(full_rows[:, m0:m1], cc.max(2))
            visited[m0:m1, n0:n1] += 1
    assert np.all(visited == 1)
    return full_rows.sum(1, dtype=np.float64).astype(np.float32)


def assess(actual, reference):
    actual, reference = np.asarray(actual, np.float32), np.asarray(reference, np.float32)
    finite = bool(np.isfinite(actual).all() and np.isfinite(reference).all())
    if not finite:
        return dict(finite=False, strict=False, combined=False, max_abs=None, max_rel=None)
    absolute = np.abs(actual.astype(np.float64)-reference.astype(np.float64))
    relative = np.divide(absolute, np.abs(reference), out=np.full_like(absolute, np.inf), where=reference != 0)
    relative[(reference == 0) & (absolute == 0)] = 0
    relmax = float(relative.max(initial=0))
    return dict(finite=True, strict=bool(np.all(absolute<1e-4) and np.all(relative<1e-4)),
                combined=bool(np.all(absolute<=1e-4+1e-4*np.abs(reference))),
                max_abs=float(absolute.max(initial=0)), max_rel=relmax if np.isfinite(relmax) else "Inf")


def two_sum(a, b):
    a, b = np.float32(a), np.float32(b)
    s = np.float32(a+b)
    bp = np.float32(s-a)
    e = np.float32(np.float32(a-np.float32(s-bp)) + np.float32(b-bp))
    return s, e


def pair_add(hi, lo, x):
    s, error = two_sum(hi, x)
    return two_sum(s, np.float32(lo+error))


def pair_merge(hi, lo, xhi, xlo):
    hi, lo = pair_add(hi, lo, xhi)
    return pair_add(hi, lo, xlo)


def chunk_lanes(x, y):
    assert len(x) <= 256
    hi = np.zeros(256, np.float32)
    hi[:len(x)] = np.asarray(x, np.float32)*np.asarray(y, np.float32)
    lo = np.zeros_like(hi)
    size = 256
    while size > 8:
        half = size//2
        # bmms8::PairAccumulate style tree; add the right low components too.
        left, error = two_sum(hi[:half], hi[half:size])
        lo[:half] = np.float32(np.float32(lo[:half]+error)+lo[half:size])
        hi[:half] = left
        size = half
    return hi[:8], lo[:8]


def splitk_pair_model(a, b, splits=3):
    """Planned S arithmetic: normalized pairs through Max and final M Sum.

    NumPy FP32 operations model the specified operations, not device reduction
    instructions, compiler reassociation, FTZ, memory ordering, or performance.
    """
    batch, m, k = a.shape
    n = b.shape[2]
    out = np.empty(batch, np.float32)
    for bi in range(batch):
        yh, yl = np.float32(0), np.float32(0)
        for mi in range(m):
            best = None
            for ni in range(n):
                ch, cl = np.float32(0), np.float32(0)
                for k0, k1 in cut(k, splits, quantum=8):
                    ph, pl = np.float32(0), np.float32(0)
                    for start in range(k0, k1, 256):
                        stop = min(start+256, k1)
                        hi, lo = chunk_lanes(a[bi, mi, start:stop], b[bi, start:stop, ni])
                        # Exact source grouping: the eight lanes feed taskPair
                        # directly; no intermediate independently-rounded blockPair.
                        for lane in range(8):
                            ph, pl = pair_merge(ph, pl, hi[lane], lo[lane])
                    ch, cl = pair_merge(ch, cl, ph, pl)
                if best is None or ch > best[0] or (ch == best[0] and cl > best[1]):
                    best = (ch, cl)
            yh, yl = pair_merge(yh, yl, *best)
        out[bi] = np.float32(yh+yl)
    return out


def counterexamples():
    items = []
    # These powers are exact in FP16 AND BF16 and lie inside the proposed S domain.
    for dtype in DTYPES:
        a = np.zeros((1, 2, 1024), np.float32)
        b = np.zeros((1, 1024, 2), np.float32)
        a[0, 0, :2] = (64, 2**-6)
        a[0, 1, 0] = -64
        b[0, 0, :] = 64
        b[0, 1, :] = 2**-7
        a, b = stored(a, dtype), stored(b, dtype)
        ref = golden(a, b)
        c = (a.astype(np.float64) @ b.astype(np.float64)).astype(np.float32)
        lost = c.max(2).sum(1, dtype=np.float64).astype(np.float32)
        accurate = splitk_pair_model(a, b, splits=1)
        assert ref[0] == np.float32(2**-13) and lost[0] == 0
        assert not assess(lost, ref)["combined"]
        assert np.array_equal(accurate.view(np.uint32), ref.view(np.uint32))
        items.append(dict(name="S_domain_dot_low_bits", dtype=dtype, shape=[1,2,2,1024],
                          golden=ref.tolist(), fp32_c_output=lost.tolist(),
                          fp32_c_assessment=assess(lost, ref), pair_model_output=accurate.tolist(),
                          pair_model_assessment=assess(accurate, ref)))
        # Different best lows share the same rounded high. Put the residual in
        # the final 8-term K tail, distinct from the large first K contribution.
        a = np.zeros((1,2,4104), np.float32)
        b = np.zeros((1,4104,2), np.float32)
        a[0,0,0],a[0,1,0],a[0,0,-1] = 64,-64,2**-6
        b[0,0,:] = 64
        b[0,-1,:] = (2**-7,2**-6)
        a,b=stored(a,dtype),stored(b,dtype)
        ref=golden(a,b)
        accurate=splitk_pair_model(a,b,splits=4)
        assert ref[0] == np.float32(2**-12)
        assert np.array_equal(accurate.view(np.uint32),ref.view(np.uint32))
        items.append(dict(name="S_pair_Max_low_tie_and_K8_tail",dtype=dtype,shape=[1,2,2,4104],
                          golden=ref.tolist(),pair_model_output=accurate.tolist(),
                          pair_model_assessment=assess(accurate,ref)))
        # Two FP32 components are not an exact accumulator. At hi=2^30,lo=64,
        # adding 2^-18 rounds the LOW component back to 64 (half-ULP tie).
        a=np.zeros((1,32,1024),np.float32)
        b=np.zeros((1,1024,2),np.float32)
        a[0,:,:5]=[32768,8,2**-9,-32768,-8]
        b[0,:5,:]=np.array([32768,8,2**-9,32768,8],np.float32)[:,None]
        a,b=stored(a,dtype),stored(b,dtype)
        ref=golden(a,b)
        actual=splitk_pair_model(a,b,splits=1)
        assert ref[0]==np.float32(2**-13) and actual[0]==0
        assert not assess(actual,ref)["combined"]
        items.append(dict(name="S_two_component_residual_loss",dtype=dtype,shape=[1,32,2,1024],
                          golden=ref.tolist(),pair_model_output=actual.tolist(),
                          pair_model_assessment=assess(actual,ref),
                          expected_limitation=True,
                          construction="A rows [32768,8,2^-9,-32768,-8]; B columns [32768,8,2^-9,32768,8]; remaining K zero"))
    # Same mechanism in the proposed D domain; repeat a two-row mathematical pair.
    pair = np.array([1+2**-25, -1], np.float64)
    ref = np.float32(pair.sum()*4096)
    lost = np.float32(pair.astype(np.float32).astype(np.float64).sum()*4096)
    items.append(dict(name="D_domain_dot_low_bits", dtype="float16_or_bfloat16",
                      shape=[1,8192,16,256], construction="k0,k1 nonzero; remaining K padded with zero",
                      golden=float(ref), fp32_c_output=float(lost),
                      assessment=assess([lost], [ref]), execution="two-row exact repeat, no large tensor"))
    assert not items[-1]["assessment"]["combined"]
    wrong_n = np.array([[10.,9.],[9.,10.]])
    wrong_k = np.array([[10.,0.],[-10.,1.]])
    assert wrong_n.max(1).sum() == 20 and wrong_n.sum(0).max() == 19
    assert wrong_k.sum(0).max() == 1 and wrong_k.max(1).sum() == 11
    items.append(dict(name="N_scalar_and_K_early_Max_rejected", correct_N=20, wrong_N=19,
                      correct_K=1, wrong_K=11))
    a=np.zeros((1,2,1024),np.float32)
    b=np.zeros((1,1024,2),np.float32)
    a[0,:,:2]=np.float32(2**64)
    b[0,0,:]=np.float32(2**64)
    b[0,1,:]=np.float32(-2**64)
    a,b=stored(a,"bfloat16"),stored(b,"bfloat16")
    ref=golden(a,b)
    with np.errstate(over="ignore",invalid="ignore"):
        actual=splitk_pair_model(a,b,splits=1)
    assert ref[0]==0 and not np.isfinite(actual).all()
    items.append(dict(name="S_finite_BF16_products_overflow_despite_finite_golden",dtype="bfloat16",
                      shape=[1,2,2,1024],golden=ref.tolist(),pair_model_output=["NaN"],
                      pair_model_assessment=assess(actual,ref),expected_limitation=True,
                      construction="A k0=k1=2^64; B k0=2^64,k1=-2^64; remaining K zero"))
    return items


def dense_plan_checks():
    """Check current D plan/row ownership and scalar event-credit counts.

    Credit arithmetic is only a necessary condition. It cannot prove hardware
    pipeline completion, cross-core flag semantics, cache visibility, or liveness.
    """
    checked, tiles, virtual_waves, nsplit_plans, kstage_checks = 0, 0, 0, 0, 0
    k_tails=set()
    shapes = ((1,16,16,256), (1,48,144,288), (2,80,528,1024),
              (3,272,48,256), (64,16,16,8192), (1,8192,16,256),
              (1,16,528,352), (1,48,144,320), (1,64,528,416))
    for batch,m,n,k in shapes:
        for cores in (1,2,7,20,64):
            mt, nt = (m+63)//64, (n+127)//128
            pm = min(mt,max(1,(cores+batch-1)//batch))
            pn=min(nt,max(1,(cores+batch*pm-1)//(batch*pm)))
            tasks, blocks = batch*pm*pn, min(cores,batch*pm*pn)
            seen = set()
            partial_writes = np.zeros((batch,pn,m),np.int16)
            for group in range(blocks):
                sequence = 0
                for task in range(group,tasks,blocks):
                    bi, slot = divmod(task,pm*pn)
                    ms,ns=divmod(slot,pn)
                    mbeg, mend = ms*mt//pm*64, min((ms+1)*mt//pm*64,m)
                    nbeg, nend = ns*nt//pn*128,min((ns+1)*nt//pn*128,n)
                    assert mbeg < mend and nbeg<nend
                    for mbase in range(mbeg,mend,256):
                        ar = min(256,mend-mbase)
                        for nbase in range(nbeg,nend,512):
                            br = min(512,nend-nbase)
                            for mo in range(0,ar,64):
                                mr = min(64,ar-mo)
                                assert mr%16 == 0
                                for no in range(0,br,128):
                                    nr = min(128,br-no)
                                    m0,n0 = mbase+mo,nbase+no
                                    key = (bi,m0,n0)
                                    assert key not in seen
                                    seen.add(key)
                                    assert 0<nr<=128 and nr%16 == 0
                                    for sub in (0,1):
                                        vr=mr//2
                                        row0=sub*vr
                                        ring0=(group*2+sequence%2)*64*128+row0*128
                                        ring_end=ring0+(vr-1)*128+nr
                                        assert (group*2+sequence%2)*64*128<=ring0<ring_end<=(group*2+sequence%2+1)*64*128
                                        assert vr%8 == 0 and row0+vr<=mr
                                    sequence += 1
                        for mo in range(0,ar,64):
                            mr=min(64,ar-mo)
                            for sub in (0,1):
                                vr=mr//2
                                start=mbase+mo+sub*vr
                                partial_writes[bi,ns,start:start+vr]+=1
                assert sequence>0
            expected={(bi,mi,ni) for bi in range(batch) for mi in range(0,m,64) for ni in range(0,n,128)}
            assert seen == expected and np.all(partial_writes==1)
            for kb in (64,128):
                spans=[(start,min(start+kb,k)) for start in range(0,k,kb)]
                assert sum(stop-start for start,stop in spans)==k
                assert all((stop-start)%32==0 and 0<stop-start<=kb for start,stop in spans)
                k_tails.update(stop-start for start,stop in spans)
                # Count l1/l0 credits consumed by the current two-stage schedule.
                l1,l0=[0,0],[0,0]
                for ki in range(len(spans)):
                    stage=ki%2
                    if ki+1<len(spans) and ki>=1:
                        nxt=stage^1
                        assert l1[nxt]==1
                        l1[nxt]-=1
                    if ki>=2:
                        assert l0[stage]==1
                        l0[stage]-=1
                    l1[stage]+=1
                    l0[stage]+=1
                    assert max(l1)<=1 and max(l0)<=1
                assert l1==[1,1] and l0==[1,1]
                kstage_checks+=1
            checked+=1
            tiles+=len(seen)
            virtual_waves+=int(tasks>blocks)
            nsplit_plans+=int(pn>1)
    return dict(plans=checked,unique_output_tiles=tiles,tasks_exceeding_workers_plans=virtual_waves,
                nsplit_plans=nsplit_plans,kstage_credit_checks=kstage_checks,k_blocks=[64,128],
                actual_k_stage_extents=sorted(k_tails),
                row_ownership=True,ring_bounds=True,k_coverage=True,scalar_event_credit_counts=True,
                shared_consumer_ub_explicit_bytes=132256,
                producer_resources={str(kb):dict(L1_bytes=2*(64+128)*kb*2,
                                                L0A_bytes=2*64*kb*2,L0B_bytes=2*128*kb*2,
                                                L0C_bytes=64*128*4) for kb in (64,128)},
                limitation="host schedule/resource arithmetic only; no hardware flags or API semantics simulated")


def run():
    rng = np.random.default_rng(290927)
    bf16_ties=stored(np.array([1+2**-8,1+3*2**-8,-1-2**-8,-1-3*2**-8],np.float32),"bfloat16")
    assert np.array_equal(bf16_ties,np.array([1,1+2**-6,-1,-1-2**-6],np.float32))
    cases, pair_checks = [], []
    for si, shape in enumerate(SHAPES):
        batch, m, n, k = shape
        assert k%8 == 0 and 32<=k<=8192 and max(batch*m*k,batch*n*k)<=2**26
        for profile in ("signed_random", "all_negative_similarity"):
            raw_a = rng.uniform(-0.3, 0.3, (batch,m,k)).astype(np.float32)
            raw_b = rng.uniform(-0.3, 0.3, (batch,k,n)).astype(np.float32)
            if profile == "all_negative_similarity":
                raw_a = np.abs(raw_a)+np.float32(0.01)
                raw_b = -(np.abs(raw_b)+np.float32(0.01))
            for dtype in DTYPES:
                a, b = stored(raw_a, dtype), stored(raw_b, dtype)
                reference = golden(a,b,m_block=31,n_block=47)
                for ta in (False, True):
                    for tb in (False, True):
                        ap, bp = physical(a,b,ta,tb)
                        before = hashlib.sha256(ap.tobytes()+bp.tobytes()).hexdigest()
                        aa, bb = address_decode(ap,bp,shape,ta,tb)
                        assert np.array_equal(aa,a) and np.array_equal(bb,b)
                        logical_result = partition_model(aa,bb)
                        assert np.array_equal(logical_result.view(np.uint32),reference.view(np.uint32))
                        assert np.array_equal(golden(ap,bp,ta,tb).view(np.uint32),reference.view(np.uint32))
                        cc = (aa.astype(np.float64)@bb.astype(np.float64)).astype(np.float32)
                        ideal_fp32_c = cc.max(2).sum(1,dtype=np.float32)
                        assert hashlib.sha256(ap.tobytes()+bp.tobytes()).hexdigest() == before
                        cases.append(dict(id=f"s{si}_{profile}_{dtype}_{int(ta)}{int(tb)}",
                                          shape=list(shape),dtype=dtype,ta=ta,tb=tb,profile=profile,
                                          address_and_partition_semantics=True,
                                          ideal_single_fp32_c=assess(ideal_fp32_c,reference)))
                        if (not ta) and tb and batch<=3 and m*n<=16 and k>=1024:
                            splits=max(1,min((40+batch*m*n-1)//(batch*m*n),k//1024))
                            actual = splitk_pair_model(aa,bb,splits=splits)
                            check = assess(actual,reference)
                            pair_checks.append(dict(case_id=cases[-1]["id"],cores=20,splits=splits,**check))
                            assert check["strict"], pair_checks[-1]
    assert len(cases)>=64
    evidence = dict(scope="CPU address/mathematical/numerical models; not source execution or NPU tests",
                    dtype_storage="FP16 stored arrays; BF16 round-to-nearest-even uint16 encoding decoded to FP32",
                    model_cases=len(cases),shapes=len(SHAPES),dtypes=list(DTYPES),layouts=4,profiles=2,
                    mathematical_assertions="passed",cases=cases,splitk_pair_checks=pair_checks,
                    known_counterexamples=counterexamples(),
                    dense_plan_checks=dense_plan_checks(),
                    device_compiled=False,device_executed=False,
                    source_fragments={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                                      for p in Path(__file__).parent.glob("*_fragment.asc")},
                    precision_note="FP32 C precision failures are retained; pair-model passes are not whole-domain guarantees")
    evidence["ordinary_fp32_c_strict_failures"] = sum(not c["ideal_single_fp32_c"]["strict"] for c in cases)
    evidence["ordinary_fp32_c_combined_failures"] = sum(not c["ideal_single_fp32_c"]["combined"] for c in cases)
    evidence["known_current_splitk_model_precision_failures"] = sum(
        bool(c.get("expected_limitation")) for c in evidence["known_counterexamples"])
    evidence["candidate_precision_accepted"] = False
    evidence["exit_zero_means"] = "model assertions and expected failures reproduced, NOT candidate/device precision acceptance"
    target = Path(__file__).with_name("semantics_results.json")
    target.write_text(json.dumps(evidence,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in evidence.items() if k not in ("cases","splitk_pair_checks","known_counterexamples")},
                     ensure_ascii=False,indent=2))
    print(f"SplitK pair checks: {len(pair_checks)}; results: {target}")


if __name__ == "__main__":
    run()
