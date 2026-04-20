"""
AST-Grep CLI 封装

负责执行 ast-grep 命令并解析结果
"""

import asyncio
import json
import logging

from pyagentforge.plugins.tools.ast_grep.constants import (
    CLI_LANGUAGES,
    DEFAULT_MAX_MATCHES,
    DEFAULT_MAX_OUTPUT_BYTES,
    DEFAULT_TIMEOUT_MS,
)
from pyagentforge.plugins.tools.ast_grep.types import SgMatch, SgResult


async def run_sg(
    pattern: str,
    lang: str,
    binary_path: str,
    paths: list[str] | None = None,
    globs: list[str] | None = None,
    rewrite: str | None = None,
    context: int = 0,
    update_all: bool = False,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    max_matches: int = DEFAULT_MAX_MATCHES,
    logger: logging.Logger | None = None,
) -> SgResult:
    """
    执行 ast-grep 命令

    Args:
        pattern: AST 模式
        lang: 语言
        binary_path: 二进制文件路径
        paths: 搜索路径
        globs: 文件过滤
        rewrite: 替换模式
        context: 上下文行数
        update_all: 是否实际修改文件
        timeout_ms: 超时时间 (毫秒)
        max_matches: 最大匹配数
        logger: 日志记录器

    Returns:
        SgResult: 搜索/替换结果
    """
    logger = logger or logging.getLogger(__name__)

    # 验证语言
    if lang not in CLI_LANGUAGES:
        return SgResult(
            matches=[],
            total_matches=0,
            error=f"Unsupported language: {lang}. Supported: {', '.join(sorted(CLI_LANGUAGES))}",
        )

    # 构建命令参数
    args = [
        "run",
        "-p", pattern,
        "--lang", lang,
        "--json=compact",
    ]

    # 替换模式
    if rewrite:
        args.extend(["-r", rewrite])
        if update_all:
            args.append("--update-all")

    # 上下文
    if context > 0:
        args.extend(["-C", str(context)])

    # 文件过滤
    if globs:
        for g in globs:
            args.extend(["--globs", g])

    # 搜索路径
    search_paths = paths if paths else ["."]
    args.extend(search_paths)

    logger.debug(f"Running: {binary_path} {' '.join(args)}")

    try:
        # 执行命令
        proc = await asyncio.create_subprocess_exec(
            binary_path,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout_ms / 1000,
        )

        stdout_str = stdout.decode("utf-8", errors="replace")
        stderr_str = stderr.decode("utf-8", errors="replace")

        if proc.returncode != 0:
            # 非零退出码可能只是没有匹配
            if "no match" in stderr_str.lower() or not stdout_str.strip():
                return SgResult(matches=[], total_matches=0)
            return SgResult(
                matches=[],
                total_matches=0,
                error=stderr_str or f"Exit code: {proc.returncode}",
            )

        # 检查输出大小
        if len(stdout_str) > DEFAULT_MAX_OUTPUT_BYTES:
            return SgResult(
                matches=[],
                total_matches=0,
                truncated=True,
                truncated_reason="output_too_large",
                error=f"Output too large ({len(stdout_str)} bytes)",
            )

        # 解析 JSON 输出
        return parse_sg_output(stdout_str, max_matches)

    except TimeoutError:
        logger.warning(f"Command timed out after {timeout_ms}ms")
        return SgResult(
            matches=[],
            total_matches=0,
            truncated=True,
            truncated_reason="timeout",
            error=f"Command timed out after {timeout_ms}ms",
        )
    except FileNotFoundError:
        return SgResult(
            matches=[],
            total_matches=0,
            error=f"Binary not found: {binary_path}",
        )
    except json.JSONDecodeError as e:
        logger.debug(f"JSON decode error: {e}")
        return SgResult(
            matches=[],
            total_matches=0,
            error=f"Failed to parse output: {e}",
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return SgResult(
            matches=[],
            total_matches=0,
            error=str(e),
        )


def parse_sg_output(output: str, max_matches: int = DEFAULT_MAX_MATCHES) -> SgResult:
    """
    解析 ast-grep JSON 输出

    Args:
        output: JSON 字符串
        max_matches: 最大匹配数

    Returns:
        SgResult: 解析后的结果
    """
    output = output.strip()
    if not output:
        return SgResult(matches=[], total_matches=0)

    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return SgResult(matches=[], total_matches=0, error="Invalid JSON output")

    if not isinstance(data, list):
        data = [data]

    matches = []
    truncated = False
    truncated_reason = None

    for item in data:
        if len(matches) >= max_matches:
            truncated = True
            truncated_reason = "max_matches"
            break

        # 提取范围信息
        range_info = item.get("range", {})
        start_info = range_info.get("start", {})
        end_info = range_info.get("end", {})

        match = SgMatch(
            text=item.get("text", ""),
            file=item.get("file", ""),
            line=start_info.get("line", 0),
            column=start_info.get("column", 0),
            range_start_line=start_info.get("line", 0),
            range_end_line=end_info.get("line", 0),
            replacement=item.get("replacement"),
        )
        matches.append(match)

    return SgResult(
        matches=matches,
        total_matches=len(data),
        truncated=truncated,
        truncated_reason=truncated_reason,
    )
