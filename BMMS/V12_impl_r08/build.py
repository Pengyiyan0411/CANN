"""r08: native narrow-N local sum, reducing GM row traffic and final fan-in."""
from pathlib import Path
import hashlib
import importlib.util
import json

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'BMMS_V12';BASE=OUT/'v12_baseline_r03.asc'
SHA='1c9e9726aa43fdd177c98c645c69bb7d57721d2f1b07d00dfb614324286a404c'
spec=importlib.util.spec_from_file_location('helpers',ROOT/'V12_impl_r02_r03/build.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)


def module(src):
    start=src.index('// BMMS49_BEGIN');end=src.index('// BMMS49_END',start)+len('// BMMS49_END')
    s=src[start:end].replace('bmms49','bmms1208').replace('BMMS49','BMMS1208')
    s=s.replace('NarrowPacketConsumer','LocalSumConsumer')
    s=s.replace('p.pN==1&&p.blocks>1;', 'p.pN==1&&p.blocks>1&&p.tasks==p.blocks;')
    s=s.replace('// Original producer, M partition, 4-tile packet and partial layout are retained.\n// With one complete N<=64 panel, load valid columns compactly and reduce directly.',
'''// Producer, partition and packet sequence are unchanged. Every AIV owns
// all N columns for its rows. Reduce those rows locally, then merge 2*blocks
// scalar partial sums after the existing barrier. Sum order changes only.
// Single-wave guard guarantees exactly one M shard per physical group.''')
    s=s.replace('pipe->InitBuffer(runningBuf,AM*4);pipe->InitBuffer(mergedBuf,p.M*4);pipe->InitBuffer(sumBuf,p.M*4);',
'''const int maxRows=((p.mTiles+p.pM-1)/p.pM)*TM/2;
        const int partialWords=2*p.blocks*8;
        pipe->InitBuffer(runningBuf,maxRows*4);pipe->InitBuffer(mergedBuf,partialWords*4);
        pipe->InitBuffer(sumBuf,(maxRows>partialWords?maxRows:partialWords)*4);''')
    s=s.replace('int seq=0;auto run=runningBuf.Get<float>();','int seq=0,localCount=0;auto run=runningBuf.Get<float>();')
    s=s.replace('const int mBegin=(task*p.mTiles/p.pM)*TM,mEnd=MinI(((task+1)*p.mTiles/p.pM)*TM,p.M);',
'''const int mBegin=(task*p.mTiles/p.pM)*TM,mEnd=MinI(((task+1)*p.mTiles/p.pM)*TM,p.M);
            localCount=(mEnd-mBegin)/2;''')
    s=s.replace('WholeReduceMax(run[mo+sub*vr]', 'WholeReduceMax(run[(mBase-mBegin+mo)/2]')
    start=s.index('                bmms71::Fence<AscendC::HardEvent::V_MTE3>')
    end=s.index('            }\n        }\n        if(seq%PACKET_TILES)',start)
    s=s[:start]+s[end:]
    anchor='        bmms71::Fence<AscendC::HardEvent::MTE3_MTE2>(*pipe_);AscendC::SyncAll<true>();'
    s=s.replace(anchor,'''        // Eight-word slots are disjoint and aligned. Only the valid scalar
        // is stored/read; the final DMA explicitly supplies seven zero lanes.
        // No atomic add, and no incomplete-K or incomplete-N partial max.
        auto scalar=oq.AllocTensor<float>();
        AscendC::ReduceSum(scalar,run,sumBuf.Get<float>(),localCount);
        oq.EnQue(scalar);scalar=oq.DeQue<float>();
        AscendC::DataCopyExtParams sp{1,4,0,0,0};
        AscendC::DataCopyPad(part[worker*8],scalar,sp);oq.FreeTensor(scalar);
'''+anchor)
    s=s.replace('AscendC::DataCopyExtParams mp{1,uint32_t(p.M*4),0,0,0};',
                'AscendC::DataCopyExtParams mp{static_cast<uint16_t>(2*p.blocks),4,28,0,0};')
    s=s.replace('AscendC::DataCopyPadExtParams<float> pd{false,0,0,0.0f};\n            AscendC::DataCopyPad(merged,part,mp,pd);',
                'AscendC::DataCopyPadExtParams<float> pd{true,0,7,0.0f};\n            AscendC::DataCopyPad(merged,part,mp,pd);')
    s=s.replace('AscendC::ReduceSum(yy,merged,sumBuf.Get<float>(),p.M);',
                'AscendC::ReduceSum(yy,merged,sumBuf.Get<float>(),2*p.blocks*8);')
    return s+'\n\n'


def main():
    raw=BASE.read_bytes();assert hashlib.sha256(raw).hexdigest()==SHA
    fragment=module(raw.decode().replace('\r\n','\n')).encode()
    anchor=b'extern "C" void run_kernel(GM_ADDR a,const TensorGroupInfo& ia,'
    # The same NativePlan and all previous route checks have already run here.
    marker=b'        if(bmms49::TryLaunch(a,b,y,p,x.dtype,ta,tb,stream))return;'
    assert raw.count(marker)==1
    hook=b'        if(bmms1208::TryLaunch(a,b,y,p,x.dtype,ta,tb,stream))return;\r\n'
    data=raw.replace(anchor,fragment+anchor,1).replace(marker,hook+marker,1)
    assert data.replace(fragment,b'',1).replace(hook,b'',1)==raw
    target=OUT/'v12_r08_native_local_sum.asc';target.write_bytes(data)
    (ROOT/'V12_npu_lab/harness/r08.asc').write_bytes(data)
    # Audit exact shard partition and dense private row mapping. We enumerate
    # legal single-wave plans, not just the particular cost function's choices.
    plans=0
    for M in range(272,8193,16):
        tiles=(M+63)//64
        for pm in range(2,min(tiles,64)+1):
            assert 2*pm*8<=M
            covered=[]
            for group in range(pm):
                begin=(group*tiles//pm)*64;end=min(((group+1)*tiles//pm)*64,M)
                for sub in range(2):
                    private=[];logical=[]
                    for mb in range(begin,end,256):
                        for mo in range(0,min(256,end-mb),64):
                            vr=min(64,end-mb-mo)//2
                            private.extend(range((mb-begin+mo)//2,(mb-begin+mo)//2+vr))
                            logical.extend(range(mb+mo+sub*vr,mb+mo+(sub+1)*vr))
                    assert private==list(range((end-begin)//2))
                    covered.extend(logical)
            assert sorted(covered)==list(range(M));plans+=1
    report=dict(candidate=target.name,sha256=hashlib.sha256(data).hexdigest(),parent=BASE.name,
                parent_sha256=SHA,parent_recovered_byte_for_byte=True,partition_checks=plans,
                producer_and_grid_unchanged=True,sum_order_changed=True,
                scope='Host partition/address audit; device validation pending.')
    (OUT/'v12_r08_manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
