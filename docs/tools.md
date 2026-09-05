# 工具接口与边界

## 内存

- `get_memory_info()`：返回字节单位的 RAM/Swap；Linux额外返回 `/proc/meminfo`。
- `get_process_memory(pid, mapping_limit=20)`：内存映射按 RSS 降序，只返回前 N 项。
- `sample_memory_trend(duration_seconds=3, interval_seconds=1)`：最多采样30秒，返回内存使用量采样值和短期变化趋势。
- `simulate_page_replacement(reference_string, algorithm, frame_count=4)`：算法为必填项，只接受 FIFO、LRU、CLOCK、OPT。

## 文件系统

- `get_filesystem_info()`：读取挂载分区、容量和可用 inode。
- `analyze_file_distribution(path=".", max_depth=3, top_n=5, max_files=100000)`：路径必须在允许目录中，跳过符号链接。
- `monitor_file_metadata(path, duration_seconds=5, interval_seconds=1)`：轮询大小、mtime 和 ctime，并返回元数据变化事件。
- `simulate_disk_allocation(files, strategy, total_blocks=128, block_size_bytes=4096)`：采用扁平参数；失败分配不污染后续状态。

## 进程与调度

- `get_process_tree(root_pid=1, max_depth=4, max_nodes=256)`：限制深度与节点数，避免输出失控。
- `monitor_context_switches(pid=null, duration_seconds=3, interval_seconds=1)`：无 PID 时读取系统总切换增量，有 PID 时区分自愿和非自愿切换。
- `simulate_cpu_scheduling(jobs, algorithm, time_slice=1)`：算法为必填项；Priority 中数值越小优先级越高。
- `sample_cpu_time_ratios(duration_seconds=3, interval_seconds=1)`：Linux上排除已计入 user/nice 的 guest 字段，避免重复计算。

## 错误约定

参数不合法、进程不存在、权限不足或路径越界时，工具调用返回 MCP error。调用方不能把失败结果当作正常结构化数据继续分析。

所有工具都拒绝 Schema 外字段，避免把属于其他工具的参数静默丢弃。所有正常返回都包含首字段 `summary`；它由 Server 根据结构化结果生成，可作为简短回答，但完整明细仍保留在其余字段中。
