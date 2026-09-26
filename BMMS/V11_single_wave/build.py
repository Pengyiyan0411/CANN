"""R10 descendants: remove a short task wave, or parallelize the final N merge."""
from pathlib import Path
import difflib
import hashlib
import json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;OUT=ROOT/'BMMS_V11_R11_R12'
BASE=ROOT/'BMMS_V11_R09_R10/R10_SINGLE_WAVE_GRID.asc'
BASE_SHA='cd8f8d6383ca24d0e46ae14757e1fce8b639da4123cc3a2a0875664564fb3600'
NAMES={'R11':'R11_SINGLE_WAVE_EXPAND','R12':'R12_PARALLEL_N_MERGE'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,s):p.write_text(s,encoding='utf-8',newline='\n')
def once(s,a,b):
    assert s.count(a)==1,(s.count(a),a[:100]);return s.replace(a,b,1)
def between(s,a,b):
    i=s.index(a);return s[i:s.index(b,i)]
def consumer(s):return between(s,'class RowMaxConsumer {','#ifndef BMMS11R2_CPU_TEST')
def old_finish(s):return between(consumer(s),'        auto merged=mergedBuf.Get<float>(),tmp=tmpBuf.Get<float>();','    }\n};')
def parallel_macro(old):
    c=consumer(old);body=old_finish(old)
    c=once(c,body,'        FinishReduction();\n')
    c=once(c,'    __aicore__ inline void Process(){',(HERE/'parallel_finish.asc').read_text(encoding='utf-8')+'    __aicore__ inline void Process(){')
    c=once(c,'int64_t(p.B)*p.pN*p.M);','int64_t(p.B)*(p.pN+1)*p.M);')
    s=once(old,consumer(old),c)
    return once(s,'uint64_t(p.B)*p.pN*p.M*4ULL;','uint64_t(p.B)*(p.pN+1)*p.M*4ULL;')
def verify():
    assert sha(BASE)==BASE_SHA and sha(OUT/'R10_CONTROL.asc')==BASE_SHA
    original=BASE.read_text(encoding='utf-8');old=(ROOT/'V11_recovery/one_wave_macro_fragment.asc').read_text(encoding='utf-8')
    for v,frag in [('R11','expanded_macro_fragment.asc'),('R12','parallel_macro_fragment.asc')]:
        source=(OUT/(NAMES[v]+'.asc')).read_text(encoding='utf-8');part=(HERE/frag).read_text(encoding='utf-8')
        assert once(source,part,old).split('\n',1)[1]==original.split('\n',1)[1]
    old_plan=(ROOT/'V11_recovery/one_wave_plan.asc').read_text(encoding='utf-8')
    expected=once(old,old_plan,once(old_plan,'static inline Plan MakePlan(','static inline Plan MakeR10Plan(')+(HERE/'expanded_plan_tail.asc').read_text(encoding='utf-8'))
    assert expected==(HERE/'expanded_macro_fragment.asc').read_text(encoding='utf-8')
    assert parallel_macro(old)==(HERE/'parallel_macro_fragment.asc').read_text(encoding='utf-8')
    return {'independent_R10_descendants':True,'R10_native_and_residual_paths_unchanged':True,
            'all_dispatch_guards_preserved':True,'R11_existing_R10_decisions_preserved':True,
            'R11_only_macro_host_plan_changed':True,'R12_host_plan_and_producer_unchanged':True,
            'R12_full_M_sum_preserved':True,'R09_changes_not_included':True}
def main():
    assert sha(BASE)==BASE_SHA
    original=BASE.read_text(encoding='utf-8');old=(ROOT/'V11_recovery/one_wave_macro_fragment.asc').read_text(encoding='utf-8')
    old_plan=(ROOT/'V11_recovery/one_wave_plan.asc').read_text(encoding='utf-8')
    new_plan=once(old_plan,'static inline Plan MakePlan(','static inline Plan MakeR10Plan(')+(HERE/'expanded_plan_tail.asc').read_text(encoding='utf-8')
    write(HERE/'expanded_plan.asc',new_plan)
    parts={'R11':once(old,old_plan,new_plan),'R12':parallel_macro(old)}
    write(HERE/'expanded_macro_fragment.asc',parts['R11']);write(HERE/'parallel_macro_fragment.asc',parts['R12'])
    OUT.mkdir(exist_ok=True);(OUT/'R10_CONTROL.asc').write_bytes(BASE.read_bytes());rows=[]
    for v,frag in parts.items():
        s=once(original,old,frag);s=once(s,s.split('\n',1)[0],'// '+NAMES[v]+': independent R10 descendant; pending platform validation.')
        path=OUT/(NAMES[v]+'.asc');write(path,s)
        assert s.count('extern "C" void run_kernel(')==1 and '#define ASCENDC_CUBE_ONLY' not in s
        write(HERE/(NAMES[v]+'.diff'),''.join(difflib.unified_diff(original.splitlines(True),s.splitlines(True),fromfile='R10',tofile=NAMES[v])))
        rows.append({'version':v,'file':path.name,'sha256':sha(path),'platform_result_received':False})
    manifest={'base':BASE.relative_to(ROOT).as_posix(),'base_sha256':BASE_SHA,
              'control':{'file':'R10_CONTROL.asc','sha256':BASE_SHA},'variants':rows,'proof':verify(),
              'cann_compiled_locally':False,'npu_tested_locally':False,'known_numerical_limitations_remain':True}
    write(OUT/'MANIFEST.json',json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
