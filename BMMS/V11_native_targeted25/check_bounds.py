"""Exhaust alignment/capacity, odd-shard tree coverage and small packet ownership."""
from pathlib import Path
import json
HERE=Path(__file__).resolve().parent
def main():
    capacity=0;peak=0;dma_max_ratio=0
    for M in range(48,8193,16):
        for pn in range(1,65):
            cap=min(M,(16384//pn//16)*16)
            assert cap>=16 and cap%16==0 and cap*pn<=16384
            ub=16384+32+16384+128+1024+M*8+cap*pn*4
            peak=max(peak,ub);assert ub<=192*1024
            calls=(M+cap-1)//cap;assert calls<=pn
            for m0 in range(0,M,cap):
                rows=min(cap,M-m0)
                assert rows%16==0 and m0%16==0 and (pn-1)*M+m0+rows<=M*pn
            capacity+=1;dma_max_ratio=max(dma_max_ratio,calls/pn)
    tree=0
    for pn in range(1,65):
        values=[{i} for i in range(pn)];active=pn;comparisons=0
        while active>1:
            pairs=active//2;keep=active-pairs
            for i in range(pairs):
                assert not(values[i]&values[keep+i]);values[i]|=values[keep+i]
            comparisons+=pairs;active=keep
        assert values[0]==set(range(pn)) and comparisons==pn-1;tree+=1
    packets=0
    for B in range(2,65):
        for cores in range(2,65):
            blocks=min(B,cores);seen=[]
            for group in range(blocks):
                batches=list(range(group,B,blocks));seen+=batches
                for start in range(0,len(batches),4):
                    count=min(4,len(batches)-start)
                    owners=[sum((seq%2)==sub for seq in range(start,start+count)) for sub in [0,1]]
                    assert owners==[(count+1)//2,count//2];packets+=1
            assert sorted(seen)==list(range(B))
    result={'dense_capacity_cases':capacity,'dense_UB_max_bytes':peak,'small_UB_max_bytes':32*32*4+32*8+32,
        'odd_even_tree_cases':tree,'small_packets':packets,'packed_DMA_count_never_exceeds_original':True,
        'assumptions':'Native metadata bounds, original 64x128 packet producer, pN<=64, float partials',
        'scope':'integer coverage and explicit allocation arithmetic, not compiler-allocated total or NPU performance'}
    (HERE/'BOUNDS_CHECKS.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
if __name__=='__main__':main()
