from pathlib import Path
import hashlib,json,shutil
root=Path(__file__).resolve().parents[1];lab=root/'V12_npu_lab/narrow_dense';v=root/'BMMS_V12'
feedback=root/'V12_results/2026-09-29_r40_feedback';feedback.mkdir(exist_ok=True)
prior=json.loads((root/'V12_results/2026-09-29_r39_feedback/RESULTS.json').read_text(encoding='utf-8'))
times=[2.20,4.49,5.08,6.52,6.64,13.97,8.99,45.98,64.60,79.01,1110.,1420.,15.06,13.23,11.12]
rows=[]
for old,t in zip(prior['rows'],times):
 rows.append(dict(case=old['case'],status='Pass',displayed_error_percent=0,latency_us=t,platform_best_us=old['platform_best_us'],r39_us=old['latency_us']))
source=v/'v12_r40_probe_r37_unchanged_in_domain.asc'
data=dict(version='v12_r40',version_attribution='Inferred from direct reply to r40 delivery; screenshot has no version/hash label',all_15_pass=True,independent_runs=1,
 source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),rows=rows,
 conclusion='Case11 and Case12 both HIT: full r37 route guards and narrow InDomain hold, but r37 plan equals r33 plan. Keep r33; evaluate actual alternatives rather than repeat shape probes.')
(feedback/'RESULTS.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
shutil.copyfile(Path(r'E:\Tencent Files\3232896164\nt_qq\nt_data\Pic\2026-09\Ori\2e62527f762ffaae141c1a8390012dc6.png'),feedback/'judge_r40.png')
m=json.loads((v/'MAINLINE.json').read_text(encoding='utf-8'));d=m['active_diagnostic'];assert d['version']=='v12_r40'
d.update(status='Judge all15 Pass; Case11=1.11ms,Case12=1.42ms: both HIT, r37 domain/guards hold but plans unchanged',feedback='../V12_results/2026-09-29_r40_feedback/RESULTS.json',historical=True)
m.update(latest_judge_feedback=d['feedback'],next_action='Evaluate same-peak grid alternatives on NPU; preserve r33 baseline and avoid further shape probes this round.')
(v/'MAINLINE.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
mf=json.loads((v/'v12_r40_manifest.json').read_text(encoding='utf-8'));mf.update(status=d['status'],judge_feedback=d['feedback']);(v/'v12_r40_manifest.json').write_text(json.dumps(mf,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for p in [v/'v12_r40_README.md',root/'V12_npu_lab/results/r40_20260929/REPORT.md']:
 text=p.read_text(encoding='utf-8');p.write_text('> Judge更新：全15点Pass，11/12为1.11/1.42ms，均HIT。适用条件成立，但r37没有更换计划。主线保留r33，下面保留提交前记录。\n\n'+text,encoding='utf-8')

event=(lab/'event_plans.asc').read_text(encoding='utf-8')
start=event.index('static void launch_direct');end=event.index('\nint main',start)
dispatch=event[start:end].replace('bool candidate,','').replace('const bmms11r2::Plan& plan','const bmms11r2::Plan& p')
dispatch=dispatch.replace('auto p=candidate?bmms1237::MakePlan(plan.B,plan.M,plan.N,plan.K,20):plan;','')
body=r'''
int main(int argc,char**argv){
 if(argc!=4)return 2;
 const int windows=std::atoi(argv[2]),calls=16;
 std::setvbuf(stdout,nullptr,_IOLBF,0);
 std::ifstream mf(argv[1]);FILE*out=std::fopen(argv[3],"w");if(!mf||!out)return 2;
 std::string manifest=argv[1],root=manifest.substr(0,manifest.find_last_of("/\\"));
 ck(aclInit(nullptr),"init");ck(aclrtSetDevice(0),"device");aclrtStream stream=nullptr;ck(aclrtCreateStream(&stream),"stream");
 int64_t cores=0;ck(aclrtGetDeviceInfo(0,ACL_DEV_ATTR_CUBE_CORE_NUM,&cores),"cores");
 int id,dt,ta,tb;int64_t B,M,N,K;
 while(mf>>id>>B>>M>>N>>K>>dt>>ta>>tb){
  if(!bmms1240::Matched(B,M,N,K,dt,ta,tb,cores))continue;
  const auto base=bmms11r2::MakePlan(B,M,N,K,cores);const auto peak=bmms11r2::ExistingPeak(base);
  std::vector<bmms11r2::Plan> plans{base};uint64_t wsBytes=bmms11r2::WorkspaceBytes(base);
  for(int pm=1;pm<=std::min(base.mTiles,int(cores));++pm)for(int pn=1;pn<=std::min(base.nTiles,int(cores)/pm);++pn){
   if(pm*pn<(3*cores+3)/4||(pm==base.pM&&pn==base.pN))continue;
   auto p=base;p.pM=pm;p.pN=pn;p.tasks=pm*pn;p.blocks=p.tasks;
   auto q=bmms11r2::SingleWavePeak(p);if(q.tiles>peak.tiles)continue;
   plans.push_back(p);wsBytes=std::max(wsBytes,bmms11r2::WorkspaceBytes(p));
  }
  auto prefix=root+"/case"+std::to_string(id);
  auto ah=readbin(prefix+"_a.bin",B*M*K*2),bh=readbin(prefix+"_b.bin",B*N*K*2),gh=readbin(prefix+"_golden.bin",B*8);
  std::vector<double>gold(B);std::memcpy(gold.data(),gh.data(),B*8);std::vector<float>got(B);std::vector<uint32_t>poison(B,0x7fc00001u);
  void*a=nullptr,*b=nullptr,*y=nullptr,*ws=nullptr;
  ck(aclrtMalloc(&a,ah.size(),ACL_MEM_MALLOC_HUGE_FIRST),"a");ck(aclrtMalloc(&b,bh.size(),ACL_MEM_MALLOC_HUGE_FIRST),"b");ck(aclrtMalloc(&y,B*4,ACL_MEM_MALLOC_HUGE_FIRST),"y");ck(aclrtMalloc(&ws,wsBytes,ACL_MEM_MALLOC_HUGE_FIRST),"ws");
  ck(aclrtMemcpy(a,ah.size(),ah.data(),ah.size(),ACL_MEMCPY_HOST_TO_DEVICE),"a copy");ck(aclrtMemcpy(b,bh.size(),bh.data(),bh.size(),ACL_MEMCPY_HOST_TO_DEVICE),"b copy");
  auto verify=[&](){ck(aclrtMemcpy(got.data(),B*4,y,B*4,ACL_MEMCPY_DEVICE_TO_HOST),"output");double ratio=0;
   for(int j=0;j<B;++j){double r=std::fabs(got[j]-gold[j])/(1e-4+1e-4*std::fabs(gold[j]));if(!std::isfinite(got[j])||r>1){std::fprintf(stderr,"FAIL %d\n",id);std::exit(3);}ratio=std::max(ratio,r);}return ratio;};
  // Every tested plan must pass independently before timing it.
  for(auto&p:plans){ck(aclrtMemcpy(y,B*4,poison.data(),B*4,ACL_MEMCPY_HOST_TO_DEVICE),"poison");launch_direct(a,b,y,ws,p,dt,ta,tb,stream);ck(aclrtSynchronizeStreamWithTimeout(stream,10000),"verify sync");verify();}
  for(int w=0;w<windows;++w){
   for(int order=0;order<int(plans.size())+2;++order){
    int j=(order==0||order==int(plans.size())+1)?0:(w%2?int(plans.size())-order:order-1);auto p=plans[j];auto q=bmms11r2::ExistingPeak(p);
    for(int warm=0;warm<8;++warm)launch_direct(a,b,y,ws,p,dt,ta,tb,stream);
    ck(aclrtSynchronizeStreamWithTimeout(stream,10000),"warmup");
    aclrtEvent begin=nullptr,end=nullptr;ck(aclrtCreateEvent(&begin),"begin");ck(aclrtCreateEvent(&end),"end");
    ck(aclrtRecordEvent(begin,stream),"start");for(int rep=0;rep<calls;++rep)launch_direct(a,b,y,ws,p,dt,ta,tb,stream);
    ck(aclrtRecordEvent(end,stream),"stop");ck(aclrtSynchronizeStreamWithTimeout(stream,10000),"sync");float ms=0;ck(aclrtEventElapsedTime(&ms,begin,end),"time");double err=verify();
    std::fprintf(out,"{\"case\":%d,\"M\":%lld,\"N\":%lld,\"K\":%lld,\"dtype\":%d,\"ta\":%d,\"tb\":%d,\"window\":%d,\"order\":%d,\"baseline\":%s,\"pM\":%d,\"pN\":%d,\"tasks\":%d,\"blocks\":%d,\"peak_tiles\":%llu,\"peak_cells\":%llu,\"peak_input\":%llu,\"us\":%.8f,\"max_tolerance_ratio\":%.9g}\n",id,(long long)M,(long long)N,(long long)K,dt,ta,tb,w,order,j==0?"true":"false",p.pM,p.pN,p.tasks,p.blocks,(unsigned long long)q.tiles,(unsigned long long)q.cells,(unsigned long long)q.input,ms*1000.0/calls,err);std::fflush(out);
    ck(aclrtDestroyEvent(begin),"destroy");ck(aclrtDestroyEvent(end),"destroy");
   }
  }
  std::printf("PASS %d plans=%zu\n",id,plans.size());ck(aclrtFree(ws),"ws free");ck(aclrtFree(y),"y free");ck(aclrtFree(b),"b free");ck(aclrtFree(a),"a free");
 }
 std::fclose(out);ck(aclrtDestroyStream(stream),"stream free");ck(aclrtResetDevice(0),"reset");ck(aclFinalize(),"finalize");return 0;
}
'''
(lab/'sweep_plans.asc').write_bytes((event[:start]+dispatch+body).encode())
cm=(lab/'CMakeLists.txt').read_text(encoding='utf-8')
assert 'add_executable(sweep_plans' not in cm
cm+='''\nadd_executable(sweep_plans sweep_plans.asc)
target_compile_definitions(sweep_plans PRIVATE BMMS_KERNEL_HEADER="r40.asc" BMMS_VARIANT="sweep")
target_link_libraries(sweep_plans PRIVATE tiling_api register platform unified_dlog dl m graph_base)
target_include_directories(sweep_plans PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_options(sweep_plans PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=dav-2201>)
'''
(lab/'CMakeLists.txt').write_bytes(cm.encode())
script='''#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_narrow_20260929
cmake -S . -B build >logs/plan_sweep_configure.log 2>&1
cmake --build build --target sweep_plans -j2 >logs/plan_sweep_build.log 2>&1
./build/sweep_plans cases/holdout.txt 3 results/plan_sweep.jsonl >logs/plan_sweep.log 2>&1
echo SWEEP_DONE
'''
(lab/'plan_sweep.sh').write_bytes(script.encode())
print('Feedback saved; sweep prepared')
