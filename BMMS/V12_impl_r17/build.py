from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parents[1];H=R/'V12_npu_lab/harness'
raw=(R/'BMMS_V12/v12_baseline_r12.asc').read_bytes();sha=hashlib.sha256(raw).hexdigest()
assert sha=='a845fd9538fe71d5f6284fced34781d8fb7e997105c51065a84b344818ddbd2b'
s=(R/'BMMS_V12/v12_r16_case8_blockpack_nz.asc').read_text();a=s.index('// BMMS1216_BEGIN');b=s.index('// BMMS1216_END',a)+len('// BMMS1216_END')
mod=s[a:b].replace('1216','1217')
a=mod.index('    AscendC::TEventID freeId[PACK_SLOTS];');b=mod.index('    // Every AIV',a)
mod=mod[:a]+'''    auto freeId=pipe->AllocEventID<AscendC::HardEvent::MTE3_V>();
    const int worker=AscendC::GetBlockIdx(),workers=2*p.cube.blocks;
    const int jobs=p.a.jobs+p.b.jobs;
    int issued=0;
    // Two 64-KiB regions: ND input and NZ output. Both fit inside the old
    // 128-KiB pack allocation. Sequential ownership avoids any buffer race.
    auto x=buf.Get<half>(),z=buf.Get<half>()[PACK_SLOT_ELEMS];
    for(int job=worker;job<jobs;job+=workers){
        const bool isA=job<p.a.jobs;const PackDesc d=isA?p.a:p.b;
        const int j=isA?job:job-p.a.jobs,colTiles=(d.dstCols+127)/128;
        const int row0=(j/colTiles)*d.rowsPerJob,col0=(j%colTiles)*128;
        const int rows=MinI(d.rowsPerJob,d.dstRows-row0),cols=MinI(128,d.dstCols-col0);
        const int realRows=MinI(rows,d.srcRows-row0),realCols=MinI(cols,d.srcCols-col0);
        if(issued)AscendC::WaitFlag<AscendC::HardEvent::MTE3_V>(freeId);
        AscendC::Duplicate(x,half(0.0f),rows*cols);
        if(realRows>0&&realCols>0){
            bmms71::Fence<AscendC::HardEvent::V_MTE2>(*pipe);
            const int pitch=(realCols+15)/16*16;
            AscendC::DataCopyExtParams cp{static_cast<uint16_t>(realRows),uint32_t(realCols*2),
                uint32_t((d.srcCols-realCols)*2),uint32_t((cols-pitch)/16),0};
            AscendC::DataCopyPadExtParams<half> pd{true,0,static_cast<uint8_t>(pitch-realCols),half(0.0f)};
            const int64_t src=int64_t(row0)*d.srcCols+col0;
            if(isA)AscendC::DataCopyPad(x,ga[src],cp,pd);else AscendC::DataCopyPad(x,gb[src],cp,pd);
            bmms71::Fence<AscendC::HardEvent::MTE2_V>(*pipe);
        }else AscendC::PipeBarrier<PIPE_V>();
        // UB-to-UB DataCopy executes on PIPE_V (CANN dav_c220 implementation).
        // Reorder 32-byte blocks locally; do not issue strided 32-byte GM writes.
        AscendC::DataCopyParams local{static_cast<uint16_t>(rows),1,static_cast<uint16_t>(cols/16-1),0};
        for(int c=0;c<cols;c+=16)AscendC::DataCopy(z[c*rows],x[c],local);
        bmms71::Fence<AscendC::HardEvent::V_MTE3>(*pipe);
        AscendC::DataCopyParams out{static_cast<uint16_t>(cols/16),static_cast<uint16_t>(rows),0,
            static_cast<uint16_t>(d.dstRows-rows)};
        const int64_t dst=int64_t(col0/16)*d.dstRows*16+row0*16;
        if(isA)AscendC::DataCopy(gap[dst],z,out);else AscendC::DataCopy(gbp[dst],z,out);
        AscendC::SetFlag<AscendC::HardEvent::MTE3_V>(freeId);++issued;
    }
    if(issued)AscendC::WaitFlag<AscendC::HardEvent::MTE3_V>(freeId);
    pipe->ReleaseEventID<AscendC::HardEvent::MTE3_V>(freeId);
'''+mod[b:]
frag=(mod+'\n\n').encode();anchor=b'extern "C" void run_kernel(GM_ADDR a,const TensorGroupInfo& ia,'
idx=raw.index(b'    if(bmms_c8p43::TryLaunch');end=raw.index(b'\n',idx)+1;line=raw[idx:end];hook=line.replace(b'bmms_c8p43::',b'bmms1217::')
data=raw.replace(anchor,frag+anchor,1).replace(line,hook+line,1)
assert data.replace(frag,b'',1).replace(hook,b'',1)==raw
name='v12_r17_case8_ub_repack_nz.asc';(R/'BMMS_V12'/name).write_bytes(data);(H/'r17.asc').write_bytes(data)
j=dict(candidate=name,parent='v12_baseline_r12.asc',parent_sha256=sha,sha256=hashlib.sha256(data).hexdigest(),parent_recovered_byte_for_byte=True,status='experimental, pending device validation',pack_tile=[256,128],pack_ub_bytes=131072,producer='r13 NZ GM-to-L1',macro_and_plan_unchanged=True)
(R/'BMMS_V12/v12_r17_manifest.json').write_text(json.dumps(j,indent=2)+'\n')
e=(H/'event_bench_r16.asc').read_text().replace('1216','1217').replace('"r16"','"r17"');(H/'event_bench_r17.asc').write_text(e,newline='\n')
c=H/'CMakeLists.txt';st=c.read_text()
if 'add_executable(event_bench_r17' not in st:
 a=st.index('add_executable(event_bench_r16');st+=st[a:].replace('r16','r17');c.write_text(st,newline='\n')
(H/'validate_c8_r17.sh').write_text((H/'validate_c8_r16.sh').read_text().replace('r16','r17'),newline='\n')
print(json.dumps(j,indent=2))
