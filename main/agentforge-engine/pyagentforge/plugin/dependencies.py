"""
依赖解析器

解析和管理插件依赖关系
"""

import logging
from collections import defaultdict
from typing import Any

from pyagentforge.plugin.base import Plugin
from pyagentforge.plugin.registry import PluginRegistry

logger = logging.getLogger(__name__)


class CircularDependencyError(Exception):
    """循环依赖错误"""
    pass


class DependencyMissingError(Exception):
    """依赖缺失错误"""
    pass


class DependencyResolver:
    """依赖解析器"""

    def __init__(self, registry: PluginRegistry):
        self.registry = registry

    def resolve_load_order(self, plugin_ids: list[str]) -> list[str]:
        """
        解析插件加载顺序（拓扑排序）

        Args:
            plugin_ids: 需要加载的插件ID列表

        Returns:
            按依赖顺序排列的插件ID列表

        Raises:
            CircularDependencyError: 存在循环依赖
            DependencyMissingError: 缺少必需依赖
        """
        # 构建依赖图
        graph: dict[str, set[str]] = defaultdict(set)
        in_degree: dict[str, int] = defaultdict(int)

        # 初始化所有节点
        all_plugins = set(plugin_ids)
        for plugin_id in plugin_ids:
            in_degree[plugin_id] = 0

        # 构建边
        for plugin_id in plugin_ids:
            plugin = self.registry.get(plugin_id)
            if plugin is None:
                continue

            for dep_id in plugin.metadata.dependencies:
                if dep_id not in all_plugins:
                    raise DependencyMissingError(
                        f"Plugin {plugin_id} requires {dep_id} which is not in the load list"
                    )
                graph[dep_id].add(plugin_id)
                in_degree[plugin_id] += 1

        # 拓扑排序 (Kahn's algorithm)
        queue = [pid for pid in plugin_ids if in_degree[pid] == 0]
        result = []

        while queue:
            # 按优先级排序
            queue.sort(key=lambda x: self._get_priority(x), reverse=True)
            current = queue.pop(0)
            result.append(current)

            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(plugin_ids):
            # 检测循环依赖
            remaining = [p for p in plugin_ids if p not in result]
            raise CircularDependencyError(
                f"Circular dependency detected among: {remaining}"
            )

        return result

    def check_satisfaction(
        self,
        plugin: Plugin,
        check_optional: bool = False,
    ) -> tuple[bool, list[str]]:
        """
        检查插件依赖是否满足

        Args:
            plugin: 插件实例
            check_optional: 是否检查可选依赖

        Returns:
            (是否满足, 缺失的依赖列表)
        """
        missing = []

        # 检查必需依赖
        for dep_id in plugin.metadata.dependencies:
            if not self.registry.is_activated(dep_id):
                missing.append(dep_id)

        # 检查可选依赖
        if check_optional:
            for dep_id in plugin.metadata.optional_dependencies:
                if not self.registry.is_activated(dep_id):
                    missing.append(f"{dep_id} (optional)")

        return len(missing) == 0, missing

    def check_conflicts(self, plugin: Plugin) -> tuple[bool, list[str]]:
        """
        检查插件冲突

        Args:
            plugin: 插件实例

        Returns:
            (是否有冲突, 冲突的插件列表)
        """
        conflicts = []

        for conflict_id in plugin.metadata.conflicts:
            if self.registry.has_plugin(conflict_id):
                conflicts.append(conflict_id)

        return len(conflicts) > 0, conflicts

    def get_dependents(self, plugin_id: str) -> list[str]:
        """
        获取依赖于指定插件的所有插件

        Args:
            plugin_id: 插件ID

        Returns:
            依赖该插件的插件ID列表
        """
        dependents = []

        for plugin in self.registry.get_all():
            if plugin_id in plugin.metadata.dependencies:
                dependents.append(plugin.metadata.id)

        return dependents

    def _get_priority(self, plugin_id: str) -> int:
        """获取插件优先级"""
        plugin = self.registry.get(plugin_id)
        return plugin.metadata.priority if plugin else 0

    def build_dependency_tree(self, plugin_id: str) -> dict[str, Any]:
        """
        构建插件的依赖树

        Args:
            plugin_id: 插件ID

        Returns:
            依赖树结构
        """
        plugin = self.registry.get(plugin_id)
        if plugin is None:
            return {"id": plugin_id, "error": "not found"}

        tree = {
            "id": plugin_id,
            "name": plugin.metadata.name,
            "version": plugin.metadata.version,
            "dependencies": [],
            "optional_dependencies": [],
        }

        for dep_id in plugin.metadata.dependencies:
            tree["dependencies"].append(self.build_dependency_tree(dep_id))

        for dep_id in plugin.metadata.optional_dependencies:
            dep_tree = self.build_dependency_tree(dep_id)
            dep_tree["optional"] = True
            tree["optional_dependencies"].append(dep_tree)

        return tree
