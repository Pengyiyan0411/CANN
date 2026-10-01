"""B NZ laid out by complete K1/N macro panels for a single GM->L1 DMA."""
from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1];v=root/'BMMS_V12';lab=root/'V12_npu_lab/case12_k1_20261001'
base=(v/'v12_baseline_r41.asc').read_bytes().decode()
src=(v/'v12_r56_case12_b_nz_prepack.asc').read_bytes().decode().replace('1256','1257')
src=src.replace('// B-only NZ prepack experiment: original r30 grid, A path, K order and consumer.',
    '// B panel-NZ experiment: whole K1xBN panels contiguous in GM; original r30 grid retained.')
src=src.replace('static inline uint64_t BBytes(const Plan& p){return uint64_t(p.K)*p.N*2;}',
    'static inline uint64_t BBytes(const Plan& p){return uint64_t(p.K)*bmms83::UpH(p.N,BN)*BN*2;}')
src=src.replace('packed.SetGlobalBuffer(reinterpret_cast<__gm__ half*>(dst),int64_t(p.K)*p.N);',
    'packed.SetGlobalBuffer(reinterpret_cast<__gm__ half*>(dst),int64_t(p.K)*((p.N+BN-1)/BN)*BN);')
src=src.replace('uint32_t((p.K-rows)*32)','uint32_t((K1-rows)*32)')
src=src.replace('const int64_t off=int64_t(col0/16)*p.K*16+row0*16;',
'''const int64_t off=(int64_t(col0/BN)*(p.K/K1)+row0/K1)*(K1*BN)
            +((col0%BN)/16)*K1*16+(row0%K1)*16;''')
old='''        const int64_t bi=int64_t(n0/16)*p.K*16+k0*16;
        // Packed GM [N/16,K,16] -> contiguous L1 [br/16,kr,16].
        AscendC::DataCopyParams qb{uint16_t(br/16),uint16_t(kr),uint16_t(p.K-kr),0};'''
new='''        const int64_t bi=(int64_t(n0/BN)*(p.K/K1)+k0/K1)*(K1*BN);
        // Each complete K1 stage is contiguous [br/16,K1,16].
        AscendC::DataCopyParams qb{1,uint16_t(br*kr/16),0,0};'''
assert old in src;src=src.replace(old,new)
a=src.index('// BMMS1257_BEGIN');b=src.index('// BMMS1257_END',a)+len('// BMMS1257_END\n\n');mod=src[a:b]
hook='    if(bmms1257::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
assert src.replace(mod,'',1).replace(hook,'',1)==base
name='v12_r57_case12_b_panel_nz.asc';assert not (v/name).exists()
(v/name).write_bytes(src.encode());(lab/'r57.asc').write_bytes(src.encode())
meta=dict(version='v12_r57',parent='v12_baseline_r41.asc',control='v12_r56_case12_b_nz_prepack.asc',file=name,
    sha256=hashlib.sha256(src.encode()).hexdigest(),status='experimental pending validation',
    change='B prepack to [Nmacro,Kstage,N16,K256,16], then one contiguous DMA per stage; full pack cost included',
    gate='same original r30 metadata gate as r56',parent_byte_recovery=True,new_device_entries=4)
(v/'v12_r57_manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
# Add the build target only after the previous job has completed.
(lab/'check_r57.sh').write_text('''#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_case12_k1_20261001
test "$(cat results/r56.status)" = R56_DONE
trap 'echo R57_FAILED > results/r57.status' ERR
python3 - <<'PY'
from pathlib import Path
p=Path('CMakeLists.txt');s=p.read_text();s=s.replace('foreach(v r41 r51 r52 r53 r54 r55 r56)','foreach(v r41 r51 r52 r53 r54 r55 r56 r57)');p.write_text(s)
PY
echo R57_BUILD > results/r57.status
cmake -S . -B build >logs/r57_configure.log 2>&1
cmake --build build --target bench_r57 -j2 >logs/r57_build.log 2>&1
echo R57_PRECISION > results/r57.status
timeout 180 ./build/bench_r57 cases/all.txt 3 results/r57_correctness.jsonl >logs/r57_correctness.log 2>&1
echo R57_SCREEN > results/r57.status
python3 run_screen.py --baseline r41 --candidate r57 --manifest cases/screen.txt --tag r57_screen --repeats 30 --discard 5 --windows 2 >logs/r57_screen.log 2>&1
echo R57_DONE > results/r57.status
''',encoding='utf-8',newline='\n')
print(json.dumps(meta))
