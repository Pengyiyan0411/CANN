"""Case12 B-only NZ pack, preserving original r30 geometry and prefetch."""
from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1];v=root/'BMMS_V12';lab=root/'V12_npu_lab/case12_k1_20261001'
out=root/'V12_npu_lab/results/case12_bnz_20261001';out.mkdir(exist_ok=True)
base=(v/'v12_baseline_r41.asc').read_bytes().decode()
old=(v/'v12_r51_case12_kstage320.asc').read_bytes().decode()
a=old.index('// BMMS1251_BEGIN');b=old.index('// BMMS1251_END',a)+len('// BMMS1251_END\n\n')
mod=old[a:b].replace('1251','1256').replace('K1=320','K1=256')
mod=mod.replace('// Independent r41 experiment: K1=256; K0 order, grid and row-max consumer unchanged.',
    '// B-only NZ prepack experiment: original r30 grid, A path, K order and consumer.')
pack=r'''
constexpr uint16_t PACK_ALL=0,PACK_TO_CUBE=2;
constexpr int PACK_SLOT=128*128;
static inline uint64_t BBytes(const Plan& p){return uint64_t(p.K)*p.N*2;}
static inline uint64_t WorkspaceBytes(const Plan& p){return bmms11r2::WorkspaceBytes(p)+BBytes(p);}
static inline uint64_t AppUbBytes(const Plan& p){
    return 2ULL*PACK_SLOT*2+(AM/2)*BN*4ULL+32+2*(AM/2)*4ULL+3ULL*p.M*4;
}
// Raw 16-bit transport. No arithmetic reinterpretation of BF16 as half.
__aicore__ inline void PackB(GM_ADDR src,GM_ADDR dst,const Plan& p,
    AscendC::TPipe* pipe,AscendC::TBuf<AscendC::TPosition::VECCALC>& buf){
    AscendC::GlobalTensor<half> input,packed;
    input.SetGlobalBuffer(reinterpret_cast<__gm__ half*>(src),int64_t(p.K)*p.N);
    packed.SetGlobalBuffer(reinterpret_cast<__gm__ half*>(dst),int64_t(p.K)*p.N);
    auto x=buf.Get<half>(),z=buf.Get<half>()[PACK_SLOT];
    const int worker=AscendC::GetBlockIdx(),workers=2*p.blocks,colTiles=(p.N+127)/128;
    const int jobs=(p.K/128)*colTiles;
    auto freeId=pipe->AllocEventID<AscendC::HardEvent::MTE3_V>();
    bool issued=false;
    for(int job=worker;job<jobs;job+=workers){
        const int row0=(job/colTiles)*128,col0=(job%colTiles)*128;
        const int rows=128,cols=MinI(128,p.N-col0);
        if(issued)AscendC::WaitFlag<AscendC::HardEvent::MTE3_V>(freeId);
        // Previous V reads of x have completed before its next MTE2 overwrite.
        bmms71::Fence<AscendC::HardEvent::V_MTE2>(*pipe);
        AscendC::DataCopyExtParams cp{uint16_t(rows),uint32_t(cols*2),uint32_t((p.N-cols)*2),0,0};
        AscendC::DataCopyPadExtParams<half> pd{false,0,0,half(0.0f)};
        AscendC::DataCopyPad(x,input[int64_t(row0)*p.N+col0],cp,pd);
        bmms71::Fence<AscendC::HardEvent::MTE2_V>(*pipe);
        AscendC::DataCopyParams local{uint16_t(rows),1,uint16_t(cols/16-1),0};
        for(int c=0;c<cols;c+=16)AscendC::DataCopy(z[c*rows],x[c],local);
        bmms71::Fence<AscendC::HardEvent::V_MTE3>(*pipe);
        AscendC::DataCopyExtParams cpout{uint16_t(cols/16),uint32_t(rows*32),0,uint32_t((p.K-rows)*32),0};
        const int64_t off=int64_t(col0/16)*p.K*16+row0*16;
        AscendC::DataCopyPad(packed[off],z,cpout);
        AscendC::SetFlag<AscendC::HardEvent::MTE3_V>(freeId);issued=true;
    }
    if(issued)AscendC::WaitFlag<AscendC::HardEvent::MTE3_V>(freeId);
    pipe->ReleaseEventID<AscendC::HardEvent::MTE3_V>(freeId);
    // All AIVs participate, including workers with no jobs.
    AscendC::CrossCoreSetFlag<0x0,PIPE_MTE3>(PACK_ALL);
    AscendC::CrossCoreWaitFlag<0x0>(PACK_ALL);
    AscendC::CrossCoreSetFlag<0x2,PIPE_MTE3>(PACK_TO_CUBE);
}
'''
needle='template<class T,bool TA,bool TB>\nclass MacroMmadProducer'
assert mod.count(needle)==1;mod=mod.replace(needle,pack+'\n'+needle)
a=mod.index('        AscendC::Nd2NzParams qb{};')
b=mod.index('        AscendC::SetFlag<AscendC::HardEvent::MTE2_MTE1>',a)
mod=mod[:a]+'''        static_assert(!TB,"B prepack only supports physical KxN input");
        const int64_t bi=int64_t(n0/16)*p.K*16+k0*16;
        // Packed GM [N/16,K,16] -> contiguous L1 [br/16,kr,16].
        AscendC::DataCopyParams qb{uint16_t(br/16),uint16_t(kr),uint16_t(p.K-kr),0};
        AscendC::DataCopy(bb,b[bi],qb);
'''+mod[b:]
mod=mod.replace('GM_ADDR y,GM_ADDR ring,GM_ADDR part,Plan p){','GM_ADDR y,GM_ADDR bp,GM_ADDR ring,GM_ADDR part,Plan p){',1)
before='''    if ASCEND_IS_AIC {MacroMmadProducer<T,TA,TB> op;op.Init(a,b,ring,p,&pipe);op.Process();}
    if ASCEND_IS_AIV {bmms1230::RowMaxConsumer op;op.Init(ring,part,y,p,&pipe);op.Process();}'''
after='''    if ASCEND_IS_AIC {
        MacroMmadProducer<T,TA,TB> op;op.Init(a,bp,ring,p,&pipe);
        AscendC::CrossCoreWaitFlag<0x2>(PACK_TO_CUBE);op.Process();
    }
    if ASCEND_IS_AIV {
        AscendC::TBuf<AscendC::TPosition::VECCALC> packBuf;
        pipe.InitBuffer(packBuf,2*PACK_SLOT*2);
        PackB(b,bp,p,&pipe,packBuf);
        bmms1230::RowMaxConsumer op;op.Init(ring,part,y,p,&pipe);op.Process();
    }'''
assert before in mod;mod=mod.replace(before,after)
mod=mod.replace('GM_ADDR y,GM_ADDR ring,GM_ADDR part,bmms1256::Plan p)', 'GM_ADDR y,GM_ADDR bp,GM_ADDR ring,GM_ADDR part,bmms1256::Plan p)')
mod=mod.replace('Entry<T,TA,false>(a,b,y,ring,part,p);','Entry<T,TA,false>(a,b,y,bp,ring,part,p);')
mod=mod.replace('const auto p=MakePlan(B,M,N,K,cores);uint8_t* ws=nullptr;',
'''const auto p=MakePlan(B,M,N,K,cores);uint8_t* ws=nullptr;
    if(AppUbBytes(p)>190ULL*1024 || WorkspaceBytes(p)>128ULL*1024*1024)return false;''')
mod=mod.replace('(&ws),bmms11r2::WorkspaceBytes(p),','(&ws),WorkspaceBytes(p),')
mod=mod.replace('    uint8_t* partial=ws+bmms11r2::RingBytes(p);',
'''    uint8_t* partial=ws+bmms11r2::RingBytes(p);
    uint8_t* bp=ws+bmms11r2::WorkspaceBytes(p);''')
mod=mod.replace('(a,b,y,ws,partial,p)','(a,b,y,bp,ws,partial,p)')
hook='    if(bmms1256::TryLaunch(a,b,y,int(B),int(M),int(N),int(K),x.dtype,ta,tb,cores,stream))return;\n'
i=base.index('extern "C" void run_kernel(');src=base[:i]+mod+base[i:]
i=src.index('    if(bmms1241::TryLaunch');src=src[:i]+hook+src[i:]
assert src.replace(mod,'',1).replace(hook,'',1)==base
name='v12_r56_case12_b_nz_prepack.asc';assert not (v/name).exists()
(v/name).write_bytes(src.encode());(lab/'r56.asc').write_bytes(src.encode())
meta=dict(version='v12_r56',parent='v12_baseline_r41.asc',file=name,sha256=hashlib.sha256(src.encode()).hexdigest(),
    status='experimental pending NPU validation',change='B once-packed raw-word NZ in fused AIV stage; original r30 AM128BN256 plan, A load, MMAD order, ring and consumer retained',
    gate='r51 original known Case12 domain, no N%128 or new macro divisibility guard; explicit UB/workspace bound',
    parent_byte_recovery=True,new_device_entries=4)
(v/'v12_r56_manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
cm=(lab/'CMakeLists.txt').read_text();cm=cm.replace('foreach(v r41 r51 r52 r53 r54 r55)','foreach(v r41 r51 r52 r53 r54 r55 r56)')
(lab/'CMakeLists.txt').write_bytes(cm.encode())
(lab/'check_r56.sh').write_text('''#!/usr/bin/env bash
set -eo pipefail
source /home/developer/Ascend/cann-9.0.0/set_env.sh
set -u
cd /home/developer/bmms_case12_k1_20261001
trap 'echo R56_FAILED > results/r56.status' ERR
echo R56_BUILD > results/r56.status
cmake -S . -B build >logs/r56_configure.log 2>&1
cmake --build build --target bench_r56 -j2 >logs/r56_build.log 2>&1
echo R56_PRECISION > results/r56.status
timeout 180 ./build/bench_r56 cases/all.txt 3 results/r56_correctness.jsonl >logs/r56_correctness.log 2>&1
echo R56_SCREEN > results/r56.status
python3 run_screen.py --baseline r41 --candidate r56 --manifest cases/screen.txt --tag r56_screen --repeats 30 --discard 5 --windows 2 >logs/r56_screen.log 2>&1
echo R56_DONE > results/r56.status
''',encoding='utf-8',newline='\n')
(out/'PLAN.md').write_text('''# B/NZ实验（Judge r55反馈后）

父版本r41。r55支持r54完整入口MISS，具体拒绝条件仍未知。本轮不用r54的N余数或新macro整除门槛，使用原r30的Case12已知范围。

假设：一次性B预打包增加全局读写及barrier，但消除每个M分片重复ND→NZ转换。保留A的ND2NZ、原plan、AM128BN256、K1=256/K0=64及r30预取。总GM→L1逻辑B字节不减少；不把预打包称为B加载复用。

冻结验证：沿用164组CPU FP64参考。32组screen及96组holdout使用原先固定划分。筛选计时包含整个融合kernel的PackB、同步和compute，不能仅计打包后的Cube。screen若收益混合，门槛必须先由screen确定、再用holdout验证；无稳定子域则不提交Judge。

PackB用两块32KiB UB，输入和输出均为raw16字节搬运，不对BF16做half算术。所有AIV参与pack结束barrier；AIC等待组内两AIV发布PACK_TO_CUBE，再读packed GM。flag0/2与ring4..7以及SyncAll保留flag分离。UB总量在190KiB以内；GPU/NPU实测前仍需验证API与索引。
''',encoding='utf-8')
print(json.dumps(meta))
