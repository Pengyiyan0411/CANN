from pathlib import Path
import subprocess,json
r=Path(__file__).resolve().parents[1];o=r/'V12_npu_lab/results/parallel_epilogue_20260929'
old=(r/'V12_npu_lab/results/b_resident_20260929/audit_r47.cpp').read_text(encoding='utf-8')
prefix=old.split('namespace bmms1247 {')[0]
s=(r/'BMMS_V12/v12_r49_case12_fractional_guarded.asc').read_text(encoding='utf-8');a=s.index('namespace bmms1249 {');b=s.index('template<class T,bool TA,bool TB>',a)
body='int main(){'+old.split('int main(){',1)[1]
body=body.replace('bmms1247','bmms1249')
code=prefix+s[a:b]+'}\n'+body
(o/'audit_r49.cpp').write_text(code,encoding='utf-8');subprocess.run(['g++','-O2','-std=c++17',str(o/'audit_r49.cpp'),'-o',str(o/'audit_r49.exe')],check=True)
z=subprocess.check_output([str(o/'audit_r49.exe')],text=True);json.loads(z);(o/'audit_r49.json').write_text(z,encoding='utf-8');print(z)
