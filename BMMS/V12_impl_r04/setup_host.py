"""Reuse the recording harness, with R52 / r04 / accepted r03 as the three lanes."""
import build as b
s=(b.ROOT/'V12_impl_r02_r03/check_host.py').read_text()
s=s.replace('src=b.BASE.read_text(encoding=\'utf-8\')',"src=(b.OUT/'V12_BASELINE_R52.asc').read_text(encoding='utf-8')")
s=s.replace('m2=b.module2(src);m3=b.module3(src)','m2=b.module(src);m3=b.previous.module3(src)')
s=s.replace("[b.BASE]+[b.OUT/(b.NAMES[r]+'.asc') for r in [2,3]]","[b.OUT/'V12_BASELINE_R52.asc',b.OUT/(b.NAME+'.asc'),b.BASE]")
s=s.replace("([f'bmms120{i+1}'] if i else [])","(['bmms1203','bmms1204'] if i==1 else ['bmms1203'] if i==2 else [])")
s=s.replace('1202','1204')
s=s.replace("r['source_sha256']={b.NAMES[i]:hashlib.sha256((b.OUT/(b.NAMES[i]+'.asc')).read_bytes()).hexdigest() for i in [2,3]}","r['source_sha256']=hashlib.sha256((b.OUT/(b.NAME+'.asc')).read_bytes()).hexdigest();r['parent_sha256']=b.SHA")
s=s.replace('v12_r02_r03_host_checks.json','v12_r04_host_checks.json')
b.write(b.H/'check_host.py',s)
s=(b.ROOT/'V12_impl_r02_r03/host_checks.cpp.in').read_text().replace('r02','r04')
s=s.replace('128ULL*K*2+2ULL*256*128*2','4ULL*128*256*2+2ULL*256*256*2')
s=s.replace('want2.strategy=1202','want2.strategy=1204')
line='    need(r2==want2,"r04 changed unintended metadata, plan, workspace or route");\n'
s=b.once(s,line,'')
s=b.once(s,'    need(r3==want3,', '    if(hit3){want2.strategy=1203;need(r2==r3,"accepted Case2 path changed");}\n'+line+'    need(r3==want3,')
s=b.once(s,'    ++checks;','    ++checks;') if '    ++checks;' in s else s
b.write(b.H/'host_checks.cpp.in',s)
print('Host harness prepared with accepted r03 as preservation lane.')
