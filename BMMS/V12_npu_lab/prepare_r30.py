from pathlib import Path
import hashlib,json
r=Path(__file__).resolve().parents[1];o=r/'BMMS_V12';h=r/'V12_npu_lab/harness'
raw=(o/'v12_r26_dense_macro_consumer.asc').read_bytes().decode();a=raw.index('// BMMS1226_BEGIN');b=raw.index('// BMMS1226_END',a)+len('// BMMS1226_END')
mod=raw[a:b].replace('1226','1230')
mod=mod.replace('int32_t seq=0;bool cPending=false;', 'int32_t seq=0;bool cPending=false;\n    bool l1Prefetched=false;int l1Start=0;')
mod=mod.replace('void Macro(int group,int batch,int m0,int n0,int ar,int br){',
 'void Macro(int group,int batch,int m0,int n0,int ar,int br,int nextM,int nextN,int nextAr,int nextBr,bool hasNext){')
old='''        int l0Count=0;
        LoadStage(batch,m0,n0,ar,br,0,MinI(K1,p.K),0);
        for(int ki=0;ki<kCount;++ki){
            const int s1=ki&1,kBase=ki*K1,kr1=MinI(K1,p.K-kBase);'''
new='''        int l0Count=0;const int start=l1Start;
        if(!l1Prefetched)LoadStage(batch,m0,n0,ar,br,0,MinI(K1,p.K),start);
        l1Prefetched=false;
        for(int ki=0;ki<kCount;++ki){
            const int s1=(ki&1)^start,kBase=ki*K1,kr1=MinI(K1,p.K-kBase);'''
assert old in mod;mod=mod.replace(old,new)
old='''                LoadStage(batch,m0,n0,ar,br,nextK,MinI(K1,p.K-nextK),next);
            }
            for(int kk=0;kk<kr1;kk+=K0){'''
new='''                LoadStage(batch,m0,n0,ar,br,nextK,MinI(K1,p.K-nextK),next);
            }else if(hasNext){
                // While the final K1 slab computes, fill the other L1 slot with
                // the first slab of the next macro. Never overwrite current L1.
                const int next=s1^1;
                if(kCount>=2)AscendC::WaitFlag<AscendC::HardEvent::MTE1_MTE2>(l1Free[next]);
                LoadStage(batch,nextM,nextN,nextAr,nextBr,0,MinI(K1,p.K),next);
                l1Start=next;l1Prefetched=true;
            }
            for(int kk=0;kk<kr1;kk+=K0){'''
assert old in mod;mod=mod.replace(old,new)
old='''        for(int s=0;s<MinI(2,kCount);++s)AscendC::WaitFlag<AscendC::HardEvent::MTE1_MTE2>(l1Free[s]);'''
new='''        if(hasNext){
            // The other slot's old FREE was consumed before prefetch; its new
            // READY belongs to the next macro and must stay pending.
            const int last=((kCount-1)&1)^start;
            AscendC::WaitFlag<AscendC::HardEvent::MTE1_MTE2>(l1Free[last]);
        }else{
            for(int s=0;s<MinI(2,kCount);++s)
                AscendC::WaitFlag<AscendC::HardEvent::MTE1_MTE2>(l1Free[s^start]);
            l1Start=0;
        }'''
assert old in mod;mod=mod.replace(old,new)
old='''            for(int m0=mBegin;m0<mEnd;m0+=AM)for(int n0=nBegin;n0<nEnd;n0+=BN)
                Macro(group,batch,m0,n0,MinI(AM,mEnd-m0),MinI(BN,nEnd-n0));'''
new='''            for(int m0=mBegin;m0<mEnd;m0+=AM)for(int n0=nBegin;n0<nEnd;n0+=BN){
                const int nextM=n0+BN<nEnd?m0:m0+AM;
                const int nextN=n0+BN<nEnd?n0+BN:nBegin;
                const bool hasNext=nextM<mEnd;
                Macro(group,batch,m0,n0,MinI(AM,mEnd-m0),MinI(BN,nEnd-n0),
                    nextM,nextN,hasNext?MinI(AM,mEnd-nextM):0,hasNext?MinI(BN,nEnd-nextN):0,hasNext);
            }'''
assert old in mod;mod=mod.replace(old,new)
old='                AscendC::Max(merged,merged,tmp,p.M);bmms71::Fence<AscendC::HardEvent::V_MTE2>(*pipe_);'
new='''                // Explicit full vectors and tail; bounds remain visible to instrumentation.
                const int full=p.M/64,tail=p.M%64;
                const AscendC::BinaryRepeatParams rp{1,1,1,8,8,8};
                if(full)AscendC::Max(merged,merged,tmp,uint64_t(64),uint8_t(full),rp);
                if(tail)AscendC::Max(merged[full*64],merged[full*64],tmp[full*64],uint64_t(tail),uint8_t(1),rp);
                bmms71::Fence<AscendC::HardEvent::V_MTE2>(*pipe_);'''
assert old in mod;mod=mod.replace(old,new)
base=(o/'v12_baseline_r19.asc').read_bytes();module=('\n'+mod+'\n\n').encode();idx=base.index(b'extern "C" void run_kernel')
data=base[:idx]+module+base[idx:]
hook=b'    if(bmms1230::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
idx=data.index(b'    if(bmms11r2::TryLaunch(a,b,y,');data=data[:idx]+hook+data[idx:]
assert data.replace(module,b'',1).replace(hook,b'',1)==base
name='v12_r30_dense_macro_prefetch.asc';(o/name).write_bytes(data);(h/'r30.asc').write_bytes(data)
meta=dict(version='v12_r30',file=name,sha256=hashlib.sha256(data).hexdigest(),parent='v12_baseline_r19.asc',status='experimental; validation pending',
 change='r26 geometry, original grid; prefetch next macro first K1 slab during current final K1 slab, preserving double-buffer event ownership',
 L1_bytes=393216,L0A_bytes=32768,L0B_bytes=65536,L0C_bytes=131072,parent_byte_recovery=True)
(o/'v12_r30_manifest.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
(h/'event_bench_r30.asc').write_text((h/'event_bench_r26.asc').read_text(encoding='utf-8').replace('1226','1230'),encoding='utf-8',newline='\n')
cm=h/'CMakeLists.txt';t=cm.read_text(encoding='utf-8')
if 'add_executable(bench_r30 ' not in t:t+='\n'+t[t.index('add_executable(bench_r29 '):].replace('r29','r30')
cm.write_text(t,encoding='utf-8',newline='\n')
(h/'screen_r30.sh').write_text((h/'screen_r26.sh').read_text(encoding='utf-8').replace('r26','r30').replace('R26','R30'),encoding='utf-8',newline='\n')
print(json.dumps(meta))
