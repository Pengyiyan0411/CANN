from pathlib import Path
import json,hashlib
r=Path(__file__).resolve().parents[1];o=r/'BMMS_V12';h=r/'V12_npu_lab/harness'
base=(o/'v12_baseline_r19.asc').read_bytes();s=base.decode('utf-8');r20=(h/'r20.asc').read_text(encoding='utf-8')
a=s.index('class RowMaxConsumer {',s.index('namespace bmms11r2 {'));b=s.index('\n#ifndef BMMS11R2_CPU_TEST',a)
consumer=s[a:b].rstrip()
old='AscendC::Max(merged,merged,tmp,p.M);bmms71::Fence<AscendC::HardEvent::V_MTE2>(*pipe_);'
new='''const int full=p.M/64,tail=p.M%64;
                const AscendC::BinaryRepeatParams rp{1,1,1,8,8,8};
                if(full)AscendC::Max(merged,merged,tmp,uint64_t(64),uint8_t(full),rp);
                if(tail)AscendC::Max(merged[full*64],merged[full*64],tmp[full*64],uint64_t(tail),uint8_t(1),rp);
                bmms71::Fence<AscendC::HardEvent::V_MTE2>(*pipe_);'''
assert consumer.count(old)==1;consumer=consumer.replace(old,new)
start=r20.index('namespace bmms1220 {');end=r20.index('// BMMS1220_END',start)
host=r20[start:end].replace('bmms1220','bmms1221').replace('BMMS1220','BMMS1221')
host=host.replace('const auto p=MakePlan(B,M,N,K,cores);\n    uint8_t*','const auto p=MakePlan(B,M,N,K,cores);\n    if(!Changed(bmms11r2::MakePlan(B,M,N,K,cores),p))return false;\n    uint8_t*')
host=host.replace('BMMS1221_LAUNCH(bmms11r2_', 'BMMS1221_LAUNCH(bmms1221_')
module='\n// BMMS1221_BEGIN\nnamespace bmms1221 {\nusing Plan=bmms11r2::Plan;\nusing bmms83::MinI;\n'
for k in ['TM','TN','AM','BN','MACRO_ELEMS','READY','FREE']:module+=f'constexpr int {k}=bmms11r2::{k};\n'
module+=consumer+'''
template<class T,bool TA,bool TB>
__aicore__ inline void Entry(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ring,GM_ADDR partial,Plan p){
    AscendC::TPipe pipe;
    if ASCEND_IS_AIC {bmms11r2::ReuseProducer<T,TA,TB> op;op.Init(a,b,ring,p,&pipe);op.Process();}
    if ASCEND_IS_AIV {RowMaxConsumer op;op.Init(ring,partial,y,p,&pipe);op.Process();}
}
}
#define BMMS1221_KERNEL(NAME,T,TA,TB) \\
__schedmode__(1) __global__ __mix__(1,2) void NAME(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ring,GM_ADDR part,bmms1221::Plan p){bmms1221::Entry<T,TA,TB>(a,b,y,ring,part,p);}
'''
for dt,typ in [('f16','half'),('b16','bfloat16_t')]:
 for tag,ta,tb in [('nn','false','false'),('nt','false','true'),('tn','true','false'),('tt','true','true')]:module+=f'BMMS1221_KERNEL(bmms1221_{dt}_{tag},{typ},{ta},{tb})\n'
module+='#undef BMMS1221_KERNEL\n'+host+'// BMMS1221_END\n\n'
idx=base.index(b'extern "C" void run_kernel');out=base[:idx]+module.encode()+base[idx:]
hook=b'    if(bmms1221::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
idx=out.index(b'    if(bmms11r2::TryLaunch(a,b,y,');out=out[:idx]+hook+out[idx:]
assert out.replace(module.encode(),b'',1).replace(hook,b'',1)==base
src=o/'v12_r21_case12_packet_tail.asc';src.write_bytes(out);(h/'r21.asc').write_bytes(out)
m=dict(candidate=src.name,parent='v12_baseline_r19.asc',sha256=hashlib.sha256(out).hexdigest(),parent_sha256=hashlib.sha256(base).hexdigest(),parent_recovered_byte_for_byte=True,status='validation pending',change='r20 packet policy unchanged; explicit final-Max tail in selected Case12 consumer only; producer reused')
(o/'v12_r21_manifest.json').write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8')
ev=(h/'event_bench_r20.asc').read_text(encoding='utf-8').replace('bmms1220','bmms1221').replace('"r20"','"r21"')
ev=ev.replace('    DISPATCH(bmms11r2);','    if(candidate&&bmms1221::Changed(plan,c12Chosen)){DISPATCH(bmms1221);}else{DISPATCH(bmms11r2);}')
(h/'event_bench_r21.asc').write_text(ev,encoding='utf-8',newline='\n')
cm=h/'CMakeLists.txt';t=cm.read_text(encoding='utf-8')
if 'add_executable(bench_r21 ' not in t:t+=t[t.index('add_executable(bench_r20 '):].replace('r20','r21')
cm.write_text(t,encoding='utf-8',newline='\n')
ana=(h/'analyze_c12_r20.py').read_text(encoding='utf-8').replace('r20','r21');(h/'analyze_c12_r21.py').write_text(ana,encoding='utf-8',newline='\n')
script='''#!/usr/bin/env bash
set -eo pipefail
cd /home/developer/bmms_v12_lab_20260928
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cmake -S . -B build >logs/c12_r21_configure.log 2>&1
cmake --build build --target c12_r21_build -j3 >logs/c12_r21_build.log 2>&1
for pair in 'screen cases_c12_screen' 'holdout cases_c12_holdout' 'random cases_c12_random' 'original cases' 'c8 cases_c8_final' 'split cases_split' 'controls cases_split_controls'; do
  read -r label dir <<< "$pair"
  ./build/bench_r21 "$dir/manifest.txt" 3 "results/c12_r21_${label}_correctness.jsonl" >"results/c12_r21_${label}_correctness.log" 2>&1
done
./build/event_bench_r21 cases_c12_holdout/screen.txt 10 results/c12_r21_holdout_event.jsonl >results/c12_r21_holdout_event.log 2>&1
./build/event_bench_r21 cases_c12_holdout/screen.txt 10 results/c12_r21_holdout_event_repeat.jsonl >results/c12_r21_holdout_event_repeat.log 2>&1
./build/event_bench_r21 cases_c12_random/manifest.txt 10 results/c12_r21_random_event.jsonl >results/c12_r21_random_event.log 2>&1
./build/event_bench_r21 cases_c12_random/manifest.txt 10 results/c12_r21_random_event_repeat.jsonl >results/c12_r21_random_event_repeat.log 2>&1
BMMS_EVENT_AA=1 ./build/event_bench_r21 cases_c12_screen/profile.txt 6 results/c12_r21_aa.jsonl >results/c12_r21_aa.log 2>&1
python3 analyze_c12_r21.py >results/c12_r21_event_analysis.log
for entry in 'public cases_c12_holdout/screen.txt' 'c8_control cases_c8/screen.txt' 'split_control cases_split/screen.txt' 'other_control cases_split_controls/c8_unaffected.txt'; do
 read -r label manifest <<< "$entry"
 python3 run_screen.py --baseline r19 --candidate r21 --manifest "$manifest" --tag "c12_r21_${label}" --repeats 80 --discard 20 --windows 2 >"results/c12_r21_${label}.log" 2>&1
done
: >results/c12_r21_sanitizer_status.txt
for check in memcheck racecheck; do
 set +e
 timeout -k 15 360 mssanitizer -t "$check" --log-file="results/c12_r21_instrumented_${check}.log" -- ./build/sanitize_r21 cases_c12_holdout/sanitize_packet.txt 1 "results/c12_r21_instrumented_${check}.jsonl" >"results/c12_r21_instrumented_${check}_launcher.log" 2>&1
 status=$?
 set -e
 echo "$check $status" >>results/c12_r21_sanitizer_status.txt
done
python3 review_c12_sanitizers.py
python3 archive_c12.py
echo C12_R21_DONE
'''
(h/'check_c12_r21.sh').write_text(script,encoding='utf-8',newline='\n')
p=h/'review_c12_sanitizers.py';t=p.read_text(encoding='utf-8').replace("['r19','r20']","['r19','r20','r21']");p.write_text(t,encoding='utf-8',newline='\n')
p=h/'archive_c12.py';t=p.read_text(encoding='utf-8').replace("'r20.asc'","'r20.asc','r21.asc'").replace("'event_bench_r20.asc'","'event_bench_r20.asc','event_bench_r21.asc'").replace("'build/CMakeFiles/*r20*/*.make'","'build/CMakeFiles/*r20*/*.make','build/CMakeFiles/*r21*/*.make'");p.write_text(t,encoding='utf-8',newline='\n')
print(src.name,m['sha256'])
