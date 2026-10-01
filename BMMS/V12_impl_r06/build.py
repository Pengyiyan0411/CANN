from pathlib import Path
import importlib.util,hashlib,json
H=Path(__file__).resolve().parent;ROOT=H.parent;OUT=ROOT/'BMMS_V12'
spec=importlib.util.spec_from_file_location('previous',ROOT/'V12_impl_r02_r03/build.py');previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
write,once,between,function,host=previous.write,previous.once,previous.between,previous.function,previous.host
BASE=OUT/'v12_baseline_r03.asc';SHA='1c9e9726aa43fdd177c98c645c69bb7d57721d2f1b07d00dfb614324286a404c';NAME='v12_r06_case9_macro_mmad'

def module(src):
    a=src.index('template<class T,bool TA,bool TB>\nclass ReuseProducer');z=src.index('class RowMaxConsumer',a)
    dev=src[a:z].rstrip().replace('ReuseProducer','MacroMmadProducer')
    a=dev.index('        for(int mo=0;mo<ar;mo+=TM){');z=dev.index('        AscendC::SetFlag<AscendC::HardEvent::MTE1_M>',a)
    dev=dev[:a]+'''        // One full AM x K0 A operand and K0 x BN B operand in L0.
        for(int i=0;i<ar/16;++i){
            const int off=TA?i*kr1*16+kk*16:(kk/16)*ar*16+i*256;
            AscendC::LoadData(da[i*kr0*16],sa[off],la);
        }
        AscendC::LoadData2DParams lb{};lb.repeatTimes=br/16;
        lb.srcStride=TB?1:kr1/16;lb.ifTranspose=!TB;
        for(int j=0;j<kr0/16;++j){
            const int off=TB?(kk/16+j)*br*16:(kk+j*16)*16;
            AscendC::LoadData(db[j*br*16],sb[off],lb);
        }
'''+dev[z:]
    a=dev.index('                for(int mo=0;mo<ar;mo+=TM){');z=dev.index('                // Reused A/B',a)
    dev=dev[:a]+'''                // Accumulate the whole macro into one NZ matrix. K order is unchanged.
                AscendC::MmadParams q{};q.m=ar;q.n=br;q.k=kr0;q.cmatrixInitVal=(l0Count==0);
                AscendC::Mmad(cBuf.template Get<float>(),aa,bb,q);
                if((ar/16)*(br/16)<10)AscendC::PipeBarrier<PIPE_M>();
'''+dev[z:]
    dev=dev.replace('// Reused A/B stay owned by M until all four output MMADs complete.','// Both full operands stay owned by M until the macro MMAD completes.')
    dev=once(dev,'f.nSize=nr;f.mSize=mr;f.srcStride=mr;','f.nSize=nr;f.mSize=mr;f.srcStride=ar;')
    dev=once(dev,'cBuf.template Get<float>()[ci*TM*TN],f);','cBuf.template Get<float>()[(no/16)*ar*16+mo*16],f);')
    mod=previous.module2(src)
    a=mod.index('template<class T,bool TA,bool TB>\nclass ResidentAProducer');z=mod.index('} // namespace bmms1202',a)
    mod=mod[:a]+dev+'\n'+mod[z:]
    return mod.replace('ResidentAProducer','MacroMmadProducer').replace('K1=128,K0=64','K1=256,K0=64').replace('1202','1206')

def main():
    raw=BASE.read_bytes();assert hashlib.sha256(raw).hexdigest()==SHA
    mod=module(raw.decode().replace('\r\n','\n')).encode();anchor=b'extern "C" void run_kernel(GM_ADDR a,const TensorGroupInfo& ia,'
    hook=b'    if(bmms1206::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\r\n'
    marker=b'    if(bmms11r2::TryLaunch';i=raw.index(marker);end=raw.index(b'\n',i)+1;line=raw[i:end]
    data=raw.replace(anchor,mod+anchor,1).replace(line,hook+line,1)
    assert data.replace(mod,b'',1).replace(hook,b'',1)==raw
    (OUT/(NAME+'.asc')).write_bytes(data)
    write(H/'extracted.hpp',between(mod.decode(),'// BMMS1206_BEGIN','// BMMS1206_CPU_END'))
    write(OUT/'v12_r06_manifest.json',json.dumps({'candidate':NAME+'.asc','sha256':hashlib.sha256(data).hexdigest(),'parent':BASE.name,'parent_sha256':SHA,'parent_recovered_byte_for_byte':True,'guard_identical_to_r04':True,'r02_r04_cache_not_inherited':True,'MMAD_tile':[128,256,64],'K1':256,'consumer_and_grid_unchanged':True},indent=2)+'\n')
    print('Built '+NAME)
if __name__=='__main__':main()
