from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1];v=root/'BMMS_V12';lab=root/'V12_npu_lab/rethink_20261001'
base=(v/'v12_baseline_r41.asc').read_bytes().decode()
a=base.index('// BMMS1230_BEGIN');end='// BMMS1230_END\n\n';b=base.index(end,a)+len(end)
mod=base[a:b].replace('1230','1266')
def change(old,new):
 global mod
 assert mod.count(old)==1,(old,mod.count(old))
 mod=mod.replace(old,new)
change('return B==1&&M>=1024&&M<2048&&N>=2048&&N<=8192&&K>=1536&&K<4096&&bmms11r2::Eligible(B,M,N,K,cores);',
       'return bmms1230::Eligible(B,M,N,K,cores)&&M>=1280&&M<1536&&N>=4096&&N<6144&&K==1536&&!bmms1241::Eligible(B,M,N,K,cores);')
change('return (!ta||M%64==0)&&((tb?K:N)%64==0);','return !tb&&bmms1230::AlignedPitch(M,N,K,ta,tb);')
change('TM=64,TN=128,AM=128,BN=256','TM=64,TN=128,AM=256,BN=128')
change('AscendC::TPipe* pipe_;Plan p;','AscendC::TPipe* pipe_;Plan p,original;')
# Input addressing uses D=B^T*A^T geometry; task ownership remains the original C geometry.
change('        p=plan;pipe_=pipe;\n        for(int s=0;s<2;++s){',
       '        original=plan;p=plan;p.M=plan.N;p.N=plan.M;pipe_=pipe;\n        for(int s=0;s<2;++s){')
change('        const int group=AscendC::GetBlockIdx(),perBatch=p.pM*p.pN;',
       '        const Plan& p=original;constexpr int AM=128,BN=256;\n        const int group=AscendC::GetBlockIdx(),perBatch=p.pM*p.pN;')
change('                Macro(group,batch,m0,n0,MinI(AM,mEnd-m0),MinI(BN,nEnd-n0),\n                    nextM,nextN,hasNext?MinI(AM,mEnd-nextM):0,hasNext?MinI(BN,nEnd-nextN):0,hasNext);',
       '                Macro(group,batch,n0,m0,MinI(BN,nEnd-n0),MinI(AM,mEnd-m0),\n                    nextN,nextM,hasNext?MinI(BN,nEnd-nextN):0,hasNext?MinI(AM,mEnd-nextM):0,hasNext);')
change('class RowMaxConsumer {','class ColumnMaxConsumer {\n    static constexpr int AM=128,BN=256; // Original C task geometry, independent of D storage.')
change('                    AscendC::Duplicate(c,bmmmaxsum_v43::NEG_INF,vr*BN);',
       '                    AscendC::Duplicate(c,bmmmaxsum_v43::NEG_INF,256*64);')
change('                    const int64_t off=(int64_t(group)*2+ringSlot)*MACRO_ELEMS+sub*vr*BN;',
       '                    const int64_t off=(int64_t(group)*2+ringSlot)*MACRO_ELEMS+sub*vr;')
change('                    AscendC::DataCopyExtParams cp{static_cast<uint16_t>(vr),uint32_t(br*4),uint32_t((BN-br)*4),uint32_t((BN-br)/8),0};',
       '                    AscendC::DataCopyExtParams cp{static_cast<uint16_t>(br),uint32_t(vr*4),uint32_t((128-vr)*4),uint32_t((64-vr)/8),0};')
start=mod.index('                    AscendC::BinaryRepeatParams rp{1,1,1,32,32,32};')
stop=mod.index('                    cq.FreeTensor(c);++seq;',start)
mod=mod[:start]+'''                    // Each UB row is a D row (one original N position), with 64 original M lanes.
                    // Reduce across D rows, preserving every original M lane and all N-shard ownership.
                    for(int span=128;span>=1;span/=2){
                        AscendC::Max(c,c,c[span*64],span*64);AscendC::PipeBarrier<PIPE_V>();
                    }
                    AscendC::Max(run,run,c,vr);AscendC::PipeBarrier<PIPE_V>();
'''+mod[stop:]
change('if ASCEND_IS_AIC {MacroMmadProducer<T,TA,TB> op;op.Init(a,b,ring,p,&pipe);op.Process();}',
       'if ASCEND_IS_AIC {MacroMmadProducer<T,!TB,!TA> op;op.Init(b,a,ring,p,&pipe);op.Process();}')
change('if ASCEND_IS_AIV {RowMaxConsumer op;op.Init(ring,part,y,p,&pipe);op.Process();}',
       'if ASCEND_IS_AIV {ColumnMaxConsumer op;op.Init(ring,part,y,p,&pipe);op.Process();}')
for t,typ in [('f16','half'),('b16','bfloat16_t')]:
 for suf,ta in [('nt','false'),('tt','true')]:
  change(f'BMMS1266_KERNEL(bmms1266_{t}_{suf},{typ},{ta},true)\n','')
lo=mod.index('    if(dtype==1){',mod.index('static inline bool TryLaunch'));hi=mod.index('#undef BMMS1266_LAUNCH',lo)
mod=mod[:lo]+'''    if(dtype==1){if(!ta){BMMS1266_LAUNCH(bmms1266_f16_nn);}else{BMMS1266_LAUNCH(bmms1266_f16_tn);}}
    else{if(!ta){BMMS1266_LAUNCH(bmms1266_b16_nn);}else{BMMS1266_LAUNCH(bmms1266_b16_tn);}}
'''+mod[hi:]
hook='    if(bmms1266::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
pos=base.index('extern "C" void run_kernel(');src=base[:pos]+mod+base[pos:]
pos=src.index('    if(bmms1241::TryLaunch');src=src[:pos]+hook+src[pos:]
assert src.replace(mod,'',1).replace(hook,'',1)==base
name='v12_r66_case12_transposed_product.asc';assert not (v/name).exists()
for path in [v/name,lab/'r66.asc']:path.write_bytes(src.encode())
(lab/'r66_module.asc').write_bytes(mod.encode())
meta=dict(version='v12_r66',parent='v12_baseline_r41.asc',sha256=hashlib.sha256(src.encode()).hexdigest(),status='pending CANN/NPU verification',parent_byte_recovery=True,new_device_entries=4,change='D=B^T*A^T, Cube256x128 with original C128x256 task ownership; column max of D, unchanged pM/pN and final merge; original synchronization',L1=393216,L0A=65536,L0B=32768,L0C=131072)
(v/'v12_r66_manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
(root/'V12_npu_lab/results/rethink_20261001/AUDIT_R66.json').write_text(json.dumps(meta,indent=2)+'\n')
cm=(lab/'CMakeLists.txt').read_text();assert 'foreach(v r41 r65)' in cm
(lab/'CMakeLists.txt').write_text(cm.replace('foreach(v r41 r65)','foreach(v r41 r65 r66)'),newline='\n')
script=(lab/'check_r65.sh').read_text().replace('r65','r66').replace('R65','R66')
(lab/'check_r66.sh').write_text(script,newline='\n')
print(json.dumps(meta))
