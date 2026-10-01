from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parents[1];H=R/'V12_npu_lab/harness'
raw=(R/'BMMS_V12/v12_baseline_r12.asc').read_bytes();sha=hashlib.sha256(raw).hexdigest()
assert sha=='a845fd9538fe71d5f6284fced34781d8fb7e997105c51065a84b344818ddbd2b'
s=raw.decode().replace('\r\n','\n');a=s.index('namespace bmms_c8p43 {');b=s.index('// BMMS_C8P43_END',a)+len('// BMMS_C8P43_END')
mod=s[a:b].replace('bmms_c8p43','bmms1214').replace('BMMS_C8P43','BMMS1214')
mod=mod.replace('constexpr int32_t AM=bmms11r2::AM,BN=bmms11r2::BN;','constexpr int32_t AM=128,BN=128;')
mod=mod.replace('    p.cube=bmms11r2::MakePlan(1,mp,np,kp,cores);','''    p.cube=bmms11r2::MakePlan(1,mp,np,kp,cores);
    auto& c=p.cube;c.mTiles=(mp+AM-1)/AM;c.nTiles=(np+BN-1)/BN;
    c.pM=c.mTiles;c.pN=c.nTiles;c.tasks=c.pM*c.pN;
    c.blocks=bmms83::MinH(cores,c.tasks);''')
# Use the already validated whole-macro NZ L0 arrangement, but a different
# tile size that preserves double-buffering at K0=128 (unlike old R31).
old=(R/'BMMS_V12/v12_r06_case9_macro_mmad.asc').read_text();a=old.index('template<class T,bool TA,bool TB>\nclass MacroMmadProducer');b=old.index('} // namespace bmms1206',a)
prod=old[a:b].replace('MacroMmadProducer','SquareProducer')
prod='using Plan=CubePlan;\nconstexpr int K1=512,K0=128;\n'+prod
mod=mod.replace('class MaskedRowMaxConsumer {',prod+'\nclass MaskedRowMaxConsumer {',1).replace('bmms11r2::ReuseProducer<T,TA,TB>','SquareProducer<T,TA,TB>')
mod=mod.replace('// Reuse the frozen R25 producer itself, not a modified copy.','// 128x128 macro, double L1 K512 and double L0 K128.')
frag=('// BMMS1214_BEGIN\n'+mod+'\n\n').encode();anchor=b'extern "C" void run_kernel(GM_ADDR a,const TensorGroupInfo& ia,'
idx=raw.index(b'    if(bmms_c8p43::TryLaunch');end=raw.index(b'\n',idx)+1;line=raw[idx:end];hook=line.replace(b'bmms_c8p43::',b'bmms1214::')
data=raw.replace(anchor,frag+anchor,1).replace(line,hook+line,1)
assert data.replace(frag,b'',1).replace(hook,b'',1)==raw
name='v12_r14_case8_square_pipeline.asc';(R/'BMMS_V12'/name).write_bytes(data);(H/'r14.asc').write_bytes(data)
j=dict(candidate=name,parent='v12_baseline_r12.asc',parent_sha256=sha,sha256=hashlib.sha256(data).hexdigest(),parent_recovered_byte_for_byte=True,status='experimental, pending device validation',macro=[128,128],K1=512,K0=128,L1_bytes=524288,L0A_bytes=65536,L0B_bytes=65536,L0C_bytes=131072)
(R/'BMMS_V12/v12_r14_manifest.json').write_text(json.dumps(j,indent=2)+'\n')
e=(H/'event_bench_r13.asc').read_text().replace('1213','1214').replace('"r13"','"r14"')
a=e.index('    if(candidate){');b=e.index('\n#undef DISPATCH',a)
e=e[:a]+'''    if(candidate){
        auto p=bmms1214::MakePlan(plan.realM,plan.realN,plan.realK,20,ta,tb);
        // Same padded A/B and ring allocation; candidate has a larger partial region.
        DISPATCH(bmms1214);
    }else{DISPATCH(bmms_c8p43);}
'''+e[b:]
# Query the actual device core count rather than baking the test machine into a plan.
e=e.replace('    auto p=plan;auto ap=', '    static int64_t cores=0;if(!cores)ck(aclrtGetDeviceInfo(0,ACL_DEV_ATTR_CUBE_CORE_NUM,&cores),"cores");\n    auto p=plan;auto ap=').replace('plan.realK,20,ta,tb','plan.realK,cores,ta,tb')
# Different ring size if baseline runs fewer blocks. Offset calculation must
# occur after selecting the plan. Current pointer globals shadowed in branch.
e=e.replace('        // Same padded A/B and ring allocation; candidate has a larger partial region.','''        auto ap=(uint8_t*)ws;auto bp=ap+bmms1214::ABytes(p);auto ring=bp+bmms1214::BBytes(p);auto part=ring+bmms1214::RingBytes(p);''')
e=e.replace('aclrtMalloc(&ws,bmms_c8p43::WorkspaceBytes(p),', 'aclrtMalloc(&ws,bmms_c8p43::WorkspaceBytes(p)+bmms1214::WorkspaceBytes(bmms1214::MakePlan(M,N,K,cores,ta,tb)),')
(H/'event_bench_r14.asc').write_text(e,newline='\n')
c=H/'CMakeLists.txt';st=c.read_text()
if 'add_executable(event_bench_r14' not in st:
 a=st.index('add_executable(event_bench_r13');st+=st[a:].replace('r13','r14');c.write_text(st,newline='\n')
print(json.dumps(j,indent=2))
