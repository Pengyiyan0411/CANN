from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1];v=root/'BMMS_V12';lab=root/'V12_npu_lab/small_20261001'
base=(v/'v12_baseline_r41.asc').read_bytes().decode()
a=base.index('// BMMS52_BEGIN');b=base.index('// BMMS52_END',a)+len('// BMMS52_END')
mod=base[a:b].replace('bmms52','bmms1270').replace('BMMS52','BMMS1270')
mod=mod.replace('AscendC::TQue<AscendC::TPosition::VECIN,1> iq;','AscendC::TBuf<AscendC::TPosition::VECIN> input;')
mod=mod.replace('AscendC::TQue<AscendC::TPosition::VECOUT,1> oq;','AscendC::TBuf<AscendC::TPosition::VECOUT> output;')
mod=mod.replace('pipe.InitBuffer(iq,1,2*KP*sizeof(T));pipe.InitBuffer(oq,1,32);','pipe.InitBuffer(input,2*KP*sizeof(T));pipe.InitBuffer(output,32);')
mod=mod.replace('auto in=iq.AllocTensor<T>();','auto in=input.Get<T>();')
mod=mod.replace('AscendC::DataCopyPadExtParams<T> pad{false,0,0,T(0)};','AscendC::DataCopyPadExtParams<T> pad{true,0,uint8_t(KP-K),T(0)};')
start=mod.index('    iq.EnQue(in);');end=mod.index('    AscendC::PipeBarrier<PIPE_V>();AscendC::Mul',start)
mod=mod[:start]+'''    // Exactly one input-to-vector dependency; no input-buffer reuse.
    AscendC::SetFlag<AscendC::HardEvent::MTE2_V>(EVENT_ID0);
    AscendC::WaitFlag<AscendC::HardEvent::MTE2_V>(EVENT_ID0);
    auto fa=floats.Get<float>(),fb=fa[KP];
    // DataCopyPad initialized both physical tails, so this single cast is valid
    // for every supported K, including K%16 == 8.
    AscendC::Cast(fa,in,AscendC::RoundMode::CAST_NONE,2*KP);
'''+mod[end:]
mod=mod.replace('auto out=oq.AllocTensor<float>();','auto out=output.Get<float>();')
mod=mod.replace('    AscendC::ReduceSum(out,fa,scratch.Get<float>(),K);','''    if constexpr(K<=64)AscendC::WholeReduceSum(out,fa,K,1,1,1,8);
    else AscendC::ReduceSum(out,fa,scratch.Get<float>(),K);''')
mod=mod.replace('    oq.EnQue(out);out=oq.DeQue<float>();AscendC::DataCopyExtParams oc{1,4,0,0,0};\n    AscendC::DataCopyPad(gy,out,oc);oq.FreeTensor(out);iq.FreeTensor(in);','''    AscendC::SetFlag<AscendC::HardEvent::V_MTE3>(EVENT_ID0);
    AscendC::WaitFlag<AscendC::HardEvent::V_MTE3>(EVENT_ID0);
    AscendC::DataCopyExtParams oc{1,4,0,0,0};AscendC::DataCopyPad(gy,out,oc);
    // Do not release local storage before the sole store completes.
    AscendC::SetFlag<AscendC::HardEvent::MTE3_S>(EVENT_ID0);
    AscendC::WaitFlag<AscendC::HardEvent::MTE3_S>(EVENT_ID0);''')
assert 'oq.' not in mod and 'iq.' not in mod
hook='    if(bmms1270::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,stream))return;\n'
pos=base.index('extern "C" void run_kernel(');src=base[:pos]+mod+'\n\n'+base[pos:]
pos=src.index('    if(bmms1203::TryLaunch');src=src[:pos]+hook+src[pos:]
assert src.replace(mod+'\n\n','',1).replace(hook,'',1)==base
name='v12_r70_short_dot_single_shot.asc';assert not (v/name).exists()
for path in (v/name,lab/'r70.asc'):path.write_bytes(src.encode())
(lab/'r70_module.asc').write_bytes(mod.encode());(lab/'r70_hook.txt').write_text(hook)
meta=dict(version='v12_r70',parent='v12_baseline_r41.asc',sha256=hashlib.sha256(src.encode()).hexdigest(),status='pending NPU build/validation',parent_byte_recovery=True,new_device_entries=26,
          change='Short dot single-shot TBuf with explicit dependencies; initialized DMA padding enables a single Cast for all K; direct vector sum for K<=64')
(v/'v12_r70_manifest.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(meta,indent=2))
