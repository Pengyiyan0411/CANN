from pathlib import Path
import importlib.util,hashlib,json
H=Path(__file__).resolve().parent;ROOT=H.parent;OUT=ROOT/'BMMS_V12'
spec=importlib.util.spec_from_file_location('previous',ROOT/'V12_impl_r02_r03/build.py');previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
write,once,between,function,host=previous.write,previous.once,previous.between,previous.function,previous.host
BASE=OUT/'v12_r03_case2_static_k.asc';SHA='1c9e9726aa43fdd177c98c645c69bb7d57721d2f1b07d00dfb614324286a404c'
NAME='v12_r04_case9_10_partial_a_cache'

def module(src):
    start=src.index('template<class T,bool TA,bool TB>\nclass ReuseProducer')
    end=src.index('class RowMaxConsumer',start);dev=src[start:end].rstrip().replace('ReuseProducer','CachedAProducer')
    dev=once(dev,'int kr,int s){','int kr,int s,bool firstN){')
    dev=once(dev,'auto aa=a1Buf.template Get<T>()[s*AM*K1];','auto aa=a1Buf.template Get<T>()[(s+(k0<CACHE_K?2:0))*AM*K1];')
    dev=once(dev,'AscendC::DataCopy(aa,a[ai],qa);','if(firstN||k0>=CACHE_K)AscendC::DataCopy(aa,a[ai],qa);')
    dev=once(dev,'int kr0,int s1,int s0){','int kr0,int s1,int s0,int kBase){')
    dev=once(dev,'auto sa=a1Buf.template Get<T>()[s1*AM*K1];','auto sa=a1Buf.template Get<T>()[(s1+(kBase<CACHE_K?2:0))*AM*K1];')
    dev=once(dev,'int ar,int br){\n        const int kCount','int ar,int br,bool firstN){\n        const int kCount')
    dev=once(dev,'MinI(K1,p.K),0);','MinI(K1,p.K),0,firstN);')
    dev=once(dev,'MinI(K1,p.K-nextK),next);','MinI(K1,p.K-nextK),next,firstN);')
    dev=once(dev,'LoadL0(ar,br,kr1,kk,kr0,s1,s0);','LoadL0(ar,br,kr1,kk,kr0,s1,s0,kBase);')
    dev=once(dev,'pipe->InitBuffer(a1Buf,2*AM*K1*sizeof(T));','pipe->InitBuffer(a1Buf,4*AM*K1*sizeof(T));')
    dev=once(dev,'MinI(AM,mEnd-m0),MinI(BN,nEnd-n0));','MinI(AM,mEnd-m0),MinI(BN,nEnd-n0),n0==nBegin);')
    dev=dev.replace('// Free L1 only after the last K0 slice has read BOTH shared operands.','// Streaming slots keep original ownership. Cached A slots survive until the next M macro; Macro drains all readers.')
    mod=previous.module2(src)
    a=mod.index('template<class T,bool TA,bool TB>\nclass ResidentAProducer');z=mod.index('} // namespace bmms1202',a)
    mod=mod[:a]+dev+'\n'+mod[z:]
    mod=mod.replace('ResidentAProducer','CachedAProducer').replace('K1=128,K0=64','K1=256,K0=64,CACHE_K=512').replace('1202','1204')
    return mod

def main():
    raw=BASE.read_bytes();assert hashlib.sha256(raw).hexdigest()==SHA;src=raw.decode().replace('\r\n','\n');mod=module(src).encode()
    anchor=b'extern "C" void run_kernel(GM_ADDR a,const TensorGroupInfo& ia,'
    hook=b'    if(bmms1204::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\r\n'
    marker=b'    if(bmms11r2::TryLaunch';i=raw.index(marker);e=raw.index(b'\n',i)+1;line=raw[i:e]
    data=raw.replace(anchor,mod+anchor,1).replace(line,hook+line,1)
    assert data.replace(mod,b'',1).replace(hook,b'',1)==raw
    assert b'BMMS1202_BEGIN' not in data
    (OUT/(NAME+'.asc')).write_bytes(data)
    write(H/'extracted.hpp',between(mod.decode(),'// BMMS1204_BEGIN','// BMMS1204_CPU_END'))
    write(OUT/'v12_r04_manifest.json',json.dumps({'candidate':NAME+'.asc','sha256':hashlib.sha256(data).hexdigest(),'parent':BASE.name,'parent_sha256':SHA,'parent_recovered_byte_for_byte':True,'r02_not_inherited':True},indent=2)+'\n')
    print('Built '+NAME)
if __name__=='__main__':main()
