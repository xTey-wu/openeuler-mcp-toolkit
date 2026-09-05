# GLM-5.2 MCP 评测材料

本目录保存 OpenRouter `z-ai/glm-5.2` 对当前 openEuler MCP Toolkit 的评测材料。

## 文件说明

- `REPORT.zh-CN.md`：完整中文报告、指标、失败原因、token 与费用。
- `cases.jsonl`：本轮实际使用的 20 道固定题目。
- `scored_results.json`：60 次任务的确定性评分及逐题汇总。
- `manual_review_decisions.jsonl`：60 条脱敏人工复核结论。
- `run_openai_compatible_eval.py`：OpenAI 兼容接口的原生工具调用评测器。

## 隐私说明

公开仓库不包含 API Key，也不包含带有本机挂载点、用户名、请求 ID 和完整工具返回的原始 trace。这里保留固定题目、聚合评分和逐条复核结论，以便核对报告中的分子和分母。

## 复现提示

评测器只从 `--key-file` 指定的文件读取 API Key，不应把密钥写入代码或结果文件。PID 题需要为每次运行创建仍存活的受控进程并重新生成题目，不能直接复用本目录记录的 PID。
