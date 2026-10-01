from pathlib import Path
import subprocess,json
r=Path(__file__).resolve().parent;d=r/'host_c1112';d.mkdir(exist_ok=True)
src=(r.parent/'BMMS_V12/v12_baseline_r19.asc').read_text(encoding='utf-8')
t=(r/'host_c12/host.cpp').read_text(encoding='utf-8').split('using Plan=bmms11r2::Plan;\nvoid need')[0]
a=src.index('static inline uint64_t RingBytes',src.index('namespace bmms11r2 {'));b=src.index('template<class T,bool TA,bool TB>',a)
t+='\nnamespace bmms11r2{'+src[a:b]+'}\n'
a=src.index('namespace bmms1219 {');b=src.index('// BMMS1219_HOST_MODEL_END',a)
t+=src[a:b]+'}\n'
s22=(r.parent/'BMMS_V12/v12_r22_dense_nz_pitch.asc').read_text(encoding='utf-8')
a=s22.index('namespace bmms1222 {');b=s22.index('static inline bool TryLaunch',a)
t+=s22[a:b]+'}\n'
t+=r'''
void need(bool b){if(!b)throw std::runtime_error("host invariant");}
int main(){
 int total=0,switched=0;int bins[3][2]{};
 for(int M=1024;M<2048;M+=16)for(int N=2048;N<=8192;N+=16){
   auto a=bmms11r2::MakePlan(1,M,N,1536,20),b=bmms1220::MakePlan(1,M,N,1536,20);
   bool hit=bmms1220::Changed(a,b);++total;switched+=hit;int bin=N<4096?0:(N<6144?1:2);++bins[bin][hit];
 }
 uint64_t maxWs=0,maxUb=0;int checks=0;
 for(int M:{1024,1040,1536,2032})for(int N:{2048,2064,4096,6144,8192})
 for(int K:{1536,1568,1664,1760,2048,2080,3072,4064})for(int c:{1,2,20,32,64})
 for(int layout=0;layout<4;++layout){
   auto p=bmms1219::MakePlan(M,N,K,c,layout/2,layout%2);auto q=bmms11r2::MakePlan(1,M,N,K,c);
   need(p.cube.pM==q.pM&&p.cube.pN==q.pN&&p.cube.blocks==q.blocks);
   need(p.cube.M==M&&p.cube.N==N&&p.cube.K==K&&p.cube.blocks<=c);
   need(bmms1222::ValidPlan(p,c)&&bmms1222::Eligible(1,M,N,K,1,c));
   need(bmms1222::Prefer(M,N,K,layout/2,layout%2)==bmms1219::PreferNz(p.cube,layout/2,layout%2));
   for(auto desc:{p.a,p.b}){
     need(desc.srcRows==desc.dstRows&&desc.srcCols==desc.dstCols&&desc.srcRows%16==0&&desc.srcCols%16==0);
     // Each job covers a unique row slab / column panel. NZ offset for a
     // 16-column block spans [c*height+r*16, c*height+(r+rows)*16).
     int64_t area=0;
     for(int job=0;job<desc.jobs;++job){int panels=(desc.dstCols+127)/128;
       int row=(job/panels)*desc.rowsPerJob,col=job%panels*128;
       int rows=std::min(desc.rowsPerJob,desc.dstRows-row),cols=std::min(128,desc.dstCols-col);
       need(rows>0&&cols>0&&rows%16==0&&cols%16==0&&rows*cols<=32768);
       for(int j=0;j<cols;j+=16){int64_t first=int64_t(col+j)*desc.dstRows+row*16;
         need(first>=0&&first+rows*16<=int64_t(desc.dstRows)*desc.dstCols);}
       area+=rows*cols;
     }
     need(area==int64_t(desc.dstRows)*desc.dstCols);
   }
   auto ws=bmms1219::WorkspaceBytes(p),ub=bmms1219::AppUbBytes(p);
   need(ws<=bmms1219::MAX_WORKSPACE_BYTES&&ub<=bmms1219::UB_BUDGET_BYTES);
   maxWs=std::max(maxWs,ws);maxUb=std::max(maxUb,ub);++checks;
 }
 std::cout<<"{\"geometry_count\":"<<total<<",\"r21_changed\":"<<switched
 <<",\"bins_no_yes\":[["<<bins[0][0]<<","<<bins[0][1]<<"],["<<bins[1][0]<<","<<bins[1][1]<<"],["<<bins[2][0]<<","<<bins[2][1]<<"]],\"nz_bounds_checks\":"<<checks
 <<",\"max_workspace_bytes\":"<<maxWs<<",\"max_app_ub_bytes\":"<<maxUb<<",\"passed\":true}\n";
}
'''
(d/'host.cpp').write_text(t,encoding='utf-8')
subprocess.run(['C:/msys64/ucrt64/bin/g++.exe','-O2','-std=c++17',str(d/'host.cpp'),'-o',str(d/'host.exe')],check=True)
p=subprocess.run([str(d/'host.exe')],check=True,capture_output=True,text=True)
(d/'RESULTS.json').write_text(p.stdout,encoding='utf-8');print(p.stdout)
