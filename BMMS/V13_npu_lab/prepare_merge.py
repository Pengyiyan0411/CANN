from pathlib import Path
import difflib, hashlib, json, shutil

root=Path(__file__).resolve().parents[1]
v=root/'BMMS_V13'; lab=root/'V13_npu_lab/c12_merge_20261001'
for p in (v, v/'evidence', lab, lab/'results'): p.mkdir(parents=True,exist_ok=True)
r41=(root/'BMMS_V12/v12_baseline_r41.asc').read_bytes().decode()
r72=(root/'BMMS_V12/v12_r72_small_cases_index_padded.asc').read_bytes().decode()
branch=Path('C:/Users/cc/Downloads/C12R2_NBIT1.asc').read_bytes().decode()
shutil.copyfile('C:/Users/cc/Downloads/C12R2_NBIT1.asc',v/'evidence/C12R2_NBIT1.asc')
shutil.copyfile('C:/Users/cc/Downloads/新总结.ini',v/'evidence/新总结.ini')
start=branch.index('// BMMS12OPT_BEGIN');end=branch.index('// BMMS12OPT_END',start)+len('// BMMS12OPT_END')
module=branch[start:end]
hook='    if(bmms12opt::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
without=branch[:start]+branch[end:]
without=without.replace(hook,'')
# Differences outside the isolated module and launch hook must be comments/blank lines only.
diff=list(difflib.unified_diff(r41.splitlines(True),without.splitlines(True),fromfile='r41',tofile='branch_without_c12'))
changes=[l[1:].strip() for l in diff if l[:1] in '+-' and l[:3] not in ('+++','---')]
def code_lines(s):
    return [x.strip() for x in s.splitlines() if x.strip() and not x.strip().startswith('//')]
assert code_lines(r41)==code_lines(without),'Non-comment code outside module changed'
(v/'evidence/branch_outside_module.diff').write_text(''.join(diff),encoding='utf-8')
enc='''    // Strong timing encoder for bit 1 of q=(N-4096)/64.
    const int qN=(N-4096)/64;
    if(((qN>>1)&1)!=0){
        p.pM=1; p.pN=1; p.tasks=B; p.blocks=1;
    }
'''
assert module.count(enc)==1
clean=module.replace(enc,'')
assert 'qN' not in clean
before='    if(bmms1230::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;'
assert r72.count(before)==1
anchor='extern "C" void run_kernel('
assert r72.count(anchor)==1
merged=r72.replace(anchor,clean+'\n\n'+anchor).replace(before,hook+before)
assert merged.replace(clean+'\n\n','').replace(hook,'')==r72
cleanbranch=r41.replace(anchor,clean+'\n\n'+anchor).replace(before,hook+before)
for name,src in [('v13_r1_baseline_r72.asc',r72),('v13_r2_case12_o10.asc',merged)]:
    target=v/name
    assert not target.exists() or target.read_bytes()==src.encode()
    target.write_bytes(src.encode())
for name,src in [('r1.asc',r72),('r2.asc',merged),('branch_clean.asc',cleanbranch),('c12_module.asc',clean)]:
    (lab/name).write_bytes(src.encode())
(v/'evidence/probe_removal.diff').write_text(''.join(difflib.unified_diff(module.splitlines(True),clean.splitlines(True),fromfile='supplied_NBIT1',tofile='clean_O10')),encoding='utf-8')
oldmod=r41[r41.index('// BMMS1230_BEGIN'):r41.index('// BMMS1230_END')+len('// BMMS1230_END')]
(v/'evidence/r30_to_o10.diff').write_text(''.join(difflib.unified_diff(oldmod.splitlines(True),clean.splitlines(True),fromfile='r41_r30_route',tofile='O10_clean')),encoding='utf-8')
shutil.copyfile(root/'V12_npu_lab/small_20261001/main.asc',lab/'main.asc')
shutil.copyfile(root/'V12_npu_lab/small_20261001/run_screen.py',lab/'run_screen.py')
(lab/'CMakeLists.txt').write_text('''cmake_minimum_required(VERSION 3.16)
find_package(ASC REQUIRED)
project(bmms_v13 LANGUAGES ASC CXX)
set(CMAKE_CXX_STANDARD 17)
foreach(v r2)
 add_executable(bench_${v} main.asc)
 target_compile_definitions(bench_${v} PRIVATE BMMS_KERNEL_HEADER="${v}.asc" BMMS_VARIANT="${v}")
 target_link_libraries(bench_${v} PRIVATE tiling_api register platform unified_dlog dl m graph_base)
 target_compile_options(bench_${v} PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=dav-2201>)
endforeach()
''',encoding='utf-8')
meta=dict(line='V13',accepted_sota='v13_r1_baseline_r72.asc',accepted_sha256=hashlib.sha256(r72.encode()).hexdigest(),acceptance_basis='User explicitly reports clear Case2-4 improvement in r72 and promotes it as v13-r1.',active_candidate='v13_r2_case12_o10.asc',candidate_sha256=hashlib.sha256(merged.encode()).hexdigest(),candidate_status='merged; validation pending; Judge15 required',parents=['v12_r72_small_cases_index_padded.asc','C12R2_NBIT1.asc'],isolation_verified=True,removed_probe=True)
(v/'MAINLINE.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(meta,ensure_ascii=False,indent=2))
print('Outside-module diff:', ''.join(diff)[:4000])
