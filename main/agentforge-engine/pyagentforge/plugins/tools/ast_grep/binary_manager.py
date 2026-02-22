"""
AST-Grep 二进制管理器

负责检测、安装和管理 ast-grep CLI 二进制文件
"""

import asyncio
import logging
import os
import platform
import shutil
from pathlib import Path
from typing import Optional

from pyagentforge.plugins.tools.ast_grep.constants import CLI_NAME, CLI_PACKAGE_NAME


class BinaryManager:
    """管理 ast-grep 二进制文件"""

    def __init__(
        self,
        logger: Optional[logging.Logger] = None,
        auto_install: bool = False,
    ):
        """
        初始化二进制管理器

        Args:
            logger: 日志记录器
            auto_install: 是否自动安装
        """
        self.logger = logger or logging.getLogger(__name__)
        self.auto_install = auto_install
        self._binary_path: Optional[str] = None
        self._checked = False
        self._version: Optional[str] = None

    async def check_availability(self) -> bool:
        """
        检查 ast-grep 是否可用

        Returns:
            bool: 是否可用
        """
        if self._checked:
            return self._binary_path is not None

        self._checked = True

        # 1. 检查 PATH
        path = shutil.which(CLI_NAME)
        if path:
            self._binary_path = path
            self.logger.debug(f"Found {CLI_NAME} in PATH: {path}")
            return True

        # 2. 检查常见安装位置
        common_paths = self._get_common_paths()
        for p in common_paths:
            if Path(p).exists():
                self._binary_path = p
                self.logger.debug(f"Found {CLI_NAME} at: {p}")
                return True

        # 3. 尝试自动安装
        if self.auto_install:
            self.logger.info(f"{CLI_NAME} not found, attempting auto-install...")
            return await self._auto_install()

        self.logger.warning(
            f"{CLI_NAME} binary not found. "
            f"Install with: pip install {CLI_PACKAGE_NAME} or cargo install ast-grep"
        )
        return False

    async def is_available(self) -> bool:
        """检查可用性（异步版本）"""
        return await self.check_availability()

    def get_binary_path(self) -> Optional[str]:
        """获取二进制路径"""
        return self._binary_path

    async def get_version(self) -> Optional[str]:
        """
        获取版本号

        Returns:
            str or None: 版本号
        """
        if self._version:
            return self._version

        if not await self.is_available():
            return None

        try:
            proc = await asyncio.create_subprocess_exec(
                self._binary_path,
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            self._version = stdout.decode().strip()
            return self._version
        except Exception as e:
            self.logger.debug(f"Failed to get version: {e}")
            return None

    def _get_common_paths(self) -> list[str]:
        """获取常见安装路径"""
        system = platform.system()
        home = Path.home()

        if system == "Windows":
            return [
                str(home / ".cargo" / "bin" / f"{CLI_NAME}.exe"),
                str(home / "AppData" / "Local" / "ast-grep" / f"{CLI_NAME}.exe"),
                str(Path(os.environ.get("LOCALAPPDATA", "")) / "ast-grep" / f"{CLI_NAME}.exe"),
            ]
        else:  # Linux / macOS
            return [
                str(home / ".cargo" / "bin" / CLI_NAME),
                "/usr/local/bin/sg",
                "/usr/bin/sg",
                str(home / ".local" / "bin" / CLI_NAME),
            ]

    async def _auto_install(self) -> bool:
        """
        尝试自动安装

        Returns:
            bool: 是否安装成功
        """
        self.logger.info(f"Attempting to install {CLI_PACKAGE_NAME}...")

        # 尝试 pip 安装
        try:
            proc = await asyncio.create_subprocess_exec(
                "pip",
                "install",
                CLI_PACKAGE_NAME,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)

            if proc.returncode == 0:
                # 重新检查
                path = shutil.which(CLI_NAME)
                if path:
                    self._binary_path = path
                    self.logger.info(f"Successfully installed {CLI_PACKAGE_NAME} at {path}")
                    return True
            else:
                self.logger.warning(
                    f"pip install failed: {stderr.decode()}"
                )
        except asyncio.TimeoutError:
            self.logger.warning("pip install timed out")
        except FileNotFoundError:
            self.logger.warning("pip not found")
        except Exception as e:
            self.logger.warning(f"Auto-install failed: {e}")

        return False

    def get_install_hint(self) -> str:
        """返回安装提示"""
        return (
            f"ast-grep ({CLI_NAME}) 未安装。\n\n"
            f"安装方式:\n"
            f"  pip install {CLI_PACKAGE_NAME}\n"
            f"  cargo install ast-grep --locked\n"
            f"  brew install ast-grep\n\n"
            f"安装后请确保 {CLI_NAME} 在 PATH 中"
        )
