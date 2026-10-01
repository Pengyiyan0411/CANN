from pathlib import Path
import subprocess,shutil,json
H=Path(__file__).resolve().parent;OUT=H.parent/'BMMS_V12'
src=(H/'host_build/host.cpp').read_text().split('uint64_t checks=0,')[0]
src+='''
int main(){bool comma=false;std::cout<<"[";
for(int B:{1,2})for(int M:{1024,2048})for(int N:{1024,2048}){
    auto p=bmms11r2::MakePlan(B,M,N,1024,20);
    if(comma)std::cout<<",";comma=true;
    std::cout<<"{\\"B\\":"<<B<<",\\"M\\":"<<M<<",\\"N\\":"<<N<<",\\"K\\":1024,\\"cores\\":20,\\"pM\\":"<<p.pM<<",\\"pN\\":"<<p.pN
       <<",\\"tasks\\":"<<p.tasks<<",\\"blocks\\":"<<p.blocks<<",\\"eligible\\":"<<(bmms1204::Eligible(B,M,N,1024,20)?"true":"false")
       <<",\\"reusesA\\":"<<(bmms1204::ReusesA(p)?"true":"false")<<"}";
}std::cout<<"]\\n";}
'''
(H/'host_build/review_plans.cpp').write_text(src)
p=subprocess.run([shutil.which('g++'),'-std=c++20','-O2',str(H/'host_build/review_plans.cpp'),'-o',str(H/'host_build/review_plans.exe')],capture_output=True,text=True)
assert p.returncode==0,p.stderr
p=subprocess.run([str(H/'host_build/review_plans.exe')],capture_output=True,text=True);assert p.returncode==0,p.stderr
data=json.loads(p.stdout)
(OUT/'v12_r04_review_plan_examples.json').write_text(json.dumps({'scope':'synthetic legal shape examples from actual planner; not inferred Judge shapes','examples':data},indent=2)+'\n')
print(json.dumps(data,indent=2))
