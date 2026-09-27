"""Replay unchanged device code under original and diagnostic single-group plans."""
from pathlib import Path
import importlib.util,json,shutil,subprocess,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;BUILD=HERE/'cpu_build'
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
b=load('diag_builder',HERE/'build.py');old=load('split_checks',ROOT/'V11_split_k/run_checks.py')
old.BUILD=BUILD;old.native.BUILD=BUILD;old.native.previous.BUILD=BUILD;old.native.previous.flex.BUILD=BUILD;old.native.previous.flex.redirect(old.native.previous.flex.prior)

TREE=r'''
template<class T,bool SUM>
void treeProbe(int B,int L,int K,int cores,bool reverse){
    auto p=bmms83::MakeTree(B,L,K,cores);if(DIAG_STRESS)p.workers=1;
    std::vector<T>a(size_t(B)*(SUM?L:1)*K),b(size_t(B)*K*(SUM?1:L));
    std::mt19937 rng(812+L+K);std::uniform_int_distribution<int> rand(-4,4);
    for(auto&v:a)v=T(rand(rng)/32.f);for(auto&v:b)v=T(rand(rng)/32.f);
    std::vector<double>gold(B,0);std::vector<float>y(B,NAN);
    for(int batch=0;batch<B;++batch){double score=SUM?0:-INFINITY;
        for(int l=0;l<L;++l){double dot=0;
            for(int k=0;k<K;++k)dot+=double(float(a[SUM?(size_t(batch)*K+k)*L+l:size_t(batch)*K+k]))*
                float(b[SUM?size_t(batch)*K+k:(size_t(batch)*K+k)*L+l]);
            if(SUM)score+=dot;else score=std::max(score,dot);}
        gold[batch]=score;}
    std::vector<float>part(bmms83::TreePartialBytes<SUM>(p)/4,NAN);
    Mock::Context ctx(p.workers);ctx.add(a.data(),a.size()*sizeof(T),true);ctx.add(b.data(),b.size()*sizeof(T),true);
    if(!part.empty())ctx.add(part.data(),part.size()*4,false);ctx.add(y.data(),y.size()*4,false);
    RingAudit::active=nullptr;ReductionAudit::active=nullptr;SplitAudit::active=nullptr;
    workers(p.workers,ctx,[&](int){bmms83::TreeGemv<T,SUM>((GM_ADDR)a.data(),(GM_ADDR)b.data(),(GM_ADDR)y.data(),(GM_ADDR)part.data(),p);},reverse);
    assess(std::string("tree_")+(std::is_same_v<T,half>?"f16":"b16")+std::to_string(SUM)+"_"+std::to_string(B)+"_"+std::to_string(L)+"_"+std::to_string(K),y,gold);
}
int main(){try{
    for(int rev=0;rev<2;++rev){
        for(auto shape:std::vector<std::array<int,5>>{
            {1,16,32,64,20},{1,32,144,32,20},{1,144,32,64,20},{3,144,272,128,20},
            {1,112,144,256,20},{3,128,128,544,20},{1,128,256,1024,20},
            {1,144,272,256,2},{3,144,272,288,4}}){
            layouts<half>(shape,0,rev);layouts<bfloat16_t>(shape,1,rev);
        }
        for(auto lk:std::vector<std::array<int,2>>{{64,256},{144,96}}){
            treeProbe<half,false>(3,lk[0],lk[1],20,rev);treeProbe<half,true>(3,lk[0],lk[1],20,rev);
            treeProbe<bfloat16_t,false>(3,lk[0],lk[1],20,rev);treeProbe<bfloat16_t,true>(3,lk[0],lk[1],20,rev);
        }
    }
    std::cout<<std::setprecision(12)<<"{\"source_runs\":"<<checks<<",\"repeat_checks\":"<<repeats
        <<",\"strict_misses\":"<<strictMisses<<",\"combined_misses\":"<<combinedMisses
        <<",\"native_runs\":"<<smallRoutes<<",\"residual_runs\":"<<residualRoutes<<",\"macro_runs\":"<<macroRoutes
        <<",\"tree_runs\":"<<checks-denseRuns<<",\"max_abs\":"<<maxError<<",\"output_bits\":{";
    bool first=true;for(auto&[k,v]:outputs){if(!first)std::cout<<",";first=false;std::cout<<"\""<<k<<"\":[";
        for(size_t i=0;i<v.size();++i){if(i)std::cout<<",";std::cout<<v[i];}std::cout<<"]";}
    std::cout<<"}}\n";return strictMisses||combinedMisses?2:0;
}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
'''

def harness(stress):
    source=old.native.harness('R14');source=source[:source.index('int main(){try{')]
    anchor='    const bool reuse=useSmall&&NATIVE_VARIANT==21&&p.nTiles>=2*p.pN;'
    source=b.once(source,anchor,'    if(DIAG_STRESS){'+b.ONE_GROUP+'}\n'+anchor)
    # The mutation is exactly the host intervention used by the three diagnostics.
    for name in ['C00_NATIVE_1G','C01_R03_1G','X6_01_MACRO_1G']:
        assert 'if(true){'+b.ONE_GROUP+'}' in (b.OUT/(name+'.asc')).read_text(encoding='utf-8')
    return '#define DIAG_STRESS '+str(stress)+'\n'+source+TREE

def main():
    b.verify();BUILD.mkdir(exist_ok=True);compiler=shutil.which('g++');assert compiler
    results={}
    for mode in [0,1]:
        old.prepare()
        base=b.BASE.read_text(encoding='utf-8')
        tree=b.between(base,'struct TreePlan {','} // namespace bmms83\n\n#define BMMS83_NATIVE')
        common=BUILD/'common_extracted.hpp'
        b.write(common,common.read_text(encoding='utf-8')+'\nnamespace bmms83 {\n'+tree+'\n}\n')
        source=harness(mode);b.write(BUILD/'plan_source.cpp',source)
        exe=BUILD/('plans_'+str(mode)+'.exe')
        subprocess.run([compiler,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-pthread','-DCHECK_R01=1','-DCHECK_R04=1',str(BUILD/'plan_source.cpp'),'-o',str(exe)],check=True)
        run=subprocess.run([str(exe)],capture_output=True,text=True,timeout=600)
        b.write(BUILD/(str(mode)+'.stderr.txt'),run.stderr)
        if run.returncode:raise RuntimeError(run.stderr[-3000:]+run.stdout[-3000:])
        data=json.loads(run.stdout);assert data['strict_misses']==data['combined_misses']==0
        results[str(mode)]=data;b.write(HERE/('CPU_RESULT_'+str(mode)+'.json'),json.dumps(data,indent=2)+'\n')
        print(json.dumps({k:v for k,v in data.items() if k!='output_bits'}),flush=True)
    assert results['0']['output_bits']==results['1']['output_bits']
    inherited=json.loads((ROOT/'V11_split_k/CHECKS.json').read_text(encoding='utf-8'))
    for rel,digest in inherited['artifacts'].items():assert b.sha(ROOT/rel)==digest,rel
    assert inherited['K1_outputs_equal_R14_bitwise'] and inherited['sources']['R23_K1_CONTROL.asc']==b.K1_SHA
    report={'scope':'unchanged actual Native/R03/macro/tree device code replayed with old and diagnostic schedules in CPU model',
        'runs':{k:{n:v for n,v in r.items() if n!='output_bits'} for k,r in results.items()},'outputs_equal_bitwise':True,
        'SplitK_K1_coverage_inherited_from':'V11_split_k/CHECKS.json','CANN_or_NPU_test':False,
        'fallback_core_argument_checked_by':'HOST_CHECKS.json; existing fallback implementation unchanged, not newly device-replayed',
        'artifacts':{**inherited['artifacts'],**{p.relative_to(ROOT).as_posix():b.sha(p) for p in [HERE/'build.py',Path(__file__),ROOT/'V11_split_k/CHECKS.json',ROOT/'V11_split_k/run_checks.py']}},
        'sources':{p.name:b.sha(p) for p in b.OUT.glob('*.asc')}}
    for p in [HERE/'CPU_CHECKS.json',b.OUT/'CPU_CHECKS.json']:b.write(p,json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
