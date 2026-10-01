from pathlib import Path
import hashlib,json
r=Path(__file__).resolve().parents[1];o=r/'BMMS_V12';h=r/'V12_npu_lab/harness'
base=(o/'v12_baseline_r19.asc').read_bytes()
s=(o/'v12_r26_dense_macro_consumer.asc').read_bytes().decode()
a=s.index('// BMMS1226_BEGIN');b=s.index('// BMMS1226_END',a)+len('// BMMS1226_END')
mod=s[a:b].replace('1226','1228')
mod=mod.replace('TM=64,TN=128,AM=128,BN=256,K1=256,K0=64,MACRO_ELEMS=4*TM*TN',
                'TM=64,TN=128,AM=128,BN=128,K1=512,K0=128,MACRO_ELEMS=AM*BN')
# Re-evaluate exactly the existing planner for the new tile geometry.
bs=base.decode();start=bs.index('// Closed-form peak work',bs.index('namespace bmms11r2 {'))
end=bs.index('\ntemplate<class T,bool TA,bool TB>',start)
planner=bs[start:end]
old='static inline Plan MakePlan(int B,int M,int N,int K,int cores){return bmms11r2::MakePlan(B,M,N,K,cores);}'
assert old in mod
mod=mod.replace(old,planner)
mod=mod.replace('bmms11r2::WorkspaceBytes(p)','WorkspaceBytes(p)').replace('bmms11r2::RingBytes(p)','RingBytes(p)')
mod=mod.replace('pipe->InitBuffer(cBuf,4*TM*TN*sizeof(float));','pipe->InitBuffer(cBuf,MACRO_ELEMS*sizeof(float));')
old='''                    AscendC::BinaryRepeatParams rp{1,1,1,32,32,32};
                    AscendC::Max(c,c,c[128],64,vr,rp);AscendC::PipeBarrier<PIPE_V>();
                    AscendC::Max(c[64],c[64],c[192],64,vr,rp);AscendC::PipeBarrier<PIPE_V>();
                    AscendC::Max(c,c,c[64],64,vr,rp);AscendC::PipeBarrier<PIPE_V>();
                    AscendC::WholeReduceMax(rows,c,64,vr,1,1,32,AscendC::ReduceOrder::ORDER_ONLY_VALUE);'''
new='''                    AscendC::BinaryRepeatParams rp{1,1,1,16,16,16};
                    AscendC::Max(c,c,c[64],64,vr,rp);AscendC::PipeBarrier<PIPE_V>();
                    AscendC::WholeReduceMax(rows,c,64,vr,1,1,16,AscendC::ReduceOrder::ORDER_ONLY_VALUE);'''
assert old in mod;mod=mod.replace(old,new)
mod=mod.replace('// One full AM x K0 A operand and K0 x BN B operand in L0.',
'''// 128x128x128 MMAD, double buffered L0A/B (64 KiB each).
        // K1=512 uses exactly 512 KiB L1; no other L1 buffers are allocated.''')
mod=('\n'+mod+'\n\n').encode();idx=base.index(b'extern "C" void run_kernel')
data=base[:idx]+mod+base[idx:]
hook=b'    if(bmms1228::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
idx=data.index(b'    if(bmms11r2::TryLaunch(a,b,y,');data=data[:idx]+hook+data[idx:]
assert data.replace(mod,b'',1).replace(hook,b'',1)==base
name='v12_r28_dense_square_k128.asc';(o/name).write_bytes(data);(h/'r28.asc').write_bytes(data)
meta=dict(version='v12_r28',file=name,sha256=hashlib.sha256(data).hexdigest(),parent='v12_baseline_r19.asc',status='experimental; validation pending',
    change='128x128 output, K0=128 K1=512, existing grid planner recomputed with 128-column tiles; same aligned-pitch gate',
    L1_bytes=524288,L0A_bytes=65536,L0B_bytes=65536,L0C_bytes=65536,parent_byte_recovery=True)
(o/'v12_r28_manifest.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
e=(h/'event_bench_r26.asc').read_text(encoding='utf-8').replace('1226','1228')
e=e.replace(' auto p=plan;auto ring=(uint8_t*)ws;auto part=ring+bmms11r2::RingBytes(p);',
''' auto p=candidate?bmms1228::MakePlan(plan.B,plan.M,plan.N,plan.K,20):plan;
 auto ring=(uint8_t*)ws;auto part=ring+(candidate?bmms1228::RingBytes(p):bmms11r2::RingBytes(p));''')
# Measured device core count, no hardcoded launch dimensions.
e=e.replace('static bool eligible(', 'static int measuredCores=0;\nstatic bool eligible(')
e=e.replace('plan.K,20)', 'plan.K,measuredCores)')
e=e.replace('    int id,dt,ta,tb;', '    measuredCores=int(cores);\n    int id,dt,ta,tb;')
e=e.replace('bmms11r2::WorkspaceBytes(p),ACL_MEM',
    'bmms11r2::WorkspaceBytes(p)+bmms1228::WorkspaceBytes(bmms1228::MakePlan(B,M,N,K,cores)),ACL_MEM')
(h/'event_bench_r28.asc').write_text(e,encoding='utf-8',newline='\n')
cm=h/'CMakeLists.txt';t=cm.read_text(encoding='utf-8')
if 'add_executable(bench_r28 ' not in t:t+='\n'+t[t.index('add_executable(bench_r27 '):].replace('r27','r28')
cm.write_text(t,encoding='utf-8',newline='\n')
(h/'screen_r28.sh').write_text((h/'screen_r26.sh').read_text(encoding='utf-8').replace('r26','r28').replace('R26','R28'),encoding='utf-8',newline='\n')
print(json.dumps(meta))
