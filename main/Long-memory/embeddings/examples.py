"""Local Embeddings 示例。

本文件仅演示 embeddings 插件自身的调用思路，
不再包含任何内置厂商 Provider 或 SDK 集成示例。
"""

from __future__ import annotations

import asyncio


async def main() -> None:
    print("Local Embeddings 示例已更新")
    print("- embeddings 插件可独立使用")
    print("- 远端 LLM 请在宿主应用中通过 LLMClient + 模型级配置接入")


if __name__ == "__main__":
    asyncio.run(main())
