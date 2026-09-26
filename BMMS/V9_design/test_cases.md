# BatchMatmulMaxSum V9 用例设计

## 1. 算子标杆

精确业务顺序为逻辑布局下的 FP64 bmm → FP64 Max(N) → FP64 Sum(M) → 最后转 FP32。不能调用 FP32 bmm 后再把结果升到 FP64 来当标杆。

小例可直接用：

```python
a = x1.astype('float64')
b = x2.astype('float64')
if transpose_x1: a = a.swapaxes(1, 2)
if transpose_x2: b = b.swapaxes(1, 2)
y = (a @ b).max(axis=2).sum(axis=1, dtype='float64').astype('float32')
```

大例使用 [blocked_oracle.py](blocked_oracle.py)，按 batch/M/N 分块，K 点积完整；它保留全 M 的 FP64 row-max，最后统一 Sum 后转 FP32。BF16 输入先按真实 BF16 位值解码为可精确表示它的 FP32，再升 FP64；不能用未量化随机数组代替设备实际输入。

## 2. 用例说明

### 2.1 测试配置

`SUPPORTED_DTYPES = [float16, bfloat16]`；`LAYOUTS = [(False,False),(False,True),(True,False),(True,True)]`。所有下列元组顺序均为 `(B,M,N,K)`。

常规形状：

| 场景 | Shape |
|---|---|
| Dot | 1,1,1,32 |
| Resident | 2,4,8,64 |
| Native 对照 | 1,64,128,128 |
| 完整 K256 | 1,64,128,256 |
| 完整 K1024 | 1,64,128,1024 |
| 小输出大 K | 1,8,8,8192 |
| N1 | 1,65,1,128 |
| M1 | 1,1,65,128 |

泛化形状共16组，完整清单在 `prepare_design.py` 的 GENERAL 及 `precision_cases.jsonl`：覆盖 K40/72/136、K8184 尾段、M/N 非对齐、小输出边界、B3/20/21/64、M或N8192、输入规模上限。B20/21只是检验跨常见核数组合的场景，不硬编码机器核数。

数值场景：

| pattern | Shape | 输入构造规格 |
|---|---|---|
| all_negative | 1,17,33,40 | A 为正的可表示值，B 为负的可表示值，保证所有 dot<0 |
| all_zero | 1,17,33,40 | A/B 全0，检查首槽、尾块和输出写入 |
| equal_max | 1,17,33,40 | B 的多个列相同，构造跨 N tile 的相等最大值 |
| near_tie | 1,17,33,40 | 从实际量化后的输入构造近似相等列，在一列改变1个可表示 ULP；避免量化前差别量化后消失 |
| dot_rounding_loss | 1,8192,16,256 | A 行交替[1,2^-12]与[-1,0]；B列[1,2^-13]，其余K清零；将K32反例补零扩到新dense域 |
| n_split_crossing | 1,2,2,32 | 用前2个K维产生 C=[[10,0],[0,10]]，其余清零 |
| k_split_crossing | 1,2,2,64 | 第1段 dot=[10,0]、第2段=[-10,1]，每行相同；将有效项放在不同K段 |
| normalized_random | 2,31,65,136 | 逻辑行向量归一化后量化到对应输入类型；只作一个场景，不假定所有输入已归一化 |

随机种子固定20260926；输入内容从逻辑张量生成，再转置成连续物理存储，不能四种布局各自生成不同随机值。FP16/BF16 都实际量化后计算 oracle。

### 2.2 用例覆盖统计

| 类别 | 场景数 | dtype | 布局 | 用例数 |
|---|---:|---:|---:|---:|
| 常规形状 | 8 | 2 | 4 | 64 |
| 泛化形状 | 16 | 2 | 4 | 128 |
| 数值场景 | 8 | 2 | 4 | 64 |
| 合计 | 32 | 2 | 4 | 256 |

共享性能清单另含8个代表 shape，双 dtype×四布局，共64条；初次方向筛选仅取 FP16/NN 与 BF16/TT，共16条。它们覆盖 Native控制、大K、宽N、尾块、小输出和 strided GEMV；不代表隐藏15点的已知 shape。

## 3. 使用说明

执行 `python V9_design/prepare_design.py` 生成以下**用例规格**，不执行设备测试、不物化所有张量：

- `precision_cases.jsonl`：完整256条。
- `smoke_cases.jsonl`：其中32条，覆盖完整K、尾块、小输出和全负。
- `perf_cases.jsonl` / `perf_screen.jsonl`：完整64条 / 首轮16条。
- `manifest.json`：清单与 P01 对照源 SHA256。

JSONL 的 `device_status` 当前全部是 `NOT_RUN`。未来设备 runner 需实现 pattern 生成、真实 dtype 编码、实际路由记录、输入只读检查和输出保存；当前清单不能冒充即传即跑的上机包。

`stress_only=true` 的输入规模边界延后执行；先准备分块 golden 与数据磁盘预算，不能在初次短时筛选里运行全边界巨型矩阵乘。`precision_counterexamples.py` 可现在用 CPU 运行，验证数学反例与分块 oracle；它不是新 kernel 的测试。
