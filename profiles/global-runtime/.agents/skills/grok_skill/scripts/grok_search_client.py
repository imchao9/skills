#!/usr/bin/env python3
"""
最小化 Grok Search MCP 调用脚本。
固定通过 uvx 启动 grok-search（grok-with-tavily 分支），并通过 JSON-RPC 调用指定工具。
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

UVX_COMMAND = "uvx"
# 对齐项目推荐：固定使用 grok-with-tavily 分支。
UVX_ARGS = ["--from", "git+https://github.com/GuDaStudio/GrokSearch@grok-with-tavily", "grok-search"]


def load_dotenv() -> None:
    """加载项目根目录 .env，未配置项保留系统环境变量。"""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return

    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        return


class McpStdioClient:
    """最小 JSON-RPC over stdio 客户端。"""

    def __init__(self) -> None:
        self._next_id = 1
        self._proc = subprocess.Popen(
            [UVX_COMMAND, *UVX_ARGS],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
            env=os.environ.copy(),
        )
        self._initialize()

    def _send(self, payload: Dict[str, Any]) -> None:
        if not self._proc.stdin:
            raise RuntimeError("MCP 进程 stdin 不可用")
        self._proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self._proc.stdin.flush()

    def _read_message(self) -> Dict[str, Any]:
        if not self._proc.stdout:
            raise RuntimeError("MCP 进程 stdout 不可用")

        while True:
            line = self._proc.stdout.readline()
            if line == "":
                stderr = ""
                if self._proc.stderr:
                    stderr = self._proc.stderr.read().strip()
                raise RuntimeError(f"未收到 MCP 响应，stderr: {stderr}")
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                # 忽略非 JSON 行，继续读取。
                continue

    def _request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        req_id = self._next_id
        self._next_id += 1
        self._send({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params})

        while True:
            message = self._read_message()
            if message.get("id") != req_id:
                continue
            if "error" in message:
                raise RuntimeError(json.dumps(message["error"], ensure_ascii=False))
            return message.get("result", {})

    def _notify(self, method: str, params: Optional[Dict[str, Any]] = None) -> None:
        payload: Dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        self._send(payload)

    def _initialize(self) -> None:
        self._request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "grok-search-cli", "version": "1.0.0"},
            },
        )
        self._notify("notifications/initialized", {})

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("tools/call", {"name": tool_name, "arguments": arguments})

    def close(self) -> None:
        if self._proc.stdin:
            try:
                self._proc.stdin.close()
            except Exception:
                pass
        if self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="最小化 Grok Search MCP 调用脚本")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_call = subparsers.add_parser("call", help="调用指定 MCP 工具")
    p_call.add_argument("--tool", required=True, help="工具名，例如 web_search")
    p_call.add_argument("--args-json", default="{}", help="工具参数 JSON 字符串")

    return parser.parse_args()


def main() -> int:
    load_dotenv()
    args = parse_args()

    if not os.environ.get("GROK_API_URL"):
        print("错误：未设置 GROK_API_URL", file=sys.stderr)
        return 1
    if not os.environ.get("GROK_API_KEY"):
        print("错误：未设置 GROK_API_KEY", file=sys.stderr)
        return 1

    if args.command != "call":
        print("错误：不支持的命令", file=sys.stderr)
        return 2

    try:
        tool_args = json.loads(args.args_json)
    except json.JSONDecodeError as exc:
        print(f"错误：--args-json 不是合法 JSON: {exc}", file=sys.stderr)
        return 2

    if not isinstance(tool_args, dict):
        print("错误：--args-json 必须是 JSON 对象", file=sys.stderr)
        return 2

    client = None
    try:
        client = McpStdioClient()
        result = client.call_tool(args.tool, tool_args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"执行失败：{exc}", file=sys.stderr)
        return 1
    finally:
        if client:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
