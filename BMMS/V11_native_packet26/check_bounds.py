"""Exact production cursor versus an independent nested-loop enumeration."""
from pathlib import Path
import importlib.util,json,shutil,subprocess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;BUILD=HERE/'bounds_build'
s=importlib.util.spec_from_file_location('packet_bounds_builder',HERE/'build.py');b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
def main():
    b.verify();BUILD.mkdir(exist_ok=True)
    src=(b.OUT/(b.NAME+'.asc')).read_text(encoding='utf-8')
    native=b.between(src,'namespace bmms83 {','// Only fixed-size TBuf allocations')+'}\n'
    cursor=b.between(src,'class PacketCursor {','class DensePacketConsumer {')
    code='#include <cstdint>\n#include <vector>\n#include <array>\n#include <iostream>\n#include <stdexcept>\n#define __aicore__\n'+native+'using namespace bmms83;\n'+cursor+r'''
void need(bool b,const char* s){if(!b)throw std::runtime_error(s);}
int main(){try{
    uint64_t plans=0,groups=0,tiles=0,packets=0,fullPackets=0,raggedPackets=0,last[4]={};
    for(int M:{48,64,80,128,144,240,256,272,512,528,784,1024,1040,2048,4096,8192})
    for(int N:{48,64,80,128,144,240,256,272,512,528,784,1024,1040,2048,4096,8192})
    for(int cores:{1,2,3,5,20,32,64}){
        auto p=MakeNative(1,M,N,128,cores);++plans;
        for(int group=0;group<p.blocks;++group){
            ++groups;std::vector<std::array<int,2>> expected;
            for(int task=group;task<p.tasks;task+=p.blocks){
                int ms=task/p.pN,ns=task%p.pN;
                int m0=(ms*p.mTiles/p.pM)*64,m1=MinH(((ms+1)*p.mTiles/p.pM)*64,M);
                int n0=(ns*p.nTiles/p.pN)*128,n1=MinH(((ns+1)*p.nTiles/p.pN)*128,N);
                for(int m=m0;m<m1;m+=256)for(int n=n0;n<n1;n+=512)
                for(int a=m;a<MinH(m+256,m1);a+=64)for(int z=n;z<MinH(n+512,n1);z+=128)
                    expected.push_back({MinH(a+64,m1)-a,MinH(z+128,n1)-z});
            }
            PacketCursor it;it.Init(p,group);
            for(auto tile:expected){int mr=0,nr=0;need(it.Next(mr,nr),"cursor ended early");
                need(mr==tile[0]&&nr==tile[1],"cursor differs from independent enumeration");++tiles;}
            int mr=0,nr=0;need(!it.Next(mr,nr),"cursor traversed extra tile");
            for(size_t q=0;q<expected.size();q+=4){
                int count=MinH(4,expected.size()-q);bool full=true;++packets;
                for(int i=0;i<count;++i){auto tile=expected[q+i];full&=tile[0]==64&&tile[1]==128;
                    int vr=tile[0]/2;
                    need(vr%8==0&&tile[1]%16==0,"row alignment");
                    for(int sub=0;sub<2;++sub){
                        int first=i*64*128+sub*vr*128;
                        int end=first+(vr-1)*128+tile[1];
                        need(first>=i*64*128&&end<=i*64*128+tile[0]*128,"GM reads leave published tile");
                        need(i*4096+(vr-1)*128+tile[1]<=16384,"UB packet overflow");
                    }
                }
                full?++fullPackets:++raggedPackets;
                if(q+count==expected.size())++last[count-1];
            }
        }
    }
    for(auto n:last)need(n>0,"missing final packet length");
    std::cout<<"{\"plans\":"<<plans<<",\"groups\":"<<groups<<",\"tiles\":"<<tiles<<",\"packets\":"<<packets
        <<",\"full_packets\":"<<fullPackets<<",\"ragged_packets\":"<<raggedPackets<<",\"final_packet_lengths\":[";
    for(int i=0;i<4;++i){if(i)std::cout<<",";std::cout<<last[i];}std::cout<<"]}\n";
}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
'''
    cpp=BUILD/'cursor.cpp';exe=BUILD/'cursor.exe';b.write(cpp,code)
    subprocess.run([shutil.which('g++'),'-std=c++20','-O2',str(cpp),'-o',str(exe)],check=True)
    p=subprocess.run([str(exe)],capture_output=True,text=True,timeout=120)
    if p.returncode:raise RuntimeError(p.stderr)
    result=json.loads(p.stdout);peak=0;cases=0
    for M in range(48,8193,16):
        for pn in range(1,65):
            cap=min(M,(16384//pn//16)*16);assert cap>=16 and cap%16==0 and cap*pn<=16384
            work=max(4*32*128,2*M+cap*pn)
            ub=(work+32*128+32+256)*4+32
            assert ub<=192*1024;peak=max(peak,ub);cases+=1
            assert M+cap*pn+M<=work
            for m0 in range(0,M,cap):
                rows=min(cap,M-m0);assert rows%16==0 and (pn-1)*M+m0+rows<=M*pn
    result.update(capacity_cases=cases,UB_max_explicit_bytes=peak,shared_UB_lifetimes_separated_by_barrier_and_V_MTE2=True,
        actual_cursor_sha256=b.sha(HERE/'packet_helpers.asc'),checker_sha256=b.sha(Path(__file__)),
        source_sha256=b.sha(b.OUT/(b.NAME+'.asc')),scope='production cursor, bounds and explicit resource arithmetic; no device compilation or timing')
    for f in [HERE/'BOUNDS_CHECKS.json',b.OUT/'BOUNDS_CHECKS.json']:b.write(f,json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
