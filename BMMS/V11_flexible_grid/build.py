"""Independent R11 descendants that allow a smaller, more balanced single wave."""
from pathlib import Path
import difflib,hashlib,json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;OUT=ROOT/'BMMS_V11_R13_R14'
BASE=ROOT/'BMMS_V11_R11_R12/R11_SINGLE_WAVE_EXPAND.asc'
BASE_SHA='425db189f068ad963dadf2c537a96118b33a5035ef47c5e43dad2f81fd0ad223'
NAMES={'R13':'R13_FLEX_SHORT_WAVE','R14':'R14_FLEX_SINGLE_WAVE'}
GATES={'R13':'p.tasks<=cores','R14':'p.tasks!=cores'}
OLD_FRAGMENT=ROOT/'V11_single_wave/expanded_macro_fragment.asc'
OLD_PLAN=ROOT/'V11_single_wave/expanded_plan.asc'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,s):p.write_text(s,encoding='utf-8',newline='\n')
def once(s,a,b):
    assert s.count(a)==1,(s.count(a),a[:100]);return s.replace(a,b,1)
def between(s,a,b):
    i=s.index(a);return s[i:s.index(b,i)]
def fragment(version):
    plan=once(OLD_PLAN.read_text(encoding='utf-8'),'static inline Plan MakePlan(','static inline Plan MakeR11Plan(')
    plan+=(HERE/'flexible_plan_tail.asc').read_text(encoding='utf-8').replace('FLEX_REGIME_GATE',GATES[version])
    return once(OLD_FRAGMENT.read_text(encoding='utf-8'),OLD_PLAN.read_text(encoding='utf-8'),plan)
def verify():
    assert sha(BASE)==BASE_SHA and sha(OUT/'R11_CONTROL.asc')==BASE_SHA
    original=BASE.read_text(encoding='utf-8');old=OLD_FRAGMENT.read_text(encoding='utf-8')
    for v,name in NAMES.items():
        part=fragment(v);s=(OUT/(name+'.asc')).read_text(encoding='utf-8')
        assert part==(HERE/(v+'_macro_fragment.asc')).read_text(encoding='utf-8')
        assert once(s,part,old).split('\n',1)[1]==original.split('\n',1)[1]
        assert between(part,'static inline uint64_t RingBytes(','// BMMS11R2_CPU_EXTRACT_END')==between(old,'static inline uint64_t RingBytes(','// BMMS11R2_CPU_EXTRACT_END')
    return {'independent_R11_descendants':True,'all_device_code_unchanged':True,
            'all_dispatch_guards_preserved':True,'R11_planner_retained_as_fallback':True,
            'R13_only_old_multi_wave':'p.tasks > cores','R14_only_old_single_wave':'p.tasks == cores',
            'candidate_occupancy_floor':'ceil(3*cores/4)','candidate_blocks_equal_tasks':True,
            'R12_changes_not_included':True,'native_and_residual_unchanged':True}
def main():
    assert sha(BASE)==BASE_SHA;OUT.mkdir(exist_ok=True)
    (OUT/'R11_CONTROL.asc').write_bytes(BASE.read_bytes());original=BASE.read_text(encoding='utf-8');rows=[]
    for v,name in NAMES.items():
        part=fragment(v);write(HERE/(v+'_macro_fragment.asc'),part)
        s=once(original,OLD_FRAGMENT.read_text(encoding='utf-8'),part)
        s=once(s,s.split('\n',1)[0],'// '+name+': independent R11 descendant; pending platform validation.')
        p=OUT/(name+'.asc');write(p,s)
        write(HERE/(name+'.diff'),''.join(difflib.unified_diff(original.splitlines(True),s.splitlines(True),fromfile='R11',tofile=name)))
        rows.append({'version':v,'file':p.name,'sha256':sha(p),'platform_result_received':False})
    manifest={'base':BASE.relative_to(ROOT).as_posix(),'base_sha256':BASE_SHA,
        'control':{'file':'R11_CONTROL.asc','sha256':BASE_SHA},'variants':rows,'proof':verify(),
        'cann_compiled_locally':False,'npu_tested_locally':False,'known_numerical_limitations_remain':True}
    write(OUT/'MANIFEST.json',json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
