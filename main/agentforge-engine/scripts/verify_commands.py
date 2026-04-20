#!/usr/bin/env python3
"""简单验证命令文件格式"""

from pathlib import Path

import yaml

commands_dir = Path(__file__).parent.parent / "data" / "commands"

print("=" * 60)
print("验证命令文件格式")
print("=" * 60)

errors = []
commands = []

for md_file in sorted(commands_dir.glob("*.md")):
    try:
        content = md_file.read_text(encoding="utf-8")

        # 检查是否有 frontmatter
        if not content.startswith("---"):
            errors.append(f"{md_file.name}: 缺少 YAML frontmatter")
            continue

        # 解析 frontmatter
        parts = content.split("---", 2)
        if len(parts) < 3:
            errors.append(f"{md_file.name}: frontmatter 格式错误")
            continue

        frontmatter_str = parts[1].strip()
        metadata = yaml.safe_load(frontmatter_str)

        # 检查必需字段
        if "name" not in metadata:
            errors.append(f"{md_file.name}: 缺少 'name' 字段")
            continue

        if "description" not in metadata:
            errors.append(f"{md_file.name}: 缺少 'description' 字段")
            continue

        commands.append({
            "file": md_file.name,
            "name": metadata["name"],
            "description": metadata["description"],
            "alias": metadata.get("alias", []),
            "category": metadata.get("category", "未分类"),
        })

    except Exception as e:
        errors.append(f"{md_file.name}: {e}")

# 显示结果
print(f"\n✓ 成功解析 {len(commands)} 个命令\n")

# 按类别分组
categories = {}
for cmd in commands:
    cat = cmd["category"]
    if cat not in categories:
        categories[cat] = []
    categories[cat].append(cmd)

# 显示命令列表
for category in sorted(categories.keys()):
    print(f"\n【{category.upper()}】")
    print("-" * 60)

    for cmd in sorted(categories[category], key=lambda c: c["name"]):
        alias_str = f" (别名: {', '.join(cmd['alias'])})" if cmd["alias"] else ""
        print(f"  /{cmd['name']}{alias_str}")
        print(f"    {cmd['description']}")

# 显示错误
if errors:
    print("\n" + "=" * 60)
    print("⚠️  错误")
    print("=" * 60)
    for error in errors:
        print(f"  {error}")
else:
    print("\n✓ 所有命令文件格式正确")

# 统计
print("\n" + "=" * 60)
print("统计")
print("=" * 60)
print(f"  总命令数: {len(commands)}")
print(f"  分类数: {len(categories)}")

total_aliases = sum(len(cmd["alias"]) for cmd in commands)
print(f"  总别名数: {total_aliases}")

print("\n" + "=" * 60)
print("验证完成！")
print("=" * 60)
