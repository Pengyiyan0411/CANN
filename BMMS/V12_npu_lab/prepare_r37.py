from pathlib import Path
import hashlib,json,shutil
root=Path(__file__).resolve().parents[1]
lab=root/'V12_npu_lab/narrow_dense'
lab.mkdir(exist_ok=True)
base=(root/'BMMS_V12/v12_baseline_r33.asc').read_bytes()
raw=base.decode()
policy='''// BMMS1237_PLAN_BEGIN
namespace bmms1237 {
using Plan=bmms11r2::Plan;
static inline bool InDomain(int B,int M,int N,int K){
    return B==1&&((M>=1536&&M<1792&&N>=2048&&N<3072&&K>=2048&&K<2560)||
                  (M>=1280&&M<1536&&N>=4096&&N<6144&&K>=1536&&K<1664));
}
static inline Plan MakePlan(int B,int M,int N,int K,int cores){
    const Plan old=bmms11r2::MakePlan(B,M,N,K,cores);
    if(!InDomain(B,M,N,K)||cores<2||cores>64)return old;
    const auto prior=bmms11r2::ExistingPeak(old);
    Plan best=old;auto peakBest=prior;
    const int minGroups=(3*cores+3)/4;
    for(int pm=1;pm<=bmms83::MinH(old.mTiles,cores);++pm){
        const int lo=bmms83::MaxH(1,bmms83::UpH(minGroups,pm));
        const int hi=bmms83::MinH(old.nTiles,cores/pm);
        for(int pn=lo;pn<=hi;++pn){
            Plan p=old;p.pM=pm;p.pN=pn;p.tasks=pm*pn;p.blocks=p.tasks;
            const auto q=bmms11r2::SingleWavePeak(p);
            // Strictly reduce peak macro count without increasing peak cells/input.
            // Unlike R14, evaluate this also when the old plan has a partial 2nd wave.
            if(q.tiles>=prior.tiles||q.cells>prior.cells||q.input>prior.input)continue;
            if(q.tiles<peakBest.tiles||(q.tiles==peakBest.tiles&&
               (q.cells<peakBest.cells||(q.cells==peakBest.cells&&
               (q.input<peakBest.input||(q.input==peakBest.input&&
               (pn<best.pN||(pn==best.pN&&p.blocks>best.blocks)))))))){
                best=p;peakBest=q;
            }
        }
    }
    return best;
}
}
// BMMS1237_PLAN_END
'''
old='static inline Plan MakePlan(int B,int M,int N,int K,int cores){return bmms11r2::MakePlan(B,M,N,K,cores);}'
new=old.replace('return bmms11r2::','return bmms1237::')
assert raw.count(old)==1
pos=raw.index('// BMMS1230_BEGIN')
data=raw[:pos]+policy+'\n'+raw[pos:]
data=data.replace(old,new)
assert data.replace(policy+'\n','',1).replace(new,old).encode()==base
name='v12_r37_dense_singlewave_plan.asc'
(root/'BMMS_V12'/name).write_bytes(data.encode())
(lab/'r37.asc').write_bytes(data.encode());(lab/'r33.asc').write_bytes(base)
(lab/'policy.hpp').write_text(policy)
shutil.copyfile(root/'V12_npu_lab/harness/main.asc',lab/'main.asc')
shutil.copyfile(root/'V12_npu_lab/harness/run_screen.py',lab/'run_screen.py')
event=(root/'V12_npu_lab/harness/event_bench_r33.asc').read_text()
event=event.replace('bmms1233::Eligible','bmms1230::Eligible')
event=event.replace('auto p=plan;auto ring=', 'auto p=candidate?bmms1237::MakePlan(plan.B,plan.M,plan.N,plan.K,20):plan;auto ring=')
event=event.replace('if(candidate){DISPATCH(bmms1233);}else{DISPATCH(bmms11r2);}','DISPATCH(bmms1230);')
event=event.replace('candidate?"r33":"r30"','candidate?"r37":"r33"')
event=event.replace('const auto p=bmms11r2::MakePlan', 'if(cores!=20){std::fprintf(stderr,"Expected 20 Cube cores, got %lld\\n",(long long)cores);return 4;}\n        const auto p=bmms11r2::MakePlan')
event=event.replace('bmms11r2::WorkspaceBytes(p),ACL_MEM', 'std::max(bmms11r2::WorkspaceBytes(p),bmms11r2::WorkspaceBytes(bmms1237::MakePlan(B,M,N,K,cores))),ACL_MEM')
(lab/'event_plans.asc').write_text(event)
(lab/'CMakeLists.txt').write_text('''cmake_minimum_required(VERSION 3.16)
find_package(ASC REQUIRED)
project(bmms_narrow LANGUAGES ASC CXX)
set(CMAKE_CXX_STANDARD 14)
foreach(v r33 r37)
 add_executable(bench_${v} main.asc)
 target_compile_definitions(bench_${v} PRIVATE BMMS_KERNEL_HEADER="${v}.asc" BMMS_VARIANT="${v}")
endforeach()
add_executable(event_plans event_plans.asc)
target_compile_definitions(event_plans PRIVATE BMMS_KERNEL_HEADER="r37.asc" BMMS_VARIANT="r37")
foreach(t bench_r33 bench_r37 event_plans)
 target_link_libraries(${t} PRIVATE tiling_api register platform unified_dlog dl m graph_base)
 target_include_directories(${t} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
 target_compile_options(${t} PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=dav-2201>)
endforeach()
''')
manifest={'version':'v12_r37','parent':'v12_baseline_r33.asc','sha256':hashlib.sha256(data.encode()).hexdigest(),'parent_sha256':hashlib.sha256(base).hexdigest(),'status':'experimental, pending NPU tests','new_device_entries':0,'source_byte_recovery':True}
(root/'BMMS_V12/v12_r37_manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(manifest))
