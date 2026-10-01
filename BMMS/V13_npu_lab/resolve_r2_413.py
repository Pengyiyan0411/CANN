from pathlib import Path
import json,hashlib
root=Path(__file__).resolve().parents[1];v=root/'BMMS_V13'
proof=json.loads((v/'evidence/compact_preprocess.json').read_text())
assert all(proof[x]['preprocessed_tokens_equal'] for x in ('host','aicore'))
p=v/'evidence/r2_compact_manifest.json';manifest=json.loads(p.read_text())
source=v/manifest['submission']
assert hashlib.sha256(source.read_bytes()).hexdigest()==manifest['submission_sha256']
manifest['compiler_preprocessing_equivalence']={'tool':'CANN 9.0 Bisheng, dav-2201','host_tokens_equal':True,'device_tokens_equal':True,'report':'compact_preprocess.json'}
p.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
p=v/'MAINLINE.json';m=json.loads(p.read_text(encoding='utf-8'))
m['active_candidate']=source.name;m['candidate_sha256']=manifest['submission_sha256']
m['candidate_status']='HTTP 413 upload rejection resolved by 21.02% source compaction; host/device preprocessed tokens identical to locally validated r2; Judge15 pending'
m['readable_candidate_source']=manifest['original'];m['readable_source_sha256']=manifest['original_sha256']
m['judge_r2_feedback']={'result':'NOT_EVALUATED','failure_type':'HTTP 413 Request Entity Too Large','case':None,'source':'User supplied the HTTP 413 HTML response; this is request rejection, not an operator correctness or runtime failure.','original_upload_source_sha256':manifest['original_sha256']}
m['recommended_submission']=source.name;m['upload_fix_report']='R2_UPLOAD_413.md'
p.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
oldnotice='> 更新：用户反馈 r2 提交 FAIL，已撤回推荐；失败类型/点号待核实。已接受基线仍为 r1。下文为提交前的分析与本地验证记录。\n\n'
newnotice='> 已确认先前“Fail”为 HTTP 413 上传请求过大，代码未进入测评。请提交 `v13_r2_submit_compact.asc`；它与原 r2 的 Host/Device 预处理代码一致。已接受基线仍为 r1。\n\n'
for name in ('README.md','VALIDATION.md','CASE12_BRANCH_ANALYSIS.md'):
    p=v/name;s=p.read_text(encoding='utf-8');assert oldnotice in s
    s=s.replace(oldnotice,newnotice)
    if name=='README.md':
        s=s.replace('[v13_r2_case12_o10.asc](v13_r2_case12_o10.asc)','[v13_r2_submit_compact.asc](v13_r2_submit_compact.asc)')
        s+='\n上传413的原因、更正与等价校验见 [R2_UPLOAD_413.md](R2_UPLOAD_413.md)。原始可读源码仍保留。\n'
    else:
        s=s.replace('最终提交：`v13_r2_case12_o10.asc`','最终提交：`v13_r2_submit_compact.asc`（原始可读源码为 `v13_r2_case12_o10.asc`）')
        s=s.replace('提交文件：`v13_r2_case12_o10.asc`','提交文件：`v13_r2_submit_compact.asc`（原始可读源码 `v13_r2_case12_o10.asc`）')
    p.write_text(s,encoding='utf-8')
p=v/'R2_JUDGE_FAILURE.md';old=p.read_text(encoding='utf-8')
p.write_text('# r2 反馈更正：HTTP 413 上传被拒\n\n用户补充的实际响应是 `413 Request Entity Too Large`。因此先前记录中的“Judge FAIL”并不是测评结论；上传阶段就被拒绝，不能据此判断算法、编译或精度失败。问题已按文件体积处理，交付 `v13_r2_submit_compact.asc`。详见 [R2_UPLOAD_413.md](R2_UPLOAD_413.md)。\n\n以下保留当时信息不足时的排查记录，后续判断以上述更正为准。\n\n---\n\n'+old,encoding='utf-8')
report=f'''# r2 HTTP 413 上传修复

## 原因

用户返回的 HTML 明确为 `413 Request Entity Too Large`。这是 HTTP 请求内容超过服务器或代理的限制，不是 kernel 的编译、精度或运行失败。服务端具体阈值未知，也可能按包含编码/表单开销的整个请求计算；本次不臆测固定上限。

## 提交文件

- 使用：[`{source.name}`]({source.name})。
- 原始可读源码 `{manifest['original']}` 保留。
- 文件体积：{manifest['original_bytes']:,} → **{manifest['submission_bytes']:,} 字节**，减少 **{manifest['reduction_pct']:.2f}%**。
- 压缩版小于此前用户确认能提交的 r72（363,256 字节）。实际服务器接收仍需重新上传确认。
- 只删除注释、空行和冗余横向空白，按 C++ 规则先处理反斜线续行；字符串/字符常量及预处理指令逻辑边界保持不变。
- 保留全部 kernel、路由、r72 小点优化和 Case12 O10；不引入算法修改，不新增版本号。

## 等价验证

1. 本地校验原始/压缩源码的逻辑行词法内容一致。
2. 在原 NPU 环境使用 CANN 9.0 Bisheng 对同一路径下的两份源码分别做 Host、Device 预处理。排除空白后，字符串及其他代码内容完全一致：
   - Host 438,790 个 token chunks，SHA256 `{proof['host']['outputs']['original']['canonical_sha256']}`。
   - Device 1,108,002 个 token chunks，SHA256 `{proof['aicore']['outputs']['original']['canonical_sha256']}`。
3. 沿用原 r2 的编译及 NPU 实验记录，不因仅注释/空白变化重复整个性能实验。历史严格抵消精度用例及 sanitizer 限制仍见 `VALIDATION.md`；413 本身与这些问题无关。

压缩版 SHA256：`{manifest['submission_sha256']}`。

生成脚本：`../V13_npu_lab/compact_submission.py`。
编译器等价证据：`evidence/compact_preprocess.json`。
版本状态已更正：r1 仍为已接受基线，压缩 r2 为待 Judge15 的提交候选。
'''
(v/'R2_UPLOAD_413.md').write_text(report,encoding='utf-8')
print(f'Ready: {source}, {source.stat().st_size} bytes; host/device equivalence verified; HTTP failure classification corrected.')
