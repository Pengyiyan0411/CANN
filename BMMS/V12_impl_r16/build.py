from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parents[1];H=R/'V12_npu_lab/harness'
raw=(R/'BMMS_V12/v12_baseline_r12.asc').read_bytes();sha=hashlib.sha256(raw).hexdigest()
assert sha=='a845fd9538fe71d5f6284fced34781d8fb7e997105c51065a84b344818ddbd2b'
s=(R/'BMMS_V12/v12_r13_case8_prepacked_nz.asc').read_text();a=s.index('// BMMS1213_BEGIN');b=s.index('// BMMS1213_END',a)+len('// BMMS1213_END')
mod=s[a:b].replace('1213','1216')
mod=mod.replace('    d.rowsPerJob=dr;\n    d.jobs=dc/16; // one complete NZ C0 stripe per job', '    d.rowsPerJob=PACK_SLOT_ELEMS/128;\n    d.jobs=((dr+d.rowsPerJob-1)/d.rowsPerJob)*((dc+127)/128);')
a=mod.index('        const int col0=j*16,rows=d.dstRows;');b=mod.index('        AscendC::SetFlag<AscendC::HardEvent::MTE3_V>',a)
mod=mod[:a]+'''        const int colTiles=(d.dstCols+127)/128;
        const int row0=(j/colTiles)*d.rowsPerJob,col0=(j%colTiles)*128;
        const int rows=MinI(d.rowsPerJob,d.dstRows-row0),cols=MinI(128,d.dstCols-col0);
        const int realRows=MinI(rows,d.srcRows-row0),realCols=MinI(cols,d.srcCols-col0);
        const int slot=issued&(PACK_SLOTS-1);
        if(issued>=PACK_SLOTS)AscendC::WaitFlag<AscendC::HardEvent::MTE3_V>(freeId[slot]);
        auto x=buf.Get<half>()[slot*PACK_SLOT_ELEMS];
        AscendC::Duplicate(x,half(0.0f),rows*cols);
        if(realRows>0&&realCols>0){
            bmms71::Fence<AscendC::HardEvent::V_MTE2>(*pipe);
            const int pitch=(realCols+15)/16*16;
            AscendC::DataCopyExtParams cp{static_cast<uint16_t>(realRows),uint32_t(realCols*2),
                uint32_t((d.srcCols-realCols)*2),uint32_t((cols-pitch)/16),0};
            AscendC::DataCopyPadExtParams<half> pd{true,0,static_cast<uint8_t>(pitch-realCols),half(0.0f)};
            const int64_t src=int64_t(row0)*d.srcCols+col0;
            if(isA)AscendC::DataCopyPad(x,ga[src],cp,pd);
            else AscendC::DataCopyPad(x,gb[src],cp,pd);
            bmms71::Fence<AscendC::HardEvent::MTE2_MTE3>(*pipe);
        }else bmms71::Fence<AscendC::HardEvent::V_MTE3>(*pipe);
        // Read 128 physical columns together, then scatter C0 stripes from
        // UB. Each (row slab, column slab) job owns disjoint padded NZ cells.
        AscendC::DataCopyExtParams out{static_cast<uint16_t>(rows),32,uint32_t(cols/16-1),0,0};
        for(int c=0;c<cols;c+=16){
            const int64_t dst=int64_t((col0+c)/16)*d.dstRows*16+row0*16;
            if(isA)AscendC::DataCopyPad(gap[dst],x[c],out);
            else AscendC::DataCopyPad(gbp[dst],x[c],out);
        }
'''+mod[b:]
frag=(mod+'\n\n').encode();anchor=b'extern "C" void run_kernel(GM_ADDR a,const TensorGroupInfo& ia,'
idx=raw.index(b'    if(bmms_c8p43::TryLaunch');end=raw.index(b'\n',idx)+1;line=raw[idx:end];hook=line.replace(b'bmms_c8p43::',b'bmms1216::')
data=raw.replace(anchor,frag+anchor,1).replace(line,hook+line,1)
assert data.replace(frag,b'',1).replace(hook,b'',1)==raw
name='v12_r16_case8_blockpack_nz.asc';(R/'BMMS_V12'/name).write_bytes(data);(H/'r16.asc').write_bytes(data)
j=dict(candidate=name,parent='v12_baseline_r12.asc',parent_sha256=sha,sha256=hashlib.sha256(data).hexdigest(),parent_recovered_byte_for_byte=True,status='experimental, pending device validation',pack_tile=[256,128],producer='r13 NZ GM-to-L1',macro_and_plan_unchanged=True)
(R/'BMMS_V12/v12_r16_manifest.json').write_text(json.dumps(j,indent=2)+'\n')
e=(H/'event_bench_r14.asc').read_text().replace('1214','1216').replace('"r14"','"r16"')
(H/'event_bench_r16.asc').write_text(e,newline='\n')
c=H/'CMakeLists.txt';st=c.read_text()
if 'add_executable(event_bench_r16' not in st:
 a=st.index('add_executable(event_bench_r15');st+=st[a:].replace('r15','r16');c.write_text(st,newline='\n')
(H/'validate_c8_r16.sh').write_text((H/'validate_c8_r15.sh').read_text().replace('r15','r16'),newline='\n')
print(json.dumps(j,indent=2))
