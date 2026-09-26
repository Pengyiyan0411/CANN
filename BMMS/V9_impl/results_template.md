# V9 评测结果记录

- 文件ID：
- 提交编号：
- 源SHA256（见MANIFEST.json）：
- 编译：成功 / 失败
- 编译或运行错误全文：
- 平台显示总分：
- 当前最优T是否完整保存：是 / 否

| 点 | 状态 | 用时μs | 当次最优T（可空） |
|---:|---|---:|---:|
|1||||
|2||||
|3||||
|4||||
|5||||
|6||||
|7||||
|8||||
|9||||
|10||||
|11||||
|12||||
|13||||
|14||||
|15||||

可选JSON输入格式（rows必须15项；compile_error则可省rows）：

```json
{
  "variant": "D01_DENSE_K128",
  "submission_id": "填写平台编号",
  "compile_error": null,
  "rows": [{"case": 1, "status": "Pass", "latency_us": 1.0}]
}
```

示例仅展示1行字段，使用脚本前需填全15行。每行可选 `best_us`；缺少任一行best_us时统一使用历史T，避免混用两个时点。

执行：`python record_results.py --input result.json`。输出到包目录 `results/`，不覆盖同名已有记录。
