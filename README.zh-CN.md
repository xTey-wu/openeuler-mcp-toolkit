[English](README.md) | **简体中文**

# openEuler MCP Toolkit

面向 openEuler/Linux 的只读系统观测与操作系统算法实验 MCP Server。它把内存、文件系统、进程与 CPU 信息封装为类型化工具，让支持 MCP 的大模型客户端能够调用可靠、可测试、结果规模受控的系统能力。

> 这个仓库是 MCP Server，不内置大模型。工具选择和自然语言解释由连接它的 MCP 客户端完成。

## 项目特点

- 12 个正式工具，覆盖内存、文件系统、进程和 CPU 调度。
- 实时系统观测与算法仿真采用独立模块和输出类型。
- Pydantic 输入输出模型；所有工具拒绝 Schema 外字段，避免错误参数被静默忽略。
- 文件工具受允许目录限制；不提供删除文件、结束进程等写操作。
- 每个结构化结果都以简短 `summary` 开头，便于客户端生成完整、可核对的回答。
- 长时间采样支持取消和进度通知。
- 纯算法测试、系统服务测试和真实 stdio MCP 协议测试。
- 20 条自然语言评测任务，不绑定模型厂商或 API Key。

## 工具列表

| 模块 | 工具 | 类型 | 说明 |
|---|---|---|---|
| 内存 | `get_memory_info` | 实时观测 | RAM、Swap 和 `/proc/meminfo` |
| 内存 | `get_process_memory` | 实时观测 | 进程 RSS、VMS 和前 N 项内存映射 |
| 内存 | `sample_memory_trend` | 实时观测 | 有界时间窗口内的内存趋势 |
| 内存 | `simulate_page_replacement` | 算法仿真 | FIFO、LRU、CLOCK、OPT |
| 文件系统 | `get_filesystem_info` | 实时观测 | 分区、容量和 inode |
| 文件系统 | `analyze_file_distribution` | 实时观测 | 受控目录内的文件分布 |
| 文件系统 | `monitor_file_metadata` | 实时观测 | 轮询文件大小和时间戳变化 |
| 文件系统 | `simulate_disk_allocation` | 算法仿真 | 连续、链式、索引分配 |
| 调度 | `get_process_tree` | 实时观测 | 有深度和节点上限的进程树 |
| 调度 | `monitor_context_switches` | 实时观测 | 系统或单进程上下文切换增量 |
| 调度 | `simulate_cpu_scheduling` | 算法仿真 | FCFS、SJF、RR、Priority |
| 调度 | `sample_cpu_time_ratios` | 实时观测 | CPU 各状态时间占比 |

## 快速开始

需要 Python 3.11 或 3.12。推荐在 openEuler/Linux 上运行；macOS 可运行算法和多数 psutil 工具，但没有 `/proc` 数据。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

启动 stdio Server：

```bash
openeuler-mcp
```

stdio 是协议通道，直接运行后没有交互式提示属于正常现象。可以运行协议示例：

```bash
python examples/smoke_client.py
```

使用 MCP Inspector：

```bash
mcp dev src/openeuler_mcp/server.py
```

通用客户端配置见 [`examples/mcp-config.json`](examples/mcp-config.json)。请把命令改为虚拟环境中 `openeuler-mcp` 的绝对路径，并替换允许访问的目录。

## 文件访问安全

文件分析默认只能访问 Server 的启动目录。通过系统路径分隔符配置多个允许目录：

```bash
export OPENEULER_MCP_ALLOWED_ROOTS="/var/log:/home/user/safe-data"
```

- 工具拒绝允许目录以外的路径。
- 扫描时跳过符号链接。
- 不要授权包含私钥、浏览器配置、Cookie 或其他敏感数据的目录。
- MCP 客户端可能将工具结果发送给所配置的模型服务，请同时检查客户端的数据策略。

## 三条演示链路

### 1. 系统内存检查

> 查看当前内存和交换区使用情况，并说明数据来源。

客户端应调用 `get_memory_info`，然后区分 psutil 数据与 Linux `/proc/meminfo` 数据。

### 2. 进程内存分析

> 分析 PID 1234 的内存占用，只列出 RSS 最大的 10 项映射。

客户端应调用 `get_process_memory(pid=1234, mapping_limit=10)`。进程不存在或无权限时，调用应明确失败而不是返回伪造结果。

### 3. 调度算法对比

> 对任务 A(到达0、运行4) 和 B(到达0、运行2) 使用时间片1的 RR 调度，解释等待时间。

客户端应调用 `simulate_cpu_scheduling`。正确结果中 A、B 的累计等待时间都为 2。

更多示例见 [`docs/demo.md`](docs/demo.md)。

## 测试

```bash
ruff check .
pytest --cov=openeuler_mcp --cov-report=term-missing
```

测试覆盖页面置换、RR 累计等待时间、磁盘分配回滚、路径边界、当前系统服务，以及 MCP Server 的 12 个工具注册、Schema 和结构化调用。

## 评测

[`evaluation/cases.jsonl`](evaluation/cases.jsonl) 包含 20 条任务，其中两条用于验证模型不会选择不存在的危险写工具。PID 题使用 `__CONTROLLED_PID__` 占位符；先创建一个受控测试进程，再生成本轮固定题目：

```bash
python evaluation/render_cases.py --controlled-pid 12345 --output /tmp/mcp-cases.jsonl
```

其中 `12345` 必须替换为当前仍在运行的受控进程真实 PID。每题使用独立模型上下文；建议固定模型、提示词、工具配置和参数后重复三次。把客户端轨迹整理为 [`result.example.jsonl`](evaluation/result.example.jsonl) 所示字段，确保每条都包含实际参数、原始工具返回、最终回答、总耗时和人工复核理由，再运行：

```bash
python evaluation/evaluate_results.py results.jsonl \
  --cases /tmp/mcp-cases.jsonl \
  --expected-repeats 3
```

评分器会检查漏题和重复记录，并把 18 个功能任务与 2 个安全拒绝任务分开报告。
参数正确性根据实际 `arguments` 与预设参数计算，不再直接信任输入结果中的自报标记。

### GLM-5.2 实测结果

[`evaluation/glm52/`](evaluation/glm52/) 保存 OpenRouter `z-ai/glm-5.2` 对当前项目的评测材料。60 次独立任务尝试的主要结果为：

- 工具选择准确率：54/54（100.00%）
- 必要参数及严格参数符合率：54/54（100.00%）
- 真实工具调用成功率：51/54（94.44%）
- 端到端任务完成率：48/54（88.89%）
- 危险操作正确拒绝率：6/6（100.00%）

完整条件、分子、分母和失败说明见[中文评测报告](evaluation/glm52/REPORT.zh-CN.md)。

## 文档

- [架构与数据流](docs/architecture.md)
- [工具接口与边界](docs/tools.md)
- [演示问题](docs/demo.md)
- [平台支持](docs/platform-support.md)
- [安全策略](SECURITY.md)

## 已知限制

- 仅提供本地 stdio transport，不包含远程 HTTP 和认证。
- 文件变化通过元数据轮询观察，快速发生并恢复的变化可能被漏掉。
- 进程和系统状态具有瞬时性，采集期间进程可能退出或权限可能变化。
- 磁盘分配和 CPU/页面调度仅计算模拟结果，不会修改真实操作系统状态。
- 算法工具要求显式给出算法名；磁盘分配使用扁平参数，减少模型构造嵌套对象时的错误。

## 当前接口约定

- `simulate_page_replacement` 和 `simulate_cpu_scheduling` 必须显式传入 `algorithm`。
- `simulate_disk_allocation` 使用 `files`、`strategy`、`total_blocks`、`block_size_bytes` 四个扁平参数。
- 所有工具拒绝 Schema 中未声明的额外参数；正常结果包含必填 `summary` 字段。
- 工具说明要求传入题面给出的数值限制，即使该参数有默认值。
- 进程树枚举会跳过无权访问的无关进程，避免单个受限进程导致整个查询失败。

## License

[MIT](LICENSE)
