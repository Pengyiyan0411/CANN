from pathlib import Path
import subprocess,json
r=Path(__file__).resolve().parents[1]
o=r/'V12_npu_lab/results/b_resident_20260929'
old=(o/'audit_r46.cpp').read_text(encoding='utf-8')
prefix=old.split('namespace bmms1246 {')[0]
s=(r/'BMMS_V12/v12_r47_case12_fractional_rows.asc').read_text(encoding='utf-8')
a=s.index('namespace bmms1247 {');b=s.index('template<class T,bool TA,bool TB>',a)
body='int main(){'+old.split('int main(){',1)[1]
body=body.replace('bmms1246','bmms1247')
body=body.replace('std::vector<int> jobs(2*p.mTiles,0);','std::vector<int> jobs(2*p.mTiles,0), finalRows(M,0);')
body=body.replace('rows+=vr;', 'rows+=vr;for(int m=mStart;m<mStart+vr;++m)++finalRows[m];')
body=body.replace('for(int c:jobs)assert(c==1);', 'for(int c:jobs)assert(c==1);for(int c:finalRows)assert(c==1);')
body=body.replace('2*(2*p.blocks*8*4)+32','2*M*4')
body=body.replace('size_t(2*p.blocks)*8*4','size_t(M)*4')
code=prefix+s[a:b]+'}\n'+body
(o/'audit_r47.cpp').write_text(code,encoding='utf-8')
subprocess.run(['g++','-O2','-std=c++17',str(o/'audit_r47.cpp'),'-o',str(o/'audit_r47.exe')],check=True)
z=subprocess.check_output([str(o/'audit_r47.exe')],text=True)
json.loads(z);(o/'audit_r47.json').write_text(z,encoding='utf-8');print(z)
