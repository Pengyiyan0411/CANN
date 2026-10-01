"""Keep r30 geometry; halve full-macro A LoadData commands via destination gap."""
from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1];v=root/'BMMS_V12';lab=root/'V12_npu_lab/case12_k1_20261001'
out=root/'V12_npu_lab/results/case12_wide_load_20261001';out.mkdir(exist_ok=True)
base=(v/'v12_baseline_r41.asc').read_bytes().decode()
a=base.index('// BMMS1230_BEGIN');endmark='// BMMS1230_END\n\n';b=base.index(endmark,a)+len(endmark)
mod=base[a:b].replace('1230','1262')
old='return B==1&&M>=1024&&M<2048&&N>=2048&&N<=8192&&K>=1536&&K<4096&&bmms11r2::Eligible(B,M,N,K,cores);'
assert mod.count(old)==1
mod=mod.replace(old,'return bmms1230::Eligible(B,M,N,K,cores)&&M>=1280&&M<1536&&N>=4096&&N<6144&&K==1536&&!bmms1241::Eligible(B,M,N,K,cores);')
mod=mod.replace('return (!ta||M%64==0)&&((tb?K:N)%64==0);','return !tb&&bmms1230::AlignedPitch(M,N,K,ta,tb);')
lo=mod.index('        AscendC::LoadData2DParams la{};');hi=mod.index('        AscendC::LoadData2DParams lb{};',lo)
new='''        AscendC::LoadData2DParams la{};la.ifTranspose=TA;
        if(ar>=kr0){
            // Iterate along K; hardware repeats along M. Destination is still ZZ.
            // A source/destination fractal addresses match the old (M,K) loops exactly.
            la.repeatTimes=ar/16;la.srcStride=TA?kr1/16:1;la.dstGap=kr0/16-1;
            for(int j=0;j<kr0/16;++j){
                const int off=TA?kk*16+j*256:(kk/16+j)*ar*16;
                AscendC::LoadData(da[j*256],sa[off],la);
            }
        }else{
            // Very short M tails use fewer commands in the original orientation.
            la.repeatTimes=kr0/16;la.srcStride=TA?1:ar/16;
            for(int i=0;i<ar/16;++i){
                const int off=TA?i*kr1*16+kk*16:(kk/16)*ar*16+i*256;
                AscendC::LoadData(da[i*kr0*16],sa[off],la);
            }
        }
'''
mod=mod[:lo]+new+mod[hi:]
# Four real dispatches; TB is false by the host guard.
for t in ('f16','b16'):
 for suf,ta in [('nt','false'),('tt','true')]:
  typ='half' if t=='f16' else 'bfloat16_t'
  mod=mod.replace(f'BMMS1262_KERNEL(bmms1262_{t}_{suf},{typ},{ta},true)\n','')
lo=mod.index('    if(dtype==1){',mod.index('static inline bool TryLaunch'));hi=mod.index('#undef BMMS1262_LAUNCH',lo)
mod=mod[:lo]+'''    if(dtype==1){if(!ta){BMMS1262_LAUNCH(bmms1262_f16_nn);}else{BMMS1262_LAUNCH(bmms1262_f16_tn);}}
    else{if(!ta){BMMS1262_LAUNCH(bmms1262_b16_nn);}else{BMMS1262_LAUNCH(bmms1262_b16_tn);}}
'''+mod[hi:]
hook='    if(bmms1262::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
pos=base.index('extern "C" void run_kernel(');src=base[:pos]+mod+base[pos:]
pos=src.index('    if(bmms1241::TryLaunch');src=src[:pos]+hook+src[pos:]
assert src.replace(mod,'',1).replace(hook,'',1)==base
name='v12_r62_case12_wide_load_gap.asc';assert not (v/name).exists()
for p in [v/name,lab/'r62.asc']:p.write_bytes(src.encode())
(lab/'r62_module.asc').write_bytes(mod.encode())
# Exact mapping of EVERY 512-byte fractal; check no overlaps and address bounds.
states=0
for ar in range(16,129,16):
 for kr1 in (256,):
  for kk in range(0,kr1,64):
   kr0=64
   for ta in (0,1):
    oldmap={};newmap={}
    for i in range(ar//16):
     for j in range(kr0//16):
      dst=i*kr0*16+j*256
      source=(i*kr1*16+kk*16+j*256) if ta else ((kk//16+j)*ar*16+i*256)
      assert source+256<=ar*kr1 and dst+256<=ar*kr0
      assert dst not in oldmap;oldmap[dst]=source
    if ar>=kr0:
     for j in range(kr0//16):
      off=kk*16+j*256 if ta else (kk//16+j)*ar*16
      for i in range(ar//16):
       dst=j*256+i*(kr0//16)*256
       source=off+i*(kr1//16 if ta else 1)*256
       assert dst not in newmap;newmap[dst]=source
    else:newmap=oldmap.copy()
    assert newmap==oldmap;states+=1
meta=dict(version='v12_r62',parent='v12_baseline_r41.asc',file=name,sha256=hashlib.sha256(src.encode()).hexdigest(),
          status='pending NPU validation',new_device_entries=4,parent_byte_recovery=True,
          change='Original r30 N256 geometry/plan/K/floating-point schedule; A LoadData loops swapped with dstGap, 8 to4 commands on full M128 K64 tiles',
          address_mapping_states=states,L1_bytes=393216,L0A_bytes=32768,L0B_bytes=65536,L0C_bytes=131072)
(v/'v12_r62_manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
(out/'AUDIT_R62.json').write_text(json.dumps(meta,indent=2)+'\n')
cm=(lab/'CMakeLists.txt').read_text().replace('r60 r61)','r60 r61 r62)');(lab/'CMakeLists.txt').write_bytes(cm.encode())
script='''#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_case12_k1_20261001
trap 'echo R62_FAILED > results/r62.status' ERR
echo R62_BUILD > results/r62.status
cmake -S . -B build >logs/r62_configure.log 2>&1
cmake --build build --target bench_r62 -j2 >logs/r62_build.log 2>&1
echo R62_PRECISION > results/r62.status
timeout 180 ./build/bench_r62 cases/all.txt 3 results/r62_correctness.jsonl >logs/r62_correctness.log 2>&1
timeout 180 ./build/bench_r62 cases_r59_extra/all.txt 5 results/r62_extra_precision.jsonl >logs/r62_extra_precision.log 2>&1
echo R62_SCREEN > results/r62.status
python3 run_screen.py --baseline r41 --candidate r62 --manifest cases/r59_first8.txt --tag r62_first8 --repeats 30 --discard 5 --windows 2 >logs/r62_first8.log 2>&1
echo R62_DONE > results/r62.status
'''
(lab/'check_r62.sh').write_text(script,encoding='utf-8',newline='\n')
(out/'BASELINE_REPORT.md').write_bytes((root/'V12_npu_lab/results/case12_nmajor_20261001/REPORT.md').read_bytes())
print(json.dumps(meta))
