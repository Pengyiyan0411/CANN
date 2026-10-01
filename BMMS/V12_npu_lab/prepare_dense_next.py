from pathlib import Path
import json,hashlib,shutil
r=Path(__file__).resolve().parents[1];o=r/'BMMS_V12';h=r/'V12_npu_lab/harness'
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
base=(o/'v12_r30_dense_macro_prefetch.asc').read_bytes()
sha=hashlib.sha256(base).hexdigest();assert sha=='9ac17c7b6f793cf043ee8d150479f42a1423a73ffe5c877b2456d16396d1fa17'
(o/'v12_baseline_r30.asc').write_bytes(base)
d=r/'V12_results/2026-09-28_r30_feedback';d.mkdir(parents=True,exist_ok=True)
times=[2.50,4.53,5.10,6.41,6.51,15.01,9.60,46.78,70.62,84.55,97.09,115.12,15.35,13.67,11.37]
refs=[1.22,1.58,2.13,2.92,1.89,7.07,3.68,14.88,50.68,72.39,74.82,91.20,5.14,5.40,4.05]
dump(d/'RESULTS.json',dict(version='v12_r30',source_sha256=sha,source_attribution='Conversation: response to r30 delivery; user confirms effective',independent_runs=1,duplicate_attachment=True,cases=[dict(case=i+1,pass_=True,error_display_pct=0,latency_us=t,reference_us=refs[i]) for i,t in enumerate(times)]))
img=Path(r'E:\Tencent Files\3232896164\nt_qq\nt_data\Pic\2026-09\Ori\feee6808f38ea7f2248d51cea3ff8ff5.png')
if img.exists():shutil.copyfile(img,d/'judge_r30.png')
main=json.loads((o/'MAINLINE.json').read_text(encoding='utf-8'))
main.update(accepted_version='v12_r30',accepted_sota='v12_baseline_r30.asc',accepted_sha256=sha,previous_sota='v12_baseline_r19.asc',acceptance_basis='User confirms r30 effective; single Judge result (duplicate images), all15 Pass, Case11 97.09us, Case12 115.12us, Case8 46.78us, Case15 11.37us. Local race/init/sync findings remain unresolved.',naming='v12_rxx; r30 accepted after Judge feedback',recommended_candidate=None,next_action='Validate independent r31 compact LoadData and r32 short-K macro-prefetch extension against r30; preserve accepted source.')
for x in main['candidates']:
 if x['version']=='v12_r30':x.update(status='Accepted by user after Judge15/15Pass; local sanitizer limitations remain open',judge_feedback='../V12_results/2026-09-28_r30_feedback/RESULTS.json')
dump(o/'MAINLINE.json',main)
p=o/'README.md';lines=p.read_text(encoding='utf-8').splitlines();lines[2]='**当前主线：** [r30](v12_baseline_r30.asc)。用户确认有效：Judge 15/15 Pass，Case11 97.09μs、Case12 115.12μs，Case8 46.78μs、Case15 11.37μs。两张相同截图按一次测试记录。r19保留回退；本地竞争/初始化告警仍未闭环。以下为历史记录。';p.write_text('\n'.join(lines)+'\n',encoding='utf-8')
raw=base.decode();a=raw.index('// BMMS1230_BEGIN');b=raw.index('// BMMS1230_END',a)+len('// BMMS1230_END');module=raw[a:b]
mod=module.replace('1230','1231')
a=mod.index('        AscendC::LoadData2DParams la{};');b=mod.index('        AscendC::SetFlag<AscendC::HardEvent::MTE1_M>',a)
mod=mod[:a]+'''        AscendC::LoadData2DParams la{};la.ifTranspose=TA;
        if constexpr(TA){
            la.repeatTimes=kr0/16;la.srcStride=1;
            for(int i=0;i<ar/16;++i)
                AscendC::LoadData(da[i*kr0*16],sa[i*kr1*16+kk*16],la);
        }else{
            // Same A fractals as r30, reordered across M with strided L0 writes.
            la.repeatTimes=ar/16;la.srcStride=1;la.dstGap=kr0/16-1;
            for(int j=0;j<kr0/16;++j)
                AscendC::LoadData(da[j*256],sa[(kk/16+j)*ar*16],la);
        }
        AscendC::LoadData2DParams lb{};lb.ifTranspose=!TB;
        if constexpr(TB){
            // K-by-N fractals are consecutive at both endpoints.
            lb.repeatTimes=(kr0/16)*(br/16);lb.srcStride=1;
            AscendC::LoadData(db,sb[(kk/16)*br*16],lb);
        }else{
            lb.repeatTimes=br/16;lb.srcStride=kr1/16;
            for(int j=0;j<kr0/16;++j)
                AscendC::LoadData(db[j*br*16],sb[(kk+j*16)*16],lb);
        }
'''+mod[b:]
def save(v,name,mod,desc,eventbase):
 payload=('\n'+mod+'\n\n').encode();ix=base.index(b'extern "C" void run_kernel');data=base[:ix]+payload+base[ix:]
 hook=f'    if(bmms12{v}::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'.encode()
 ix=data.index(b'    if(bmms1230::TryLaunch');data=data[:ix]+hook+data[ix:]
 assert data.replace(payload,b'',1).replace(hook,b'',1)==base
 (o/name).write_bytes(data);(h/f'r{v}.asc').write_bytes(data)
 dump(o/f'v12_r{v}_manifest.json',dict(version=f'v12_r{v}',file=name,sha256=hashlib.sha256(data).hexdigest(),parent='v12_baseline_r30.asc',status='experimental; pending validation',change=desc,parent_byte_recovery=True))
 event=(h/'event_bench_r30.asc').read_text(encoding='utf-8').replace('1230',f'12{v}')
 event=event.replace('DISPATCH(bmms11r2);',f'DISPATCH({eventbase});').replace('"macro_store":"r19"',f'"r{v}":"r30"')
 (h/f'event_bench_r{v}.asc').write_text(event,encoding='utf-8',newline='\n')
 cm=h/'CMakeLists.txt';t=cm.read_text(encoding='utf-8');block=t[t.index('add_executable(bench_r30 '):];block=block[:block.index('add_custom_target(r30_build')]+ 'add_custom_target(r30_build DEPENDS bench_r30 event_bench_r30)\n'
 if f'add_executable(bench_r{v} ' not in t:t+='\n'+block.replace('r30',f'r{v}')
 cm.write_text(t,encoding='utf-8',newline='\n')
 print(v,name,len(data))
save(31,'v12_r31_dense_compact_load.asc',mod,'r30 geometry and prefetch; fewer L1-to-L0 LoadData calls; accumulation unchanged','bmms1230')
# Independent extension: delegate to EXACT r30 device implementation, retaining its original long-K entry.
prefix='''// BMMS1232_BEGIN
namespace bmms1232 {
using Plan=bmms1230::Plan;using bmms1230::MakePlan;using bmms1230::AlignedPitch;
static inline bool Eligible(int B,int M,int N,int K,int cores){
    return B==1&&M>=1024&&M<=8192&&N>=1024&&N<=8192&&K>=1024&&K<1536&&bmms11r2::Eligible(B,M,N,K,cores);
}
template<class T,bool TA,bool TB>
__aicore__ inline void Entry(GM_ADDR a,GM_ADDR b,GM_ADDR y,GM_ADDR ring,GM_ADDR part,Plan p){
    bmms1230::Entry<T,TA,TB>(a,b,y,ring,part,p);
}
}
'''
a=module.index('#define BMMS1230_KERNEL')
short=prefix+module[a:].replace('1230','1232')
save(32,'v12_r32_shortk_macro_prefetch.asc',short,'Add aligned B1 M/N>=1024 K[1024,1536) route using exact r30 kernel; r30 Case11/12 entry byte-preserved','bmms11r2')
