"""Case12 design audit. CPU only; no latency prediction or kernel execution."""
from pathlib import Path
import csv
import hashlib
import json
from statistics import median
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'V12_npu_lab/results/case12_redesign_20261001'
BASE = ROOT / 'BMMS_V12/v12_baseline_r41.asc'
PLANS = ROOT / 'V12_results/2026-10-01_case12_offline_review/compatible_plans.csv'
EXPECTED = '1caf7870ac4154c0f555621ba9c41f4601c6ecee96cb2e8d0bf23acc4fc4f373'

def ceildiv(x, y):
    return (x + y - 1) // y

def partition(length, unit, shards):
    units = ceildiv(length, unit)
    edges = [min(length, i * units // shards * unit) for i in range(shards + 1)]
    assert edges[0] == 0 and edges[-1] == length
    assert all(a < b for a, b in zip(edges, edges[1:]))
    return list(zip(edges, edges[1:]))

def metrics(M, N, cores, pm, pn, nunit, bn, resident):
    mranges, nranges = partition(M, 128, pm), partition(N, nunit, pn)
    tasks = []
    K = 1536
    for m0, m1 in mranges:
        for n0, n1 in nranges:
            mr, nr = m1 - m0, n1 - n0
            mt, nt = ceildiv(mr, 128), ceildiv(nr, bn)
            a = 2 * K * mr * nt
            b = 2 * K * nr * (1 if resident else mt)
            macros = mt * nt
            tasks.append(dict(cells=mr*nr, a=a, b=b, ab=a+b,
                              macros=macros, a_dma=macros*6,
                              b_dma_fill=nt*6 if resident else macros*6,
                              b_dma_preload=nt if resident else macros*6,
                              m_reuse=mt))
    assert len(tasks) == cores == pm * pn
    assert sum(t['cells'] for t in tasks) == M * N
    assert sum(t['b'] for t in tasks) == 2*K*N*(pm if resident else ceildiv(M,128))
    return dict(
        pM=pm, pN=pn, nunit=nunit,
        a_bytes=sum(t['a'] for t in tasks), b_bytes=sum(t['b'] for t in tasks),
        ab_bytes=sum(t['ab'] for t in tasks), peak_ab_bytes=max(t['ab'] for t in tasks),
        peak_cells=max(t['cells'] for t in tasks),
        c_macros=sum(t['macros'] for t in tasks), peak_macros=max(t['macros'] for t in tasks),
        mmads=24*sum(t['macros'] for t in tasks),
        a_dma=sum(t['a_dma'] for t in tasks), b_dma_fill=sum(t['b_dma_fill'] for t in tasks),
        b_dma_preload=sum(t['b_dma_preload'] for t in tasks),
        min_b_reuse=min(t['m_reuse'] for t in tasks), max_b_reuse=max(t['m_reuse'] for t in tasks),
        partial_bytes=4*pn*M, ring_capacity_bytes=cores*2*128*bn*4,
        useful_ring_roundtrip_bytes=8*M*N)

def flat_tasks(M,N,cores):
    mt,nt=ceildiv(M,128),ceildiv(N,128)
    total=mt*nt
    for g in range(cores):
        lo,hi=g*total//cores,(g+1)*total//cores
        runs=[]
        while lo<hi:
            n,m=divmod(lo,mt)
            end=min(hi,(n+1)*mt)
            runs.append((n*128,min((n+1)*128,N),m*128,min((end-n*mt)*128,M)))
            lo=end
        yield runs

def flat_metrics(M,N,cores):
    K=1536; tasks=[];reuse=[]
    for runs in flat_tasks(M,N,cores):
        a=b=cells=macros=0
        for n0,n1,m0,m1 in runs:
            count=ceildiv(m1-m0,128)
            a+=2*K*(m1-m0); b+=2*K*(n1-n0)
            cells+=(m1-m0)*(n1-n0); macros+=count;reuse.append(count)
        tasks.append(dict(a=a,b=b,cells=cells,macros=macros,runs=len(runs)))
    assert sum(t['cells'] for t in tasks)==M*N
    assert sum(t['macros'] for t in tasks)==ceildiv(M,128)*ceildiv(N,128)
    return dict(pM=0,pN=cores,nunit=128,
                a_bytes=sum(t['a'] for t in tasks),b_bytes=sum(t['b'] for t in tasks),
                ab_bytes=sum(t['a']+t['b'] for t in tasks),peak_ab_bytes=max(t['a']+t['b'] for t in tasks),
                peak_cells=max(t['cells'] for t in tasks),
                c_macros=sum(t['macros'] for t in tasks),peak_macros=max(t['macros'] for t in tasks),
                mmads=24*sum(t['macros'] for t in tasks),a_dma=6*sum(t['macros'] for t in tasks),
                b_dma_fill=6*sum(t['runs'] for t in tasks),b_dma_preload=sum(t['runs'] for t in tasks),
                min_b_reuse=min(reuse),max_b_reuse=max(reuse),
                partial_bytes=4*cores*M,ring_capacity_bytes=cores*2*128*128*4,
                useful_ring_roundtrip_bytes=8*M*N)

def audit_b_layout():
    """Independently compare whole-panel NZ packing and six incremental K fills."""
    K, checked = 1536, 0
    for br in range(16, 129, 16):
        raw = np.random.default_rng(br).integers(0, 65536, (K, br), dtype=np.uint16)
        expected = raw.reshape(K, br//16, 16).transpose(1,0,2).copy().reshape(-1)
        staged = np.empty(K*br, dtype=np.uint16)
        written = np.zeros(K*br, dtype=np.uint8)
        for k0 in range(0, K, 256):
            for n16 in range(br//16):
                dst = n16*K*16 + k0*16
                staged[dst:dst+256*16] = raw[k0:k0+256, n16*16:(n16+1)*16].reshape(-1)
                written[dst:dst+256*16] += 1
        assert np.all(written == 1) and np.array_equal(staged, expected)
        # Every logical K0 operand, as consumed by the full-K-stride L0B load.
        nz = staged.reshape(br//16,K,16)
        for k0 in range(0,K,64):
            reconstructed = nz[:,k0:k0+64,:].transpose(1,0,2).reshape(64,br)
            assert np.array_equal(reconstructed,raw[k0:k0+64,:])
            checked += 1
    return {'panel_widths':8, 'k0_operand_slices':checked, 'raw_uint16_exact':True}

def audit_semantics():
    """Small exact-integer oracle: complete K, max N shards, then sum M."""
    M,N,K,cores = 272,528,128,4
    rng = np.random.default_rng(5901)
    random_a=rng.integers(-3,4,(M,K),dtype=np.int64)
    random_b=rng.integers(-3,4,(K,N),dtype=np.int64)
    inputs=[(random_a, random_b),
            (np.ones((M,K),dtype=np.int64), -np.ones((K,N),dtype=np.int64)),
            (np.zeros((M,K),dtype=np.int64), random_b)]
    cancel_b=random_b.copy(); cancel_b[64:]=-cancel_b[:64]
    cancel_a=random_a.copy(); cancel_a[:,64:]=cancel_a[:,:64]
    inputs.append((cancel_a,cancel_b))
    tests=0
    for A,B in inputs:
        oracle=(A@B).max(axis=1)
        for pm in (1,2):
            pn=cores//pm
            for unit in (16,64,128):
                partial=np.full((pn,M),np.iinfo(np.int64).min,dtype=np.int64)
                writes=np.zeros((pn,M),dtype=np.uint8)
                for m0,m1 in partition(M,128,pm):
                    for ns,(n0,n1) in enumerate(partition(N,unit,pn)):
                        running=np.full(m1-m0,np.iinfo(np.int64).min,dtype=np.int64)
                        for n in range(n0,n1,128):
                            for m in range(m0,m1,128):
                                me,ne=min(m+128,m1),min(n+128,n1)
                                C=np.zeros((me-m,ne-n),dtype=np.int64)
                                for k in range(0,K,64):
                                    C += A[m:me,k:k+64]@B[k:k+64,n:ne]
                                running[m-m0:me-m0]=np.maximum(running[m-m0:me-m0], C.max(axis=1))
                        partial[ns,m0:m1]=running; writes[ns,m0:m1]+=1
                merged=partial.max(axis=0)
                assert np.all(writes==1) and np.array_equal(merged,oracle)
                assert merged.sum()==oracle.sum()
                tests+=1
        partial=np.full((cores,M),np.iinfo(np.int64).min,dtype=np.int64)
        covered=np.zeros((M,N),dtype=np.uint8)
        for g,runs in enumerate(flat_tasks(M,N,cores)):
            for n0,n1,m0,m1 in runs:
                for m in range(m0,m1,128):
                    me=min(m+128,m1)
                    C=np.zeros((me-m,n1-n0),dtype=np.int64)
                    for k in range(0,K,64):
                        C+=A[m:me,k:k+64]@B[k:k+64,n0:n1]
                    partial[g,m:me]=np.maximum(partial[g,m:me],C.max(axis=1))
                    covered[m:me,n0:n1]+=1
        assert np.all(covered==1) and np.array_equal(partial.max(axis=0),oracle)
        tests+=1
    return {'exact_integer_tiled_checks':tests,'distributions':['random','all_negative','zero','K_cancellation'],
            'scope':'Mathematical scheduling only; not NPU floating point or asynchronous-event validation.'}

def main():
    assert hashlib.sha256(BASE.read_bytes()).hexdigest()==EXPECTED
    source=list(csv.DictReader(PLANS.open(encoding='utf-8-sig')))
    rows=[]
    for s in source:
        M,N,cores,ta=[int(s[k]) for k in ('M','N','cores','TA')]
        old=metrics(M,N,cores,int(s['pM']),int(s['pN']),256,256,False)
        assert old['peak_cells']==int(s['peak_cells'])
        for pm in (1,2,4):
            if cores%pm: continue
            for unit in (16,64,128):
                new=metrics(M,N,cores,pm,cores//pm,unit,128,True)
                ratios={k+'_ratio':new[k]/old[k] for k in
                        ('a_bytes','b_bytes','ab_bytes','peak_ab_bytes','peak_cells','c_macros','partial_bytes')}
                ratios['dma_fill_ratio']=(new['a_dma']+new['b_dma_fill'])/(old['a_dma']+old['b_dma_fill'])
                rows.append(dict(kind='rectangular',M=M,N=N,cores=cores,TA=ta,**new,**ratios))
        new=flat_metrics(M,N,cores)
        ratios={k+'_ratio':new[k]/old[k] for k in
                ('a_bytes','b_bytes','ab_bytes','peak_ab_bytes','peak_cells','c_macros','partial_bytes')}
        ratios['dma_fill_ratio']=(new['a_dma']+new['b_dma_fill'])/(old['a_dma']+old['b_dma_fill'])
        rows.append(dict(kind='flat_n_major',M=M,N=N,cores=cores,TA=ta,**new,**ratios))
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/'MODEL.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    groups={}
    for pm in (1,2,4):
        for unit in (16,64,128):
            subset=[r for r in rows if r['pM']==pm and r['nunit']==unit and r['cores']==20]
            if not subset:continue
            groups[f'cores20_pm{pm}_unit{unit}']={'states':len(subset)}
            for k in ('ab_bytes_ratio','peak_ab_bytes_ratio','peak_cells_ratio','c_macros_ratio','dma_fill_ratio'):
                xs=[r[k] for r in subset]
                groups[f'cores20_pm{pm}_unit{unit}'][k]={'min':min(xs),'median':median(xs),'max':max(xs)}
    for cores in (20,22,24):
        subset=[r for r in rows if r['kind']=='flat_n_major' and r['cores']==cores]
        group={'states':len(subset)}
        for k in ('a_bytes_ratio','b_bytes_ratio','ab_bytes_ratio','peak_ab_bytes_ratio','peak_cells_ratio','c_macros_ratio','dma_fill_ratio'):
            xs=[r[k] for r in subset]; group[k]={'min':min(xs),'median':median(xs),'max':max(xs)}
        groups[f'flat_n_major_cores{cores}']=group
    examples=[]
    for N in (4096,4160,5120,6080):
        old=metrics(1280,N,20,10,2,256,256,False)
        examples.append(dict(N=N,baseline=old,candidates=[r for r in rows if r['cores']==20 and r['N']==N and r['TA']==0 and r['pM'] in (0,1,2)]))
    summary=dict(baseline_sha256=EXPECTED,plans_sha256=hashlib.sha256(PLANS.read_bytes()).hexdigest(),
                 source_states=len(source),candidate_states=len(rows),groups=groups,examples=examples,
                 layout_audit=audit_b_layout(),semantics_audit=audit_semantics(),
                 resources={'L1_KA256':1536*128*2+2*128*256*2,'L1_KA128':1536*128*2+2*128*128*2,
                            'L0A':2*128*64*2,'L0B':2*64*128*2,'L0C':2*128*128*4},
                 limitations=['CPU structural model only','Logical requested bytes, not HBM traffic',
                              'No measured latency, pipeline overlap, bank conflicts or compiler resource validation',
                              'Metadata states inherit the earlier real-host-planner extraction'])
    (OUT/'MODEL_SUMMARY.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps({k:summary[k] for k in ('source_states','candidate_states','layout_audit','semantics_audit','resources','groups')},indent=2))

if __name__=='__main__':main()
