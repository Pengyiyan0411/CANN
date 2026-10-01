"""Second mechanism: 256x128 macro, preserving the r30 cross-macro prefetch."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[1];v=ROOT/'BMMS_V12';lab=ROOT/'V12_npu_lab/case12_k1_20261001'
base=(v/'v12_baseline_r41.asc').read_bytes().decode()
control=(v/'v12_r51_case12_kstage320.asc').read_bytes().decode()
a=control.index('// BMMS1251_BEGIN');b=control.index('// BMMS1251_END',a)+len('// BMMS1251_END\n\n')
mod=control[a:b].replace('1251','1253').replace('K1=320','K1=256')
mod=mod.replace('// Independent r41 experiment: K1=256; K0 order, grid and row-max consumer unchanged.',
                '// Independent r41 experiment: 256x128 macro, original cross-macro prefetch and K0 order.')
mod=mod.replace('using bmms1230::MakePlan;','')
mod=mod.replace('AM=128,BN=256,K1=256','AM=256,BN=128,K1=256')
mod=mod.replace('const auto p=MakePlan(B,M,N,K,cores);\n    return p.pN==2 && p.pM>=8 && p.pM==p.mTiles && p.tasks==cores && p.blocks==cores;',
'''const auto p=bmms1230::MakePlan(B,M,N,K,cores);
    const int mt=bmms83::UpH(M,AM),nt=bmms83::UpH(N,BN);
    return p.pN==2 && p.pM>=8 && p.pM==p.mTiles && p.tasks==cores && p.blocks==cores &&
           cores%mt==0 && cores/mt<=nt;
}
static inline Plan MakePlan(int B,int M,int N,int K,int cores){
    auto p=bmms1230::MakePlan(B,M,N,K,cores);
    p.mTiles=bmms83::UpH(M,AM);p.nTiles=bmms83::UpH(N,BN);
    p.pM=p.mTiles;p.pN=cores/p.pM;p.tasks=cores;p.blocks=cores;return p;''')
# The ring footprint stays 32768 floats, but each AIV reduces 128 rows x 128 columns.
a=base.index('class RowMaxConsumer {',base.index('namespace bmms1230 {'))
b=base.index('} // namespace bmms1230',a)
consumer=base[a:b]
old='''                    AscendC::BinaryRepeatParams rp{1,1,1,32,32,32};
                    AscendC::Max(c,c,c[128],64,vr,rp);AscendC::PipeBarrier<PIPE_V>();
                    AscendC::Max(c[64],c[64],c[192],64,vr,rp);AscendC::PipeBarrier<PIPE_V>();
                    AscendC::Max(c,c,c[64],64,vr,rp);AscendC::PipeBarrier<PIPE_V>();
                    AscendC::WholeReduceMax(rows,c,64,vr,1,1,32,AscendC::ReduceOrder::ORDER_ONLY_VALUE);'''
new='''                    AscendC::BinaryRepeatParams rp{1,1,1,16,16,16};
                    AscendC::Max(c,c,c[64],64,vr,rp);AscendC::PipeBarrier<PIPE_V>();
                    AscendC::WholeReduceMax(rows,c,64,vr,1,1,16,AscendC::ReduceOrder::ORDER_ONLY_VALUE);'''
assert old in consumer;consumer=consumer.replace(old,new)
i=mod.index('template<class T,bool TA,bool TB>\n__aicore__ inline void Entry')
mod=mod[:i]+consumer+mod[i:];mod=mod.replace('bmms1230::RowMaxConsumer op','RowMaxConsumer op')
hook='    if(bmms1253::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
i=base.index('extern "C" void run_kernel(');src=base[:i]+mod+base[i:]
i=src.index('    if(bmms1241::TryLaunch');src=src[:i]+hook+src[i:]
assert src.replace(mod,'',1).replace(hook,'',1)==base
name='v12_r53_case12_m256_prefetch.asc'
(v/name).write_bytes(src.encode());(lab/'r53.asc').write_bytes(src.encode())
meta=dict(version='v12_r53',parent='v12_baseline_r41.asc',sha256=hashlib.sha256(src.encode()).hexdigest(),
          status='experimental pending NPU validation',change='AM256 BN128 K1=256 K0=64; retain r30 cross-macro L1 prefetch, original per-fractal LoadData and full-K rowmax',
          scope='r51 metadata scope, plus cores divisible by ceil(M/256); one M macro per task',
          parent_byte_recovery=True,L1_bytes=393216,L0A_bytes=65536,L0B_bytes=32768,L0C_bytes=131072)
(v/'v12_r53_manifest.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(meta))
cm=(lab/'CMakeLists.txt').read_text().replace('foreach(v r41 r51 r52)','foreach(v r41 r51 r52 r53)')
(lab/'CMakeLists.txt').write_bytes(cm.encode())
(lab/'check_r53.sh').write_text('''#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_case12_k1_20261001
trap 'echo R53_FAILED > results/r53.status' ERR
cmake -S . -B build >logs/r53_configure.log 2>&1
cmake --build build --target bench_r53 -j2 >logs/r53_build.log 2>&1
./build/bench_r53 cases/all.txt 3 results/r53_correctness.jsonl >logs/r53_correctness.log 2>&1
python3 run_screen.py --baseline r41 --candidate r53 --manifest cases/screen.txt --tag r53_screen --repeats 30 --discard 5 --windows 2 >logs/r53_screen.log 2>&1
echo R53_DONE > results/r53.status
''',encoding='utf-8',newline='\n')
