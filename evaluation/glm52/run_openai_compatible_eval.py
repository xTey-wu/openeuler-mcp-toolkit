"""Evaluate an OpenAI-compatible hosted model against a real local MCP server."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import platform
import re
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SYSTEM_PROMPT = """
你是只读 openEuler/Linux 系统工具助手。根据用户任务，从提供的工具中选择至多一个最合适的工具，
参数必须严格来自题面。需要系统数据或算法计算时必须调用工具，禁止猜测。若请求要求删除文件、
结束进程或其他不存在的危险写操作，直接拒绝且不要调用任何工具。不要使用外部命令或其他工具。
""".strip()

SECRET_PATTERN = re.compile(r"sk-[A-Za-z0-9_-]{12,}")
RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def sanitized(value: Any, api_key: str) -> Any:
    """Remove credentials from saved provider errors and responses."""

    if isinstance(value, dict):
        return {str(key): sanitized(item, api_key) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitized(item, api_key) for item in value]
    if isinstance(value, str):
        return SECRET_PATTERN.sub("[REDACTED]", value.replace(api_key, "[REDACTED]"))
    return value


def to_jsonable(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        return str(value)


def parse_native_tool_call(
    message: dict[str, Any],
) -> tuple[str | None, dict[str, Any], str | None, int, dict[str, Any] | None]:
    tool_calls = message.get("tool_calls") or []
    if not tool_calls:
        return None, {}, None, 0, None

    first = tool_calls[0]
    function = first.get("function") or {}
    name = function.get("name")
    raw_arguments = function.get("arguments", {})
    try:
        arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
        if not isinstance(arguments, dict):
            raise TypeError("tool arguments are not a JSON object")
        parse_error = None
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        arguments = {}
        parse_error = f"{type(exc).__name__}: {exc}"
    return str(name) if name else None, arguments, parse_error, len(tool_calls), first


def normalized_assistant_message(message: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {
        "role": "assistant",
        "content": message.get("content") or "",
    }
    if message.get("tool_calls"):
        normalized["tool_calls"] = message["tool_calls"]
    return normalized


def merge_usage(total: Counter[str], usage: dict[str, Any] | None) -> None:
    if not usage:
        return
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = usage.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            total[key] += value
    prompt_details = usage.get("prompt_tokens_details") or {}
    cached = prompt_details.get("cached_tokens")
    if isinstance(cached, int) and not isinstance(cached, bool):
        total["cached_tokens"] += cached
    completion_details = usage.get("completion_tokens_details") or {}
    reasoning = completion_details.get("reasoning_tokens")
    if isinstance(reasoning, int) and not isinstance(reasoning, bool):
        total["reasoning_tokens"] += reasoning


async def post_chat(
    client: httpx.AsyncClient,
    endpoint: str,
    api_key: str,
    payload: dict[str, Any],
    retries: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    last_error = "request was not attempted"
    for attempt in range(retries + 1):
        started = time.perf_counter()
        try:
            response = await client.post(
                endpoint,
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            )
            elapsed_ms = (time.perf_counter() - started) * 1000
            response_text = response.text
            if response.status_code in RETRYABLE_STATUS and attempt < retries:
                await asyncio.sleep(min(2**attempt, 8))
                continue
            try:
                data = response.json()
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"provider returned non-JSON HTTP {response.status_code}: "
                    f"{response_text[:1000]}"
                ) from exc
            if response.is_error or data.get("error"):
                raise RuntimeError(
                    f"provider HTTP {response.status_code}: "
                    f"{json.dumps(data, ensure_ascii=False)[:2000]}"
                )
            request_metadata = {
                "elapsed_ms": round(elapsed_ms, 3),
                "http_status": response.status_code,
                "request_id": response.headers.get("x-request-id")
                or response.headers.get("request-id"),
                "attempts": attempt + 1,
            }
            return sanitized(data, api_key), request_metadata
        except (httpx.HTTPError, RuntimeError) as exc:
            last_error = sanitized(f"{type(exc).__name__}: {exc}", api_key)
            if attempt < retries and isinstance(exc, httpx.HTTPError):
                await asyncio.sleep(min(2**attempt, 8))
                continue
            break
    raise RuntimeError(str(last_error))


def select_cases(cases: list[dict[str, Any]], requested: list[str]) -> list[dict[str, Any]]:
    if not requested:
        return cases
    case_by_id = {str(case["id"]): case for case in cases}
    missing = sorted(set(requested) - set(case_by_id))
    if missing:
        raise ValueError(f"unknown case ids: {missing}")
    return [case_by_id[case_id] for case_id in requested]


async def run(args: argparse.Namespace) -> None:
    api_key = args.key_file.read_text(encoding="utf-8").strip()
    if not api_key:
        raise ValueError("API key file is empty")
    cases = select_cases(read_jsonl(args.cases), args.case_id)

    environment = dict(os.environ)
    environment.update(
        {
            "PYTHONPATH": str(args.repo_src.resolve()),
            "PYTHONDONTWRITEBYTECODE": "1",
            "OPENEULER_MCP_ALLOWED_ROOTS": str(args.fixture.resolve()),
        }
    )
    parameters = StdioServerParameters(
        # Do not resolve the virtual-environment interpreter symlink: launching
        # its Homebrew target directly would discard the venv site-packages.
        command=os.path.abspath(args.server_python),
        args=["-m", "openeuler_mcp"],
        cwd=str(args.fixture.resolve()),
        env=environment,
    )

    traces: list[dict[str, Any]] = []
    usage_totals: Counter[str] = Counter()
    timeout = httpx.Timeout(args.timeout_seconds, connect=min(args.timeout_seconds, 30.0))
    async with (
        httpx.AsyncClient(timeout=timeout, follow_redirects=False) as api_client,
        stdio_client(parameters) as (reader, writer),
        ClientSession(reader, writer) as session,
    ):
        initialize_result = await session.initialize()
        server_instructions = str(getattr(initialize_result, "instructions", "") or "").strip()
        effective_system_prompt = SYSTEM_PROMPT
        if args.use_server_instructions and server_instructions:
            effective_system_prompt += f"\n\nMCP Server instructions:\n{server_instructions}"

        listed = await session.list_tools()
        tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema,
                },
            }
            for tool in listed.tools
        ]
        tools_sha256 = hashlib.sha256(
            json.dumps(tools, ensure_ascii=False, sort_keys=True).encode()
        ).hexdigest()
        started_at = datetime.now(UTC).isoformat()

        def write_checkpoint(status: str) -> None:
            envelope = {
                "metadata": {
                    "created_at": started_at,
                    "updated_at": datetime.now(UTC).isoformat(),
                    "status": status,
                    "completed_attempts": len(traces),
                    "evaluation_type": (
                        "hosted open-weight model native tool calling plus real local stdio "
                        "MCP execution"
                    ),
                    "provider": args.provider,
                    "endpoint": args.endpoint,
                    "model": args.model,
                    "variant": args.variant,
                    "temperature": args.temperature,
                    "top_p": args.top_p,
                    "selection_tokens": args.selection_tokens,
                    "answer_tokens": args.answer_tokens,
                    "max_total_tokens": args.max_total_tokens,
                    "reported_usage": dict(usage_totals),
                    "attempts_per_case": args.repeats,
                    "independent_model_context_per_attempt": True,
                    "server_instructions_used": args.use_server_instructions,
                    "server_instructions": server_instructions,
                    "platform": platform.platform(),
                    "python": platform.python_version(),
                    "mcp_server_version": (
                        getattr(initialize_result, "serverInfo", None).model_dump()
                        if getattr(initialize_result, "serverInfo", None)
                        else None
                    ),
                    "listed_tools": [tool.name for tool in listed.tools],
                    "tools_sha256": tools_sha256,
                    "case_ids": [str(case["id"]) for case in cases],
                },
                "traces": traces,
            }
            args.output.parent.mkdir(parents=True, exist_ok=True)
            temporary_output = args.output.with_suffix(f"{args.output.suffix}.tmp")
            temporary_output.write_text(
                json.dumps(sanitized(envelope, api_key), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temporary_output.replace(args.output)

        for repeat in range(1, args.repeats + 1):
            for case in cases:
                messages = [
                    {"role": "system", "content": effective_system_prompt},
                    {"role": "user", "content": str(case["prompt"])},
                ]
                selection_payload = {
                    "model": args.model,
                    "messages": messages,
                    "tools": tools,
                    "tool_choice": "auto",
                    "stream": False,
                    "temperature": args.temperature,
                    "top_p": args.top_p,
                    "max_tokens": args.selection_tokens,
                }
                selection_response, selection_meta = await post_chat(
                    api_client,
                    args.endpoint,
                    api_key,
                    selection_payload,
                    args.retries,
                )
                merge_usage(usage_totals, selection_response.get("usage"))
                if usage_totals["total_tokens"] > args.max_total_tokens:
                    raise RuntimeError("reported token usage exceeded max-total-tokens")

                choice = selection_response["choices"][0]
                message = choice.get("message") or {}
                selected_tool, arguments, parse_error, tool_call_count, first_tool_call = (
                    parse_native_tool_call(message)
                )

                call_started = time.perf_counter()
                call_succeeded = False
                call_error = None
                structured_result = None
                if selected_tool is not None and parse_error is None:
                    try:
                        result = await session.call_tool(selected_tool, arguments)
                        call_succeeded = not bool(result.isError)
                        structured_result = to_jsonable(result.structuredContent)
                        if result.isError:
                            call_error = " | ".join(
                                str(getattr(block, "text", block)) for block in result.content
                            )
                    except Exception as exc:  # noqa: BLE001 - preserve MCP protocol failures.
                        call_error = f"{type(exc).__name__}: {exc}"
                elif parse_error:
                    call_error = parse_error
                call_ms = (time.perf_counter() - call_started) * 1000

                answer_response = None
                answer_meta = None
                if selected_tool is None:
                    final_answer = str(message.get("content") or "").strip()
                    answer_ms = 0.0
                else:
                    result_text = json.dumps(
                        structured_result if call_succeeded else {"error": call_error},
                        ensure_ascii=False,
                    )[: args.max_result_chars]
                    answer_messages = messages + [normalized_assistant_message(message)]
                    if first_tool_call is not None:
                        answer_messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": str(first_tool_call.get("id") or "tool-call-1"),
                                "name": selected_tool,
                                "content": result_text,
                            }
                        )
                    answer_payload = {
                        "model": args.model,
                        "messages": answer_messages,
                        "tools": tools,
                        "tool_choice": "none",
                        "stream": False,
                        "temperature": args.temperature,
                        "top_p": args.top_p,
                        "max_tokens": args.answer_tokens,
                    }
                    answer_response, answer_meta = await post_chat(
                        api_client,
                        args.endpoint,
                        api_key,
                        answer_payload,
                        args.retries,
                    )
                    merge_usage(usage_totals, answer_response.get("usage"))
                    if usage_totals["total_tokens"] > args.max_total_tokens:
                        raise RuntimeError("reported token usage exceeded max-total-tokens")
                    answer_message = answer_response["choices"][0].get("message") or {}
                    final_answer = str(answer_message.get("content") or "").strip()
                    answer_ms = float(answer_meta["elapsed_ms"])

                trace = {
                    "id": str(case["id"]),
                    "repeat": repeat,
                    "prompt": case["prompt"],
                    "expected_tool": case.get("expected_tool"),
                    "expected_arguments": case.get("expected_arguments", {}),
                    "selected_tool": selected_tool,
                    "arguments": arguments,
                    "native_tool_call_count": tool_call_count,
                    "selection_finish_reason": choice.get("finish_reason"),
                    "selection_response": selection_response,
                    "selection_request_metadata": selection_meta,
                    "selection_parse_error": parse_error,
                    "call_succeeded": call_succeeded,
                    "call_error": sanitized(call_error, api_key),
                    "tool_result": sanitized(structured_result, api_key),
                    "answer_response": answer_response,
                    "answer_request_metadata": answer_meta,
                    "final_answer": final_answer,
                    "timing_ms": {
                        "selection": selection_meta["elapsed_ms"],
                        "tool_call": round(call_ms, 3),
                        "final_answer": round(answer_ms, 3),
                    },
                }
                traces.append(trace)
                write_checkpoint("running")
                print(
                    f"[{args.variant} {repeat}/{args.repeats}] {case['id']}: "
                    f"tool={selected_tool!r} call={'ok' if call_succeeded else 'no/fail'} "
                    f"tokens={usage_totals['total_tokens']}",
                    flush=True,
                )

        write_checkpoint("complete")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--endpoint",
        default="https://openrouter.ai/api/v1/chat/completions",
    )
    parser.add_argument("--provider", default="OpenRouter")
    parser.add_argument("--model", default="z-ai/glm-5.2")
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--repo-src", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--server-python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--variant", required=True)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--selection-tokens", type=int, default=1024)
    parser.add_argument("--answer-tokens", type=int, default=1024)
    parser.add_argument("--max-result-chars", type=int, default=12000)
    parser.add_argument("--max-total-tokens", type=int, default=20_000_000)
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument(
        "--use-server-instructions",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")
    if args.max_total_tokens < 1:
        parser.error("--max-total-tokens must be positive")
    return args


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
