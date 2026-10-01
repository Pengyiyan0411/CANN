from pathlib import Path
import json,hashlib
root=Path(__file__).resolve().parents[1];v=root/'BMMS_V13'
m=json.loads((v/'MAINLINE.json').read_text(encoding='utf-8'))
m['candidate_status']='Judge FAIL reported by user; failure type and failing case pending; withdrawn from recommended submission'
m['judge_r2_feedback']={'result':'FAIL','source':'user message: 提交r2 fail了','failure_type':'unknown','case':'unknown','sha256':hashlib.sha256((v/'v13_r2_case12_o10.asc').read_bytes()).hexdigest()}
m['recommended_submission']='v13_r1_baseline_r72.asc'
(v/'MAINLINE.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for name in ('README.md','VALIDATION.md','CASE12_BRANCH_ANALYSIS.md'):
    p=v/name;s=p.read_text(encoding='utf-8')
    notice='> 更新：用户反馈 r2 提交 FAIL，已撤回推荐；失败类型/点号待核实。已接受基线仍为 r1。下文为提交前的分析与本地验证记录。\n\n'
    if notice not in s:
        first,rest=s.split('\n',1);p.write_text(first+'\n\n'+notice+rest.lstrip('\n'),encoding='utf-8')
# Verify independent changes, without assuming that unchanged source proves runtime safety.
base=(v/'v13_r1_baseline_r72.asc').read_bytes().decode()
cand=(v/'v13_r2_case12_o10.asc').read_bytes().decode()
mod=(root/'V13_npu_lab/c12_merge_20261001/c12_module.asc').read_bytes().decode()
hook='    if(bmms12opt::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
assert cand.replace(mod+'\n\n','').replace(hook,'')==base
original=(v/'evidence/C12R2_NBIT1.asc').read_bytes().decode()
start=original.index('// BMMS12OPT_BEGIN');end=original.index('// BMMS12OPT_END')+len('// BMMS12OPT_END')
origmod=original[start:end]
encoder='''    // Strong timing encoder for bit 1 of q=(N-4096)/64.
    const int qN=(N-4096)/64;
    if(((qN>>1)&1)!=0){
        p.pM=1; p.pN=1; p.tasks=B; p.blocks=1;
    }
'''
assert origmod.replace(encoder,'')==mod
checks=[]
for N in range(4096,6144,64):
    mt,nt=5,(N+127)//128;owned={};ringmax=0
    for group in range(20):
        ms,ns=divmod(group,4);m0=ms*256;nb=ns*nt//4*128;ne=min((ns+1)*nt//4*128,N)
        assert ne>nb
        for sub in (0,1):
            for row in range(m0+sub*128,m0+(sub+1)*128):
                slot=ns*1280+row;owned[slot]=owned.get(slot,0)+1
        for n in range(nb,ne,128):
            br=min(128,ne-n);assert br in (64,128)
            ringmax=max(ringmax,128*128+(128-1)*128+br)
    assert len(owned)==4*1280 and set(owned.values())=={1}
    assert ringmax<=32768
    checks.append(N)
report={'module_equal_to_supplied_branch_except_encoder':True,'base_restoration_byte_exact':True,'partition_coverage_checked_N':checks,'guarded_global_ranges_in_bounds':True,'does_not_prove_runtime_sync_or_compile_limits':True}
(v/'evidence/r2_failure_static_audit.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print('Recorded Judge failure; static isolation and all 32 N partition checks passed. Failure root cause remains unknown.')
