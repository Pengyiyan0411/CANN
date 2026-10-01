from pathlib import Path
import hashlib,json
r=Path(__file__).resolve().parents[1];o=r/'BMMS_V12';h=r/'V12_npu_lab/harness'
raw=(o/'v12_r28_dense_square_k128.asc').read_bytes().decode();a=raw.index('// BMMS1228_BEGIN');b=raw.index('// BMMS1228_END',a)+len('// BMMS1228_END')
mod=raw[a:b].replace('1228','1229').replace('AM=128,BN=128,K1=512,K0=128','AM=256,BN=128,K1=256,K0=64')
a=mod.index('        AscendC::LoadData2DParams la{};',mod.index('__aicore__ inline void LoadL0'))
b=mod.index('        AscendC::SetFlag<AscendC::HardEvent::MTE1_M>',a)
mod=mod[:a]+'''        // Reorder fractal transfers with dstGap instead of one instruction per M tile.
        // srcStride/dstGap are in 512-byte (16x16 b16) fractals.
        AscendC::LoadData2DParams la{};la.repeatTimes=ar/16;
        la.srcStride=TA?kr1/16:1;la.dstGap=kr0/16-1;la.ifTranspose=TA;
        for(int j=0;j<kr0/16;++j){
            const int off=TA?(kk/16+j)*256:(kk/16+j)*ar*16;
            AscendC::LoadData(da[j*256],sa[off],la);
        }
        AscendC::LoadData2DParams lb{};
        if constexpr(TB){
            // B's selected K slices are contiguous in both L1 and L0B.
            lb.repeatTimes=(kr0/16)*(br/16);lb.srcStride=1;lb.ifTranspose=false;
            AscendC::LoadData(db,sb[(kk/16)*br*16],lb);
        }else{
            lb.repeatTimes=br/16;lb.srcStride=kr1/16;lb.ifTranspose=true;
            for(int j=0;j<kr0/16;++j)
                AscendC::LoadData(db[j*br*16],sb[(kk+j*16)*16],lb);
        }
'''+mod[b:]
base=(o/'v12_baseline_r19.asc').read_bytes();module=('\n'+mod+'\n\n').encode();idx=base.index(b'extern "C" void run_kernel')
data=base[:idx]+module+base[idx:]
hook=b'    if(bmms1229::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
idx=data.index(b'    if(bmms11r2::TryLaunch(a,b,y,');data=data[:idx]+hook+data[idx:]
assert data.replace(module,b'',1).replace(hook,b'',1)==base
name='v12_r29_dense_m256_load2d.asc';(o/name).write_bytes(data);(h/'r29.asc').write_bytes(data)
meta=dict(version='v12_r29',file=name,sha256=hashlib.sha256(data).hexdigest(),parent='v12_baseline_r19.asc',status='experimental; validation pending',
 change='256x128 output K0=64 K1=256; grid retiled; A uses dstGap and TB contiguous B transfer',
 L1_bytes=393216,L0A_bytes=65536,L0B_bytes=32768,L0C_bytes=131072,parent_byte_recovery=True)
(o/'v12_r29_manifest.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
(h/'event_bench_r29.asc').write_text((h/'event_bench_r28.asc').read_text(encoding='utf-8').replace('1228','1229'),encoding='utf-8',newline='\n')
cm=h/'CMakeLists.txt';t=cm.read_text(encoding='utf-8')
if 'add_executable(bench_r29 ' not in t:t+='\n'+t[t.index('add_executable(bench_r28 '):].replace('r28','r29')
cm.write_text(t,encoding='utf-8',newline='\n')
(h/'screen_r29.sh').write_text((h/'screen_r28.sh').read_text(encoding='utf-8').replace('r28','r29').replace('R28','R29'),encoding='utf-8',newline='\n')
print(json.dumps(meta))
