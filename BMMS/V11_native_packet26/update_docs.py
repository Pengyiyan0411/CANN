"""Update current entry points and retain the preceding audit verbatim."""
from pathlib import Path
import shutil,subprocess
ROOT=Path(__file__).resolve().parents[1];HERE=Path(__file__).resolve().parent;OUT=ROOT/'BMMS_V11_R26'
PREVIOUS='4ec031775941d2897250aef7a82af9fa3937a220'
def write(p,s):p.write_text(s,encoding='utf-8',newline='\n')
def main():
    snap=ROOT/'audit_current/AUDIT_R25_DELIVERY.md'
    old=subprocess.check_output(['git','show',PREVIOUS+':BMMS/BatchMatmulMaxSum_当前审计报告_2026-09-26.md'],cwd=ROOT/'CANN_archive')
    if snap.exists():assert snap.read_bytes()==old
    else:snap.write_bytes(old)
    readme='''# BatchMatmulMaxSum：R25 Case5 冻结，R26 仅调整单 batch Native 消费策略

最新两图均15/15，Case5为6.60/6.45 μs，Case13为16.80/16.91 μs，Case14为13.84/13.63 μs。
按上一轮首选交付暂归属 R25，用户未再次确认文件名，平台源hash未知。
R26 从完整 R25 派生：保留 Case5 内核和路由，只替换 Native B1/K128/M,N>32/blocks>1 的消费者。

- [R26 完整提交文件](BMMS_V11_R26/R26_DENSE_PACKET.asc)
- [R26 提交包，含冻结 R25 对照](BMMS_V11_R26_提交包.zip)
- [提交顺序与验证边界](BMMS_V11_R26/README.md)
- [设计和源码证据](V11_native_packet26/DESIGN.md)
- [本轮截图归档](V11_results/2026-09-27_r25_observed/AUDIT.md)
- [当前审计](BatchMatmulMaxSum_当前审计报告_2026-09-26.md)

本地源码/host/边界检查通过，未做 CANN/NPU 编译运行。R26 平台结果待回传。
先验证13/14收益、Case5保持以及全部15点，再推进其他点。旧提交源码与ZIP保持冻结。

```powershell
python V11_native_packet26/build.py
python V11_native_packet26/run_checks.py
python V11_native_packet26/check_host.py
python V11_native_packet26/check_bounds.py
python V11_native_packet26/record_results.py
python V11_native_packet26/update_docs.py
python V11_native_packet26/package.py
```
'''
    write(ROOT/'README.md',readme)
    github=readme
    for prefix in ['BMMS_V11_R26/','BMMS_V11_R26_提交包.zip','V11_native_packet26/DESIGN.md','V11_results/','BatchMatmulMaxSum_当前审计报告_2026-09-26.md']:
        github=github.replace(']('+prefix,'](BMMS/'+prefix)
    github=github.replace('```powershell\n','```powershell\ncd BMMS\n')
    write(HERE/'CANN_README.md',github)
    write(ROOT/'BatchMatmulMaxSum_当前审计报告_2026-09-26.md','''# 当前审计：保留 Case5 优势，R26 调整 13/14 消费粒度

2026-09-27。用户要求先针对13/14调整策略，并保持5的优势；当前不推进其他点。
两份新截图均15/15 Pass，误差显示0.00%，完整数据与归属说明在[本轮结果](V11_results/2026-09-27_r25_observed/AUDIT.md)。

| Case | 新图1 μs | 新图2 μs | 本轮决定 |
|---|---:|---:|---|
| 5 | 6.60 | 6.45 | 冻结 R25 多batch整输出归约 |
| 13 | 16.80 | 16.91 | 在 B1/K128 元数据域尝试 packet 批量消费 |
| 14 | 13.84 | 13.63 | 同上，保留原 Cube、plan和最终归约次序 |
| 15 | 15.30 | 15.03 | 保留 R23 Split-K |

用户没有再次写明文件名，工作上按上一轮首选 R25_NATIVE_TARGETED 归属；这不是平台源码hash核验。
Case5两次读数均低于上一批未干预范围；13/14变化较小，无相邻同环境控制，不宣称统计显著。
没有按各点比例统一“去噪”，也不将跨提交最低值拼成一次成绩。

R26仅在原 Native 已选中后，进一步限制 B1、K128、M/N>32、原blocks>1。
分组读取最多四个 C 小块，完整列且有效M相同的相邻块合并DMA；尾列有效范围搬运，保留-inf填充。
整包进入UB后两AIV释放GM槽位，随后沿原顺序归约。阶段复用UB，显式最大148640B。
Case5的原消费者、生产者、8个绑定、plan与分配保持R25；其他域外路径逐字可还原。
未知测试点仍可能与13/14同属目标元数据域，因此性能退化与Case映射需平台全15点判定。

R25/R26各318次源码模型、70次隔离归并与194次重复核对，普通输出逐位一致。
6276次实际host对照中6164次域外记录完全相同；其中80次覆盖Case5的元数据条件。
实际cursor核对341754个tile，检查32640组UB边界；错误步长、漏尾填充、早释放及扩宽路由故障均被拒绝。
完整证据和API依据见[设计文档](V11_native_packet26/DESIGN.md)。

尚无本地 CANN 编译或 NPU 结果。CPU检查不证明真实性能或全数值域正确性。
先提交[R26_DENSE_PACKET.asc](BMMS_V11_R26/R26_DENSE_PACKET.asc)，验证全15点，再判13/14的可重复收益。
[提交包](BMMS_V11_R26_提交包.zip)含原字节R25对照，必要时相邻提交排除波动。未验证前保留R25作为回退。
原R25交付时审计保存于[快照](audit_current/AUDIT_R25_DELIVERY.md)。
''')
    write(OUT/'README.md','''# R26_DENSE_PACKET 提交说明

先提交 `R26_DENSE_PACKET.asc`。它是完整单文件，不需要与其他文件拼接。
`CONTROL_R25.asc` 与之前 `R25_NATIVE_TARGETED.asc` 原字节相同，用于回退或相邻对照。

保持 Case5 的多 batch 专用入口；仅对原 Native 中 B1、K128、M/N>32、blocks>1 使用 packet 消费者。
完整N列的相邻块合并DMA，尾列按有效范围搬入；入UB后释放GM槽位，原plan/Cube/partial与最终归约不变。

本地源码回放、host分派、边界检查通过，详情见三个 CHECKS 文件。没有本地 CANN/NPU 测试。
先核对15/15及误差，再比较13/14；Case5以当前6.45–6.60 μs的观测为参考，保留评测波动余量。
若只变化零点几微秒，不凭一次提交认定收益；用 CONTROL_R25 相邻对照。其余点同样需要完整回传。
失败或13/14无可重复收益，回退CONTROL_R25。暂不推进其他测试点，也不追加shape探针。

`DESIGN.md` 包含同步、尾块、UB复用及数值边界。`MANIFEST.json` 绑定源码hash。
在完整归档仓库根目录的 BMMS 文件夹，可按主 README 的命令重建源码和CPU检查。
''')
    shutil.copyfile(HERE/'DESIGN.md',OUT/'DESIGN.md')
    print('Current audit and delivery instructions updated; previous audit retained verbatim.')
if __name__=='__main__':main()
