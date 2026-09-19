**English** | [简体中文](README.zh-CN.md)

# openEuler MCP Toolkit

A read-only MCP server for openEuler/Linux system observability and operating-system algorithm experiments. It exposes memory, file-system, process, and CPU information as typed tools, allowing MCP-compatible language-model clients to call reliable, testable system capabilities with bounded output sizes.

> This repository provides an MCP server and does not include a language model. Tool selection and natural-language explanations are handled by the connected MCP client.

## Highlights

- 12 production tools covering memory, file systems, processes, and CPU scheduling.
- Separate modules and output types for live system observation and algorithm simulation.
- Pydantic input and output models; every tool rejects fields outside its schema so invalid arguments are not silently ignored.
- File tools are restricted to allowed directories; destructive operations such as deleting files or terminating processes are not provided.
- Every structured result begins with a concise `summary`, helping clients produce complete, verifiable answers.
- Long-running sampling supports cancellation and progress notifications.
- Pure algorithm tests, system-service tests, and real stdio MCP protocol tests.
- 20 natural-language evaluation tasks with no dependency on a specific model provider or API key.

## Tool Catalog

| Area | Tool | Type | Description |
|---|---|---|---|
| Memory | `get_memory_info` | Live observation | RAM, swap, and `/proc/meminfo` |
| Memory | `get_process_memory` | Live observation | Process RSS, VMS, and the top N memory mappings |
| Memory | `sample_memory_trend` | Live observation | Memory trends over a bounded time window |
| Memory | `simulate_page_replacement` | Algorithm simulation | FIFO, LRU, CLOCK, and OPT |
| File system | `get_filesystem_info` | Live observation | Partitions, capacity, and inodes |
| File system | `analyze_file_distribution` | Live observation | File distribution within controlled directories |
| File system | `monitor_file_metadata` | Live observation | Polling changes in file size and timestamps |
| File system | `simulate_disk_allocation` | Algorithm simulation | Contiguous, linked, and indexed allocation |
| Scheduling | `get_process_tree` | Live observation | Process tree with depth and node limits |
| Scheduling | `monitor_context_switches` | Live observation | System-wide or per-process context-switch deltas |
| Scheduling | `simulate_cpu_scheduling` | Algorithm simulation | FCFS, SJF, RR, and Priority |
| Scheduling | `sample_cpu_time_ratios` | Live observation | Time ratios across CPU states |

## Quick Start

Python 3.11 or 3.12 is required. openEuler/Linux is recommended. macOS supports the algorithm tools and most psutil-based tools, but does not provide `/proc` data.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Start the stdio server:

```bash
openeuler-mcp
```

stdio is the protocol transport, so the absence of an interactive prompt after launch is expected. To run the protocol example:

```bash
python examples/smoke_client.py
```

Use MCP Inspector:

```bash
mcp dev src/openeuler_mcp/server.py
```

A generic client configuration is available at [`examples/mcp-config.json`](examples/mcp-config.json). Replace the command with the absolute path to `openeuler-mcp` in your virtual environment and update the allowed directories.

## File-Access Safety

By default, file analysis is limited to the server's launch directory. Configure multiple allowed directories with the operating system's path separator:

```bash
export OPENEULER_MCP_ALLOWED_ROOTS="/var/log:/home/user/safe-data"
```

- Tools reject paths outside the allowed directories.
- Symbolic links are skipped during scans.
- Do not authorize directories containing private keys, browser profiles, cookies, or other sensitive data.
- An MCP client may send tool results to its configured model service; review the client's data policy as well.

## Three Demonstration Workflows

### 1. Inspect system memory

> Show the current memory and swap usage, and explain the source of each value.

The client should call `get_memory_info` and distinguish psutil data from Linux `/proc/meminfo` data.

### 2. Analyze process memory

> Analyze the memory usage of PID 1234 and list only the 10 mappings with the largest RSS values.

The client should call `get_process_memory(pid=1234, mapping_limit=10)`. If the process does not exist or access is denied, the call should fail explicitly instead of returning fabricated results.

### 3. Compare scheduling behavior

> Schedule task A (arrival 0, burst 4) and task B (arrival 0, burst 2) with RR and a quantum of 1, then explain the waiting times.

The client should call `simulate_cpu_scheduling`. In the correct result, the accumulated waiting time is 2 for both A and B.

More examples are available in [`docs/demo.md`](docs/demo.md).

## Testing

```bash
ruff check .
pytest --cov=openeuler_mcp --cov-report=term-missing
```

Tests cover page replacement, cumulative waiting time under RR, disk-allocation rollback, path boundaries, live system services, and the registration, schemas, and structured invocation of all 12 MCP server tools.

## Evaluation

[`evaluation/cases.jsonl`](evaluation/cases.jsonl) contains 20 tasks, including two that verify the model does not select nonexistent destructive tools. PID tasks use the `__CONTROLLED_PID__` placeholder. First create a controlled test process, then render a fixed case set for the current run:

```bash
python evaluation/render_cases.py --controlled-pid 12345 --output /tmp/mcp-cases.jsonl
```

Replace `12345` with the actual PID of a controlled process that is still running. Each task should use an isolated model context. Fix the model, prompts, tool configuration, and parameters, then repeat the suite three times. Format client traces according to [`result.example.jsonl`](evaluation/result.example.jsonl), ensuring that every record contains the actual arguments, raw tool result, final answer, total latency, and a manual-review rationale. Then run:

```bash
python evaluation/evaluate_results.py results.jsonl \
  --cases /tmp/mcp-cases.jsonl \
  --expected-repeats 3
```

The scorer checks for missing and duplicate records and reports the 18 functional tasks separately from the two safety-refusal tasks. Parameter correctness is computed from the actual `arguments` and expected values rather than trusting self-reported flags in the input results.

### GLM-5.2 Evaluation Results

[`evaluation/glm52/`](evaluation/glm52/) contains the evaluation artifacts for OpenRouter's `z-ai/glm-5.2` on the current project. The main results across 60 isolated task attempts are:

- Tool-selection accuracy: 54/54 (100.00%)
- Required-parameter and strict-parameter compliance: 54/54 (100.00%)
- Successful real tool calls: 51/54 (94.44%)
- End-to-end task completion: 48/54 (88.89%)
- Correct rejection of dangerous operations: 6/6 (100.00%)

See the [Chinese evaluation report](evaluation/glm52/REPORT.zh-CN.md) for the full conditions, numerators, denominators, and failure analysis.

## Documentation

- [Architecture and data flow](docs/architecture.md)
- [Tool interfaces and boundaries](docs/tools.md)
- [Demonstration questions](docs/demo.md)
- [Platform support](docs/platform-support.md)
- [Security policy](SECURITY.md)

## Known Limitations

- Only local stdio transport is supported; remote HTTP transport and authentication are not included.
- File changes are observed through metadata polling, so rapid changes that are reversed between polls may be missed.
- Process and system state is transient; processes may exit or permissions may change during collection.
- Disk allocation and CPU/page scheduling produce simulations only and do not modify real operating-system state.
- Algorithm tools require an explicit algorithm name; disk allocation uses flat parameters to reduce errors when a model constructs nested objects.

## Current Interface Contract

- `simulate_page_replacement` and `simulate_cpu_scheduling` require an explicit `algorithm` argument.
- `simulate_disk_allocation` uses four flat arguments: `files`, `strategy`, `total_blocks`, and `block_size_bytes`.
- Every tool rejects extra parameters not declared in its schema; successful results include a required `summary` field.
- Tool descriptions instruct clients to pass numeric limits stated in the request even when a parameter has a default value.
- Process-tree enumeration skips unrelated inaccessible processes so that one restricted process does not fail the entire query.

## License

[MIT](LICENSE)
