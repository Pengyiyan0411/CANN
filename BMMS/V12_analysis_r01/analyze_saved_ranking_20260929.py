"""Analyze the user-saved first ranking page; never mix per-case best runs."""
from pathlib import Path
import hashlib
import html
import json
import math
import re
import shutil
import statistics
import sys
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
SOURCE = Path('C:/Users/cc/Downloads/CANNJudge.html')
OUT = ROOT / 'V12_results/2026-09-29_ranking_priority'
CURRENT = [2.35, 4.89, 5.28, 6.45, 6.37, 13.98, 8.93, 45.71,
           65.41, 79.00, 82.82, 113.68, 14.31, 13.04, 11.40]
TARGETS = {1: 1.9, 2: 3.2, 3: 3.2, 4: 4.3, 5: 4.0, 6: 10.0,
           7: 7.2, 8: 40.0, 9: 55.0, 10: 75.0, 11: 78.0,
           12: 100.0, 13: 11.0, 14: 11.0, 15: 9.5}


def clean(value):
    return ' '.join(html.unescape(re.sub('<[^>]+>', ' ', value)).split())


def number(value):
    match = re.fullmatch(r'([0-9.]+)\s*(μs|µs|ms)?', value)
    assert match, value
    return float(match[1]) * (1000 if match[2] == 'ms' else 1)


def component(t, best):
    # All observed times and selected targets >= TBest. No extrapolation below it.
    assert t >= best
    return 100 / (1 + math.log(t / best) / math.log(1.5))


def main():
    feedback = json.loads((ROOT / 'V12_results/2026-09-29_r44_feedback/RESULTS.json').read_text(encoding='utf-8'))
    assert [r['latency_us'] for r in feedback['rows']] == CURRENT
    mainline = json.loads((ROOT / 'BMMS_V12/MAINLINE.json').read_text(encoding='utf-8'))
    assert mainline['accepted_sota'] == 'v12_baseline_r41.asc'
    assert hashlib.sha256((ROOT / 'BMMS_V12/v12_baseline_r41.asc').read_bytes()).hexdigest() == mainline['accepted_sha256']
    raw = SOURCE.read_bytes()
    text = raw.decode('utf-8')
    rows = []
    best = None
    for tr in re.findall(r'<tr\b[^>]*>(.*?)</tr>', text, re.S):
        cells = [clean(c) for c in re.findall(r'<t[dh]\b[^>]*>(.*?)</t[dh]>', tr, re.S)]
        if len(cells) == 16 and cells[0].startswith('TBest'):
            best = list(map(number, cells[1:]))
        if len(cells) == 21 and cells[0].isdigit():
            # Team/contact identifiers are unnecessary for the analysis.
            rows.append({'rank': int(cells[0]), 'score': number(cells[4]),
                         'times_us': list(map(number, cells[6:]))})
    assert len(rows) == 20 and len(best) == 15
    assert [r['rank'] for r in rows] == list(range(1, 21))
    assert all(len(r['times_us']) == 15 for r in rows)
    residuals = [sum(component(t, b) for t, b in zip(r['times_us'], best)) / 15 - r['score'] for r in rows]
    assert max(map(abs, residuals)) <= .0051
    cases = []
    for i, (t, b) in enumerate(zip(CURRENT, best), start=1):
        values = sorted(r['times_us'][i-1] for r in rows)
        target = TARGETS[i]
        cases.append({'case': i, 'current_us': t, 'TBest_us': b,
                      'visible_fastest_us': values[0], 'visible_fifth_fastest_us': values[4],
                      'visible_median_us': statistics.median(values),
                      'visible_rows_faster_than_current': sum(v < t for v in values),
                      'scenario_target_us': target,
                      'scenario_score_gain': (component(target, b) - component(t, b)) / 15,
                      'gain_to_visible_fifth': max(0, component(values[4], b) - component(t, b)) / 15})
    score = sum(component(t, b) for t, b in zip(CURRENT, best)) / 15
    data = {
        'source': str(SOURCE), 'source_sha256': hashlib.sha256(raw).hexdigest(),
        'source_modified_local': datetime.fromtimestamp(SOURCE.stat().st_mtime).isoformat(),
        'scope': 'User-saved first page, ranks 1-20 only; not the full/live leaderboard.',
        'formula_status': 'Empirically reconstructed and checked against all 20 rows, not official-rule certification.',
        'formula': 'mean(100/(1+ln(time/TBest)/ln(1.5)))',
        'max_score_reconstruction_error': max(map(abs, residuals)),
        'current_source': 'V12_results/2026-09-29_r44_feedback/RESULTS.json; latest all-normal screenshot, inferred version association',
        'current_baseline': 'v12_baseline_r41.asc',
        'current_estimated_score_not_official': score,
        'current_times_us': CURRENT, 'cases': cases, 'ranking': rows,
        'scenario_warning': 'Targets are experiment objectives and score sensitivity examples, not achieved or promised performance.',
    }
    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SOURCE, OUT / 'CANNJudge_snapshot.html')
    (OUT / 'ANALYSIS.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    table = '\n'.join(f"|{c['case']}|{c['current_us']:.2f}|{c['visible_fastest_us']:.2f}|{c['visible_fifth_fastest_us']:.2f}|{c['visible_median_us']:.2f}|{c['visible_rows_faster_than_current']}|{c['scenario_target_us']:.2f}|+{c['scenario_score_gain']:.3f}|" for c in cases)
    gain_small = sum(cases[i-1]['scenario_score_gain'] for i in (2, 3, 4))
    gain_small9 = gain_small + cases[8]['scenario_score_gain']
    report = f'''# 榜单与下一阶段优化顺序：2026-09-29

结论：主线继续 r41。下一阶段主攻顺序建议 **Case2 → Case3/4 → Case9 → Case5 → Case12**；Case6 优先做少量路由诊断，一旦确认存在具体结构机会，可插入 Case9 前后。Case1 只给一轮短实验，不阻塞主攻。其后考虑 Case7、13/14；Case10/11/15 维持成果，Case8 暂缓重投入。

这不是把点6排到最后：它是高价值但尚缺路由证据的任务。以上顺序结合提分幅度、方案覆盖、历史失败和可验证程度，没有编造成功概率或小时收益率。

## 来源与比较边界

- 用户本地榜单文件修改时间 {data['source_modified_local']}；保存了排名1–20的全部15点成绩，不是完整榜单，也不声称这些数据仍等于当前线上状态。
- 对照使用最近 r44 回传的整张正常耗时截图，不拼接各轮最低值。r44 的 Case12 诊断 MISS，主线仍为已接受的 r41。截图未包含平台源码哈希，版本关联来自对话及既有归档。
- 时延单位均为 μs。TBest 使用同一份榜单，其中 Case9=50.68。
- 按 `mean(100/(1+ln(t/TBest)/ln(1.5)))` 重算20行分数，最大绝对误差 {data['max_score_reconstruction_error']:.6f}，与两位小数显示一致。它是数据验证的评分模型，未取得官方规则正文认证。
- 当前整张截图按该榜单估算 {score:.3f} 分，不是官方提交分数。不同提交轮次的噪声仍存在；邻近成绩排名不能作为统计显著性。

## 全点对比

“第5快”是前20名队伍在该点的第5快，不是榜单第5名的成绩。“更快数”仅在这20条可见记录中计数。目标仅为收益测算，不是承诺或实测结果。

|点|当前|可见最快|可见第5快|可见中位数|更快数/20|测算目标|总分增量|
|---|---:|---:|---:|---:|---:|---:|---:|
{table}

2/3/4 三点分别达到3.2/3.2/4.3时，合计约 +{gain_small:.3f} 分；再让9达到55，合计约 +{gain_small9:.3f} 分。这是静态同口径情景，不是预测。相比之下8从45.71到40仅约+0.169分。

## 第一优先级：小矩阵2/3/4，先2验证机制，再扩展3/4

Case2有R50及v12_r03的真实收益，接管域和代码较清楚。当前bmms1203已经K常量化，但M/N仍在设备端动态循环，部分布局仍构造索引并逐行Gather，Tiny仍逐点积ReduceSum。应先用同域合成簇定位指令/同步开销，再试有限M/N分桶或常量化、批量点积归约和数据布局组织；分派只依赖合法运行时元数据。

Case3/4是榜单最普遍的短板：20/20及19/20可见队伍更快，且共同代码可能一轮覆盖两个点。历史画像是B>1、小M/N、短K，但原始Universal证据尚未独立复核。R51只是扩展R50的分阶段计算，线上无明显收益；不能把原R51重提，也不能从无收益断定未命中。若下一版依赖同族归属，先用一个校准的接管谓词验证，命中后再检查每AIV的batch数、布局与尾部成本。

第一轮不要盲换Cube：在小M/N、短K下，新增AIC/AIV搬运和同步可能抵消计算收益。Cube只作为在同域实测的独立对照，不能当成保证更快的结论。Case1保留独立单点积路线；不让为2/3/4增加的矩阵组织开销反向影响1。

## 第二优先级：Case9；10/11只作共同回归观察

9当前65.41、可见第5快53.06，多个队伍均做到52–58，目标55对应约+1.456分，机会比单看相对TBest的倍数更有价值。已知B1、M/N>=1024、1024<=K<1536、原R06域，现有r33的短K宏块流水有效。

不要重复r02/r34的完整A驻留、r04的类似缓存或r07消费者微调。先用当前r41建立短K合成簇，在保持完整K累加、Max/Sum语义的条件下研究GM→L1布局/任务访问顺序；若新假说依赖实际网格，先定位该门槛，而不是精确二分所有维度。

10/11虽然靠近TBest时评分边际较陡（79→75约+0.646分；82.82→78约+0.715分），但可见20队中分别只有2/4队更快，已无相同程度的普遍短板。保留共同路径可能带来的自然收益，不再为它们盲扫一套kernel。

## Case6：高价值诊断，确认后可提升到第二梯队前列

13.98相对可见中位10.305明显落后，20/20可见队伍更快；到10约+1.107分。问题在于当前历史证据仍未确认route，之前若干压力无响应不能排除原本就单组的路线。

先审计当前host选择顺序并给候选route做互斥分组：一条全覆盖强通道校准，再按实际候选集自适应二分。必须确保干预能让“本来单组”的route也明显响应；不能继续只把cores改成1。每次输出不变、避免超时，只解释校准成立的结果。若最终仅剩两类，一条谓词即可选方向；不能在没枚举候选前承诺固定总探针数。此轮不需要知道精确M/N/K。

## 第三优先级：Case5的新执行方式

Case5的证据比3/4和6更完整：Native强通道确认K128、M/N各为16或32、B在2–64；现有R25已把完整batch交给一个AIV，并消除了partial及SyncAll。因此“再删全局归约”不是新机会。

剩余可测方向是小batch完整运算的Vector路线，或紧凑批量Cube传输/发布路线，与现有R25逐一做受控对比；不要把两者合成一版后无法归因。只有四种空间组合，B取跨核数边界、两dtype和四布局即可建立有效筛选簇，不必先精确探B。M=N=32、K128的直接全产品缓冲很大，Vector必须分块并先核对UB，不直接照搬点2代码。

榜单可见最快2.26证明存在竞争方案，但第5快仍4.94，说明极低时延尚非普遍现象。第一目标4–5，不能按2.26给它估算必得收益。Case5从6.37降到4的分数增益约+0.672，低于3/4及9的目标收益。

## 第四优先级：Case12，保留有边界的研究投入

113.68→100仍有约+1.113分，不能认为不值得做。但r45 B驻留、r48并行Max、r50延后partial写回都未通过；r49虽有局部改善，却出现16.81%退化，不能直接晋升。

合成样本的计数器支持优先看MTE2加载/ND→NZ/调度交互，而不是继续叠加merge技巧；这些证据不等于隐藏Case12瓶颈已确定。r44只说明整宏块展平无法降低峰值宏块数量，不意味着已达到耗时下界。

下一次只接受有独立留出收益、退化边界可解释的加载或访问顺序实验。给两轮实测上限；无稳定收益就继续后续点，避免因形状资料最完整而持续集中卡时。

## 后续：7、13/14；暂缓8和重复打磨15

- 7约8.93→7.2测算+0.418。R48的batch独占、去跨组归约已有效，不能再以相同改动为下一版；需新的producer/流水假说。
- 13/14有大差距的个别成绩，但可见中位数已接近或慢于当前。13已尝试r08局部sum、r09 B常驻、r35/r36大M宏块，普遍收益不稳定。先获得新的profile/布局证据，再投入；不能因TBest约5就认定可低成本减半。
- 1可单独给一轮固定启动与短向量指令开销实验；2.35→1.9测算+0.638。原路线已无Gather、workspace、跨核归约，需要的是具体剩余开销证据，不能列举不存在的可删除动作。
- 8当前45.71，可见只有2队更快，已胜过大多数前列队伍。进一步NZ跨宏块预取r43在合成簇退化；不重复同方向盲试。明显降低耗时不一定带来同等分数增益。
- 15从约15降到约11已有稳定结构收益。11.4→9.5仅约+0.272，当前优先保留。

## 实验节奏与验收

1. 主线冻结r41，每个新方向单独派生。先小簇筛选，再新形状留出；不混入未晋升候选。
2. 性能使用同机A/B、B/A独立窗口，输入/输出校验与实际kernel命中一并记录。短时延点先A/A测波动；设备流时间与Judge口径分开。
3. 小矩阵方向目标是可重复的明显改善，不为0.1μs级单次变化提交一堆变体。新候选通过数值、资源/边界检查及目标域性能后，再完整15点Judge回归。
4. 2/3/4最多先做两条真正不同的机制；9/12各给两轮有假说的实测。未过门槛立即记录失败并换方向，不由版本数量衡量进度。
5. 诊断与性能版本分离，反馈标注文件名/哈希。快慢的单张截图不能可靠解码弱信号，负结果必须有阳性校准。

## 本地依据

- 榜单快照：本目录CANNJudge_snapshot.html；结构化数据ANALYSIS.json。
- 基线：BMMS_V12/MAINLINE.json；BMMS_V12/v12_baseline_r41.asc。
- 最新整图：V12_results/2026-09-29_r44_feedback/RESULTS.json。
- 小矩阵：BMMS_V12/v12_r02_r03_README.md；BMMS_V11_R51/README.md；BMMS_点2_形状证据与R50方案_20260928.md。
- Native证据：V11_results/2026-09-27_d24_native/AUDIT.md；V11_native_targeted25/DESIGN.md。
- 失败实验：V12_npu_lab/results/native_macro_20260929/REPORT.md；V12_npu_lab/results/parallel_epilogue_20260929/REPORT.md。
- 原榜单网址：https://cannjudge.cn/public/op_challenge_shanghe_prelim/batchmatmulmaxsum/ranking 。本报告以用户本地快照为准。
'''
    (OUT / 'PRIORITY.md').write_text(report, encoding='utf-8')
    print(json.dumps({'rows': len(rows), 'estimated_score': score,
                      'max_formula_error': max(map(abs, residuals)),
                      'report': str(OUT / 'PRIORITY.md'),
                      'small_cluster_scenario_gain': gain_small,
                      'small_plus9_scenario_gain': gain_small9}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
