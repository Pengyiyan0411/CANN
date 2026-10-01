from pathlib import Path
import hashlib, json

root = Path(__file__).resolve().parents[1]
out = root / 'BMMS_V12'
h = root / 'V12_npu_lab/harness'
base = (out / 'v12_baseline_r33.asc').read_bytes()
raw = base.decode()
a = raw.index('// BMMS1230_BEGIN')
b = raw.index('// BMMS1230_END', a) + len('// BMMS1230_END')
mod = raw[a:b].replace('1230', '1234')
mod = mod.replace('K1=256,K0=64', 'K1=128,K0=64')
mod = mod.replace('M<2048&&N>=2048&&N<=8192&&K>=1536&&K<4096',
                  'M<=8192&&N>=1024&&N<=8192&&K>=1024&&K<1536')
mod = mod.replace('||!AlignedPitch(M,N,K,ta,tb)', '')
start = mod.index('    __aicore__ inline void LoadStage(')
end = mod.index('        AscendC::Nd2NzParams qb{};', start)
mod = mod[:start] + '''    // One full-K A panel is resident for all N macros in this M row.
    // At the previous row's end Macro drains all MTE1 readers before reuse.
    __aicore__ inline void LoadA(int batch,int m0,int ar){
        AscendC::Nd2NzParams qa{};qa.ndNum=1;
        qa.nValue=TA?p.K:ar;qa.dValue=TA?ar:p.K;
        qa.srcDValue=TA?p.M:p.K;qa.dstNzC0Stride=TA?p.K:ar;qa.dstNzNStride=1;
        const int64_t ai=int64_t(batch)*p.M*p.K+(TA?m0:int64_t(m0)*p.K);
        AscendC::DataCopy(a1Buf.template Get<T>(),a[ai],qa);
        // The first B stage's MTE2_MTE1 event also orders this preceding copy.
    }
    __aicore__ inline void LoadStage(int batch,int m0,int n0,int ar,int br,int k0,int kr,int s){
        auto bb=b1Buf.template Get<T>()[s*K1*BN];
''' + mod[end:]
mod = mod.replace('int kr1,int kk,int kr0,int s1,int s0)',
                  'int kr1,int kk,int ak,int kr0,int s1,int s0)')
mod = mod.replace('auto sa=a1Buf.template Get<T>()[s1*AM*K1];',
                  'auto sa=a1Buf.template Get<T>();')
mod = mod.replace('TA?i*kr1*16+kk*16:(kk/16)*ar*16+i*256',
                  'TA?i*p.K*16+ak*16:(ak/16)*ar*16+i*256')
mod = mod.replace('LoadL0(ar,br,kr1,kk,kr0,s1,s0);',
                  'LoadL0(ar,br,kr1,kk,kBase+kk,kr0,s1,s0);')
mod = mod.replace('pipe->InitBuffer(a1Buf,2*AM*K1*sizeof(T));',
                  'pipe->InitBuffer(a1Buf,AM*p.K*sizeof(T));')
old = '''                const int nextM=n0+BN<nEnd?m0:m0+AM;
                const int nextN=n0+BN<nEnd?n0+BN:nBegin;
                const bool hasNext=nextM<mEnd;'''
new = '''                if(n0==nBegin)LoadA(batch,m0,MinI(AM,mEnd-m0));
                const int nextM=m0,nextN=n0+BN;
                // End each M row with a drained B/L0 pipeline, before replacing A.
                const bool hasNext=nextN<nEnd;'''
assert old in mod
mod = mod.replace(old, new)
payload = ('\n' + mod + '\n\n').encode()
ix = base.index(b'extern "C" void run_kernel')
data = base[:ix] + payload + base[ix:]
hook = b'    if(bmms1234::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
ix = data.index(b'    if(bmms1233::TryLaunch')
data = data[:ix] + hook + data[ix:]
assert data.replace(payload,b'',1).replace(hook,b'',1) == base
name = 'v12_r34_shortk_a_resident.asc'
(out/name).write_bytes(data)
(h/'r34.asc').write_bytes(data)
event = (h/'event_bench_r33.asc').read_text(encoding='utf-8')
event = event.replace('bmms1233', 'bmms1234').replace('DISPATCH(bmms11r2)', 'DISPATCH(bmms1233)')
event = event.replace('candidate?"r33":"r30"','candidate?"r34":"r33"')
(h/'event_bench_r34.asc').write_text(event,encoding='utf-8',newline='\n')
cm = h/'CMakeLists.txt'
s = cm.read_text(encoding='utf-8')
if 'add_executable(bench_r34 ' not in s:
    s += '\n' + s[s.index('add_executable(bench_r33 '):].replace('r33','r34')
cm.write_text(s,encoding='utf-8',newline='\n')
meta=dict(version='v12_r34',status='experimental; not submitted',parent='v12_baseline_r33.asc',
          file=name,sha256=hashlib.sha256(data).hexdigest(),parent_byte_recovery=True,
          change='Full-K A panel resident across N macros, B K1=128 double buffer, original grid and reduction',
          max_L1_bytes=128*1504*2+2*128*256*2,L0A_bytes=32768,L0B_bytes=65536,L0C_bytes=131072)
(out/'v12_r34_manifest.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
print(json.dumps(meta))
