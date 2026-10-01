from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parents[1];H=R/'V12_npu_lab/harness'
raw=(R/'BMMS_V12/v12_baseline_r12.asc').read_bytes(); sha=hashlib.sha256(raw).hexdigest()
assert sha=='a845fd9538fe71d5f6284fced34781d8fb7e997105c51065a84b344818ddbd2b'
s=raw.decode().replace('\r\n','\n')
a=s.index('namespace bmms_c8p43 {');b=s.index('// BMMS_C8P43_END',a)+len('// BMMS_C8P43_END')
mod=s[a:b].replace('bmms_c8p43','bmms1213').replace('BMMS_C8P43','BMMS1213')
mod=mod.replace('    d.rowsPerJob=PACK_SLOT_ELEMS/dc;\n    if(d.rowsPerJob>0)d.jobs=(dr+d.rowsPerJob-1)/d.rowsPerJob;', '    d.rowsPerJob=dr;\n    d.jobs=dc/16; // one complete NZ C0 stripe per job')
a=mod.index('        const int row0=j*d.rowsPerJob;');b=mod.index('        AscendC::SetFlag<AscendC::HardEvent::MTE3_V>',a)
mod=mod[:a]+'''        const int col0=j*16,rows=d.dstRows;
        const int realCols=MinI(16,d.srcCols-col0);
        const int slot=issued&(PACK_SLOTS-1);
        if(issued>=PACK_SLOTS)AscendC::WaitFlag<AscendC::HardEvent::MTE3_V>(freeId[slot]);
        auto x=buf.Get<half>()[slot*PACK_SLOT_ELEMS];
        AscendC::Duplicate(x,half(0.0f),rows*16);
        if(realCols>0){
            bmms71::Fence<AscendC::HardEvent::V_MTE2>(*pipe);
            AscendC::DataCopyExtParams cp{static_cast<uint16_t>(d.srcRows),
                uint32_t(realCols*2),uint32_t((d.srcCols-realCols)*2),0,0};
            AscendC::DataCopyPadExtParams<half> pd{true,0,static_cast<uint8_t>(16-realCols),half(0.0f)};
            if(isA)AscendC::DataCopyPad(x,ga[col0],cp,pd);
            else AscendC::DataCopyPad(x,gb[col0],cp,pd);
            bmms71::Fence<AscendC::HardEvent::MTE2_MTE3>(*pipe);
        }else bmms71::Fence<AscendC::HardEvent::V_MTE3>(*pipe);
        // NZ global storage: [physical_col / 16, padded_physical_row, 16].
        const int64_t dst=int64_t(j)*d.dstRows*16;
        if(isA)AscendC::DataCopy(gap[dst],x,rows*16);
        else AscendC::DataCopy(gbp[dst],x,rows*16);
'''+mod[b:]
# Derive producer with ONLY GM-to-L1 stage layout changes. Original L1 NZ,
# L0/MMAD, ring, scheduler and consumer interfaces remain unchanged.
a=s.index('template<class T,bool TA,bool TB>\nclass ReuseProducer');b=s.index('class RowMaxConsumer',a)
prod=s[a:b].replace('ReuseProducer','NzProducer')
a=prod.index('        AscendC::Nd2NzParams qa');b=prod.index('        AscendC::SetFlag<AscendC::HardEvent::MTE2_MTE1>',a)
prod=prod[:a]+'''        const int aHeight=TA?p.K:p.M,aRows=TA?kr:ar,aCols=TA?ar:kr;
        const int aRow0=TA?k0:m0,aCol0=TA?m0:k0;
        AscendC::DataCopyParams qa{static_cast<uint16_t>(aCols/16),static_cast<uint16_t>(aRows),
            static_cast<uint16_t>(aHeight-aRows),0};
        AscendC::DataCopy(aa,a[int64_t(batch)*p.M*p.K+int64_t(aCol0/16)*aHeight*16+aRow0*16],qa);
        const int bHeight=TB?p.N:p.K,bRows=TB?br:kr,bCols=TB?kr:br;
        const int bRow0=TB?n0:k0,bCol0=TB?k0:n0;
        AscendC::DataCopyParams qb{static_cast<uint16_t>(bCols/16),static_cast<uint16_t>(bRows),
            static_cast<uint16_t>(bHeight-bRows),0};
        AscendC::DataCopy(bb,b[int64_t(batch)*p.K*p.N+int64_t(bCol0/16)*bHeight*16+bRow0*16],qb);
'''+prod[b:]
anchor='class MaskedRowMaxConsumer {'
prod='using Plan=CubePlan;\nconstexpr int K1=bmms11r2::K1,K0=bmms11r2::K0;\n'+prod
mod=mod.replace(anchor,prod+anchor,1).replace('bmms11r2::ReuseProducer<T,TA,TB>','NzProducer<T,TA,TB>')
mod=mod.replace('// Reuse the frozen R25 producer itself, not a modified copy.','// Read the once-packed NZ matrix; L1/L0 arithmetic is inherited.')
mod=mod.replace('// Preserve physical storage order. Padding is a bitwise copy, NOT a\n    // transpose or float conversion; the Cube uses the original TA/TB flags.', '// Describe physical ND input and its padded NZ storage. Raw words remain unchanged.')
frag=('// BMMS1213_BEGIN\n'+mod+'\n\n').encode()
anchor=b'extern "C" void run_kernel(GM_ADDR a,const TensorGroupInfo& ia,'
marker=b'    if(bmms_c8p43::TryLaunch';idx=raw.index(marker);end=raw.index(b'\n',idx)+1;line=raw[idx:end]
hook=line.replace(b'bmms_c8p43::',b'bmms1213::')
data=raw.replace(anchor,frag+anchor,1).replace(line,hook+line,1)
assert data.replace(frag,b'',1).replace(hook,b'',1)==raw
name='v12_r13_case8_prepacked_nz.asc';(R/'BMMS_V12'/name).write_bytes(data);(H/'r13.asc').write_bytes(data)
manifest=dict(candidate=name,parent='v12_baseline_r12.asc',parent_sha256=sha,sha256=hashlib.sha256(data).hexdigest(),parent_recovered_byte_for_byte=True,status='experimental, pending device validation')
(R/'BMMS_V12/v12_r13_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
# Event A/B harness, include both frozen baseline kernel and candidate.
e=(H/'event_bench_r12.asc').read_text();a=e.index('static void launch_direct');b=e.index('\nint main(',a)
launch=(H/'phase_c8.asc').read_text();x=launch.index('static void launch_direct');z=launch.index('\nint main(',x)
launch=launch[x:z].replace('int phase,','bool candidate,')
launch=launch.replace('if(phase==0){DISPATCH(bmms_c8p43);}else if(phase==1){DISPATCH(c8diag1);}else{DISPATCH(c8diag2);}', '''if(candidate){
        bmms1213::RaggedPlan q{};q.cube=p.cube;q.realM=p.realM;q.realN=p.realN;q.realK=p.realK;
        auto candidatePlan=bmms1213::MakePlan(p.realM,p.realN,p.realK,p.cube.blocks,ta,tb);
        q.a=candidatePlan.a;q.b=candidatePlan.b;
        // The two layouts use identical padded sizes/grid/workspace.
        auto p=q;DISPATCH(bmms1213);
    }else{DISPATCH(bmms_c8p43);}''')
e=e[:a]+launch+e[b:]
e=e.replace('!bmms1212::Eligible','!bmms_c8p43::Eligible').replace('bmms23::MakePlan(B,M,N,K,cores)','bmms_c8p43::MakePlan(M,N,K,cores,ta,tb)').replace('(bmms23::WorkspaceBytes(p)+uint64_t(p.M)*sizeof(float))','bmms_c8p43::WorkspaceBytes(p)').replace('candidate?"r12":"r03"','candidate?"r13":"r12"')
(H/'event_bench_r13.asc').write_text(e,newline='\n')
c=H/'CMakeLists.txt';s=c.read_text()
if 'add_executable(event_bench_r13' not in s:
 s+='''
add_executable(event_bench_r13 event_bench_r13.asc)
target_compile_definitions(event_bench_r13 PRIVATE BMMS_KERNEL_HEADER="r13.asc" BMMS_VARIANT="r13")
target_link_libraries(event_bench_r13 PRIVATE tiling_api register platform unified_dlog dl m graph_base)
target_include_directories(event_bench_r13 PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_options(event_bench_r13 PRIVATE $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=${NPU_ARCH}>)
add_custom_target(c8_r13_build DEPENDS bench_r13 event_bench_r13)
''';c.write_text(s,newline='\n')
print(json.dumps(manifest,indent=2))
