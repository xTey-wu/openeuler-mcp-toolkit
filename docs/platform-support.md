# 平台支持

项目以 openEuler/Linux 为主要运行平台，依赖 Python 3.11 或 3.12。持续集成在 Ubuntu 上运行静态检查、单元测试和 MCP stdio 协议测试。

## Linux 与 openEuler

- `get_memory_info` 在 `/proc/meminfo` 可用时返回其中的内存字段。
- 进程内存、进程树和上下文切换信息受内核接口及当前用户权限限制。
- 文件系统容量通过 psutil 获取，inode 信息通过 `statvfs` 获取。
- 文件分析遵循 `OPENEULER_MCP_ALLOWED_ROOTS`，并跳过符号链接。

## macOS

页面置换、磁盘分配和 CPU 调度算法可直接运行。基于 psutil 的系统工具按平台能力返回数据；`/proc/meminfo` 不可用，部分进程信息可能受到系统权限限制。

## 验证命令

```bash
python -m pip install -e ".[dev]"
ruff check .
pytest --cov=openeuler_mcp --cov-report=term-missing
python examples/smoke_client.py
```
