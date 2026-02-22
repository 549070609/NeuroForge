"""
思维链工具

提供 Agent 操作思维链的工具。
"""

from typing import Any

from pyagentforge.tools.base import BaseTool
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class LoadCoTTool(BaseTool):
    """加载思维链工具"""

    name = "cot_load"
    description = "Load a chain of thought template for the current task type"
    parameters_schema = {
        "type": "object",
        "properties": {
            "task_type": {
                "type": "string",
                "description": "Task type (e.g., debugging, code_review, problem_solving, research)",
            },
            "custom_path": {
                "type": "string",
                "description": "Optional custom path to load a specific CoT file",
            },
            "prefer_agent": {
                "type": "boolean",
                "description": "Whether to prefer agent-generated CoT over templates (default: true)",
                "default": True,
            },
        },
        "required": ["task_type"],
    }
    timeout = 10
    risk_level = "low"

    async def execute(
        self,
        task_type: str,
        custom_path: str | None = None,
        prefer_agent: bool = True,
        **kwargs: Any,
    ) -> str:
        """执行工具"""
        cot_manager = kwargs.get("cot_manager")

        if not cot_manager:
            return "Error: Chain of thought manager not available"

        # 加载思维链
        cot = cot_manager.load_cot(
            task_type=task_type,
            prefer_agent=prefer_agent,
        )

        if not cot:
            available = cot_manager.list_templates()
            return f"Error: No CoT found for '{task_type}'. Available templates: {', '.join(available) or 'none'}"

        # 生成指导提示
        guidance = cot_manager.generate_system_prompt_extension()

        result = f"Loaded Chain of Thought: {cot.name}\n"
        result += f"Description: {cot.description}\n"
        result += f"Phases: {len(cot.phases)}\n"
        result += f"Source: {cot.source}\n\n"
        result += "=== Guidance ===\n"
        result += guidance

        return result


class UpdateCoTTool(BaseTool):
    """更新思维链工具"""

    name = "cot_update"
    description = "Update the current chain of thought with lessons learned from execution"
    parameters_schema = {
        "type": "object",
        "properties": {
            "phase": {
                "type": "string",
                "description": "Phase name to update (or 'all' for all phases)",
            },
            "lessons_learned": {
                "type": "string",
                "description": "Lessons learned or improvements to add",
            },
            "save_as_template": {
                "type": "boolean",
                "description": "Whether to save as a reusable template (default: false)",
                "default": False,
            },
        },
        "required": ["phase", "lessons_learned"],
    }
    timeout = 10
    risk_level = "low"

    async def execute(
        self,
        phase: str,
        lessons_learned: str,
        save_as_template: bool = False,
        **kwargs: Any,
    ) -> str:
        """执行工具"""
        cot_manager = kwargs.get("cot_manager")

        if not cot_manager:
            return "Error: Chain of thought manager not available"

        current_cot = cot_manager.get_current_cot()
        if not current_cot:
            return "Error: No chain of thought currently loaded"

        # 记录反思
        if phase == "all":
            # 更新整个思维链的反思
            cot_manager.update_cot_from_reflection(lessons_learned, True)
        else:
            # 更新特定阶段
            target_phase = current_cot.get_phase(phase)
            if target_phase:
                # 在阶段提示中添加经验教训
                target_phase.prompt += f"\n\n[经验教训]: {lessons_learned}"
                logger.info(f"Updated phase '{phase}' with lessons learned")
            else:
                return f"Error: Phase '{phase}' not found in current CoT"

        # 如果需要保存为模板
        if save_as_template:
            current_cot.source = "agent"
            cot_manager.save_agent_cot(current_cot)

        result = f"Updated chain of thought '{current_cot.name}'\n"
        result += f"Phase: {phase}\n"
        result += f"Lessons: {lessons_learned[:100]}...\n"

        if save_as_template:
            result += "Saved as reusable template."

        return result


class ValidatePlanTool(BaseTool):
    """验证计划工具"""

    name = "cot_validate_plan"
    description = "Validate an execution plan against the current chain of thought constraints"
    parameters_schema = {
        "type": "object",
        "properties": {
            "plan_steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string"},
                        "action": {"type": "string"},
                        "validation": {"type": "string"},
                    },
                },
                "description": "List of plan steps to validate",
            },
            "fail_on_violation": {
                "type": "boolean",
                "description": "Whether to fail on hard constraint violations (default: true)",
                "default": True,
            },
        },
        "required": ["plan_steps"],
    }
    timeout = 10
    risk_level = "low"

    async def execute(
        self,
        plan_steps: list[dict[str, Any]],
        fail_on_violation: bool = True,
        **kwargs: Any,
    ) -> str:
        """执行工具"""
        cot_manager = kwargs.get("cot_manager")

        if not cot_manager:
            return "Error: Chain of thought manager not available"

        current_cot = cot_manager.get_current_cot()
        if not current_cot:
            return "Warning: No chain of thought loaded, skipping validation"

        # 验证计划
        is_valid, violations = cot_manager.validate_plan_against_cot(plan_steps)

        # 记录计划到执行轨迹
        cot_manager.record_plan(plan_steps)

        # 记录违反
        for v in violations:
            cot_manager.record_violation(v)

        result = f"Plan Validation Result: {'PASSED' if is_valid else 'FAILED'}\n"
        result += f"Steps validated: {len(plan_steps)}\n"
        result += f"Violations found: {len(violations)}\n\n"

        if violations:
            result += "=== Violations ===\n"
            for v in violations:
                type_icon = {
                    "hard": "❗",
                    "soft": "⚠️",
                    "format": "📝",
                }.get(v.constraint_type.value, "?")

                result += f"{type_icon} [{v.phase_name}] {v.constraint_description}\n"
                result += f"   Details: {v.violation_details}\n\n"

            if not is_valid and fail_on_violation:
                result += "\n⚠️ Plan blocked due to hard constraint violations."
                result += "\nPlease revise your plan to address these issues."
        else:
            result += "✅ All constraints satisfied."

        return result


class GetCoTInfoTool(BaseTool):
    """获取思维链信息工具"""

    name = "cot_info"
    description = "Get information about the current or available chain of thought templates"
    parameters_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["current", "list", "details"],
                "description": "Action: 'current' for loaded CoT, 'list' for all templates, 'details' for specific template",
                "default": "current",
            },
            "template_name": {
                "type": "string",
                "description": "Template name (required for 'details' action)",
            },
        },
        "required": ["action"],
    }
    timeout = 10
    risk_level = "low"

    async def execute(
        self,
        action: str,
        template_name: str | None = None,
        **kwargs: Any,
    ) -> str:
        """执行工具"""
        cot_manager = kwargs.get("cot_manager")

        if not cot_manager:
            return "Error: Chain of thought manager not available"

        if action == "current":
            current_cot = cot_manager.get_current_cot()
            if not current_cot:
                return "No chain of thought currently loaded."

            result = f"Current Chain of Thought: {current_cot.name}\n"
            result += f"Description: {current_cot.description}\n"
            result += f"Version: {current_cot.version}\n"
            result += f"Source: {current_cot.source}\n"
            result += f"Execution count: {current_cot.execution_count}\n"
            result += f"Success rate: {current_cot.success_rate:.1%}\n\n"
            result += f"Phases ({len(current_cot.phases)}):\n"

            for phase in current_cot.get_ordered_phases():
                required = "✓" if phase.is_required else "○"
                result += f"  {required} {phase.name} ({len(phase.constraints)} constraints)\n"

            return result

        elif action == "list":
            templates = cot_manager.list_templates()

            if not templates:
                return "No chain of thought templates available."

            result = f"Available Templates ({len(templates)}):\n"
            for name in sorted(templates):
                template = cot_manager.get_template(name)
                if template:
                    result += f"  • {name}: {template.description[:50]}...\n"

            return result

        elif action == "details":
            if not template_name:
                return "Error: template_name is required for 'details' action"

            template = cot_manager.get_template(template_name)
            if not template:
                return f"Error: Template '{template_name}' not found"

            result = f"Template: {template.name}\n"
            result += f"Description: {template.description}\n"
            result += f"Version: {template.version}\n"
            result += f"Author: {template.author}\n"
            result += f"Tags: {', '.join(template.tags) or 'none'}\n\n"

            result += "Phases:\n"
            for i, phase in enumerate(template.get_ordered_phases(), 1):
                result += f"\n{i}. {phase.name}"
                result += " (required)" if phase.is_required else " (optional)"
                result += f"\n   {phase.prompt[:100]}...\n"

                if phase.constraints:
                    result += "   Constraints:\n"
                    for c in phase.constraints:
                        result += f"   - [{c.constraint_type.value}] {c.description}\n"

            return result

        return f"Unknown action: {action}"


class CreateCoTTool(BaseTool):
    """创建自定义思维链工具"""

    name = "cot_create"
    description = "Create a new custom chain of thought for a specific task type"
    parameters_schema = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Name for the new CoT",
            },
            "description": {
                "type": "string",
                "description": "Description of when to use this CoT",
            },
            "phases": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "prompt": {"type": "string"},
                        "order": {"type": "integer"},
                        "is_required": {"type": "boolean"},
                        "constraints": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "description": {"type": "string"},
                                    "type": {"type": "string", "enum": ["hard", "soft", "format"]},
                                },
                            },
                        },
                    },
                },
                "description": "List of phases in the CoT",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Tags for categorization",
            },
        },
        "required": ["name", "description", "phases"],
    }
    timeout = 15
    risk_level = "medium"

    async def execute(
        self,
        name: str,
        description: str,
        phases: list[dict[str, Any]],
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> str:
        """执行工具"""
        cot_manager = kwargs.get("cot_manager")

        if not cot_manager:
            return "Error: Chain of thought manager not available"

        # 创建思维链
        cot = cot_manager.create_cot_from_template(
            name=name,
            description=description,
            phases=phases,
            source="agent",
        )

        if tags:
            cot.tags = tags

        # 保存
        cot_manager.save_agent_cot(cot)

        result = f"Created chain of thought: {name}\n"
        result += f"Description: {description}\n"
        result += f"Phases: {len(phases)}\n"
        result += f"Tags: {', '.join(tags) or 'none'}\n\n"
        result += "CoT saved and ready to use. Load it with cot_load tool."

        return result


class AnalyzeCoTTool(BaseTool):
    """分析思维链工具 - Phase 3"""

    name = "cot_analyze"
    description = "Analyze execution trace and generate improvement suggestions for the current chain of thought"
    parameters_schema = {
        "type": "object",
        "properties": {
            "analysis_type": {
                "type": "string",
                "enum": ["auto", "deep", "quick"],
                "description": "Type of analysis: auto (apply improvements), deep (detailed), quick (summary)",
                "default": "auto",
            },
        },
        "required": [],
    }
    timeout = 15
    risk_level = "low"

    async def execute(
        self,
        analysis_type: str = "auto",
        **kwargs: Any,
    ) -> str:
        """执行工具"""
        cot_manager = kwargs.get("cot_manager")

        if not cot_manager:
            return "Error: Chain of thought manager not available"

        # 执行分析
        analysis = cot_manager.analyze_and_update_from_trace(analysis_type)

        if "error" in analysis:
            return f"Error: {analysis['error']}"

        # 格式化输出
        result = "=== Chain of Thought Analysis ===\n\n"
        result += f"CoT: {analysis['cot_name']}\n"
        result += f"Execution Success: {'✓ Yes' if analysis['success'] else '✗ No'}\n"
        result += f"Phases Executed: {analysis['phases_executed']}\n"
        result += f"Total Violations: {analysis['violations_count']}\n"
        result += f"  - Hard: {analysis['hard_violations']}\n"
        result += f"  - Soft: {analysis['soft_violations']}\n\n"

        if analysis["phase_insights"]:
            result += "=== Phase Insights ===\n"
            for phase_name, insight in analysis["phase_insights"].items():
                status = "⚠️ Issues" if insight["had_violations"] else "✓ Smooth"
                result += f"\n{phase_name}: {status}\n"

                if insight.get("suggestions"):
                    for suggestion in insight["suggestions"]:
                        result += f"  - {suggestion}\n"

        if analysis["suggestions"]:
            result += "\n=== Improvement Suggestions ===\n"
            for i, suggestion in enumerate(analysis["suggestions"], 1):
                result += f"{i}. {suggestion}\n"

        if analysis_type == "auto":
            result += "\n✓ Auto-update applied based on analysis.\n"

        return result


class ImproveCoTTool(BaseTool):
    """改进思维链工具 - Phase 3"""

    name = "cot_improve"
    description = "Generate an improved version of the current chain of thought based on specified modifications"
    parameters_schema = {
        "type": "object",
        "properties": {
            "adjust_constraints": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "phase": {"type": "string"},
                        "constraint_index": {"type": "integer"},
                        "new_type": {"type": "string", "enum": ["hard", "soft", "format"]},
                    },
                },
                "description": "Adjust constraint types",
            },
            "add_phase": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "prompt": {"type": "string"},
                    "order": {"type": "integer"},
                    "is_required": {"type": "boolean"},
                    "constraints": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "description": {"type": "string"},
                                "type": {"type": "string", "enum": ["hard", "soft", "format"]},
                            },
                        },
                    },
                },
                "description": "Add a new phase",
            },
            "modify_prompt": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "phase": {"type": "string"},
                        "addition": {"type": "string"},
                    },
                },
                "description": "Modify phase prompts",
            },
            "save_new_version": {
                "type": "boolean",
                "description": "Save the improved version as a new CoT (default: true)",
                "default": True,
            },
        },
        "required": [],
    }
    timeout = 15
    risk_level = "medium"

    async def execute(
        self,
        adjust_constraints: list[dict[str, Any]] | None = None,
        add_phase: dict[str, Any] | None = None,
        modify_prompt: list[dict[str, Any]] | None = None,
        save_new_version: bool = True,
        **kwargs: Any,
    ) -> str:
        """执行工具"""
        cot_manager = kwargs.get("cot_manager")

        if not cot_manager:
            return "Error: Chain of thought manager not available"

        current_cot = cot_manager.get_current_cot()
        if not current_cot:
            return "Error: No chain of thought currently loaded"

        # 构建改进配置
        improvements = {}
        if adjust_constraints:
            improvements["adjust_constraints"] = adjust_constraints
        if add_phase:
            improvements["add_phase"] = add_phase
        if modify_prompt:
            improvements["modify_prompt"] = modify_prompt

        if not improvements:
            return "Error: No improvements specified"

        # 生成改进版本
        improved_cot = cot_manager.generate_improved_cot(improvements)

        if not improved_cot:
            return "Error: Failed to generate improved CoT"

        # 保存
        if save_new_version:
            cot_manager.save_agent_cot(improved_cot)

        result = "=== Chain of Thought Improved ===\n\n"
        result += f"Original: {current_cot.name} v{current_cot.version}\n"
        result += f"New Version: {improved_cot.name} v{improved_cot.version}\n\n"

        if adjust_constraints:
            result += f"Constraints adjusted: {len(adjust_constraints)}\n"
        if add_phase:
            result += f"New phase added: {add_phase.get('name', 'unnamed')}\n"
        if modify_prompt:
            result += f"Prompts modified: {len(modify_prompt)}\n"

        if save_new_version:
            result += "\n✓ Saved as new version.\n"

        return result


class ReflectCoTTool(BaseTool):
    """反思思维链工具 - Phase 3"""

    name = "cot_reflect"
    description = "Record reflections and lessons learned from execution to improve the chain of thought"
    parameters_schema = {
        "type": "object",
        "properties": {
            "reflection": {
                "type": "string",
                "description": "Reflection on the execution process",
            },
            "what_worked": {
                "type": "string",
                "description": "What worked well in the execution",
            },
            "what_didnt_work": {
                "type": "string",
                "description": "What didn't work as expected",
            },
            "suggested_improvements": {
                "type": "string",
                "description": "Suggested improvements for future executions",
            },
            "apply_auto_improvements": {
                "type": "boolean",
                "description": "Automatically apply detected improvements (default: false)",
                "default": False,
            },
        },
        "required": ["reflection"],
    }
    timeout = 15
    risk_level = "low"

    async def execute(
        self,
        reflection: str,
        what_worked: str | None = None,
        what_didnt_work: str | None = None,
        suggested_improvements: str | None = None,
        apply_auto_improvements: bool = False,
        **kwargs: Any,
    ) -> str:
        """执行工具"""
        cot_manager = kwargs.get("cot_manager")

        if not cot_manager:
            return "Error: Chain of thought manager not available"

        current_cot = cot_manager.get_current_cot()
        if not current_cot:
            return "Error: No chain of thought currently loaded"

        # 构建完整反思
        full_reflection = f"反思: {reflection}\n"
        if what_worked:
            full_reflection += f"\n有效的做法:\n{what_worked}\n"
        if what_didnt_work:
            full_reflection += f"\n需要改进:\n{what_didnt_work}\n"
        if suggested_improvements:
            full_reflection += f"\n改进建议:\n{suggested_improvements}\n"

        # 更新思维链
        success = True  # Assume success if reflecting
        cot_manager.update_cot_from_reflection(full_reflection, success)

        # 自动分析改进
        analysis_result = ""
        if apply_auto_improvements:
            analysis = cot_manager.analyze_and_update_from_trace("auto")
            if "suggestions" in analysis and analysis["suggestions"]:
                analysis_result = "\n\n自动分析建议:\n"
                for suggestion in analysis["suggestions"]:
                    analysis_result += f"- {suggestion}\n"

        # 更新执行轨迹
        trace = cot_manager.get_execution_trace()
        if trace:
            trace.reflection = full_reflection

        result = "=== Reflection Recorded ===\n\n"
        result += f"CoT: {current_cot.name}\n"
        result += f"Reflection length: {len(full_reflection)} chars\n"
        result += "✓ Reflection saved and CoT updated.\n"
        result += analysis_result

        return result


class StatsCoTTool(BaseTool):
    """思维链统计工具 - Phase 3"""

    name = "cot_stats"
    description = "Get statistics and metrics about the current chain of thought"
    parameters_schema = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    timeout = 10
    risk_level = "low"

    async def execute(self, **kwargs: Any) -> str:
        """执行工具"""
        cot_manager = kwargs.get("cot_manager")

        if not cot_manager:
            return "Error: Chain of thought manager not available"

        stats = cot_manager.get_cot_statistics()

        if "error" in stats:
            return f"Error: {stats['error']}"

        result = "=== Chain of Thought Statistics ===\n\n"
        result += f"Name: {stats['name']}\n"
        result += f"Version: {stats['version']}\n"
        result += f"Source: {stats['source']}\n\n"

        result += "=== Usage ===\n"
        result += f"Execution Count: {stats['execution_count']}\n"
        result += f"Success Rate: {stats['success_rate']:.1%}\n\n"

        result += "=== Structure ===\n"
        result += f"Phases: {stats['phases_count']}\n"
        result += f"Total Constraints: {stats['total_constraints']}\n"
        result += f"  - Hard: {stats['hard_constraints']}\n"
        result += f"  - Soft/Format: {stats['total_constraints'] - stats['hard_constraints']}\n\n"

        result += "=== Timeline ===\n"
        result += f"Created: {stats['created_at']}\n"
        result += f"Updated: {stats['updated_at']}\n"

        return result


# ============ Phase 4: 高级特性工具 ============


class VersionCoTTool(BaseTool):
    """版本管理工具 - Phase 4"""

    name = "cot_version"
    description = "Manage chain of thought versions: view history, rollback, or compare versions"
    parameters_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["history", "rollback", "compare"],
                "description": "Action to perform",
            },
            "cot_name": {
                "type": "string",
                "description": "Chain of thought name",
            },
            "target_version": {
                "type": "string",
                "description": "Target version for rollback",
            },
        },
        "required": ["action", "cot_name"],
    }
    timeout = 10
    risk_level = "low"

    async def execute(
        self,
        action: str,
        cot_name: str,
        target_version: str | None = None,
        **kwargs: Any,
    ) -> str:
        """执行工具"""
        cot_manager = kwargs.get("cot_manager")

        if not cot_manager:
            return "Error: Chain of thought manager not available"

        if action == "history":
            history = cot_manager.get_version_history(cot_name)

            if not history:
                return f"No version history found for '{cot_name}'"

            result = f"=== Version History for '{cot_name}' ===\n\n"
            for entry in history:
                result += f"Version: {entry['version']} ({entry['source']})\n"
                result += f"  Updated: {entry['updated_at']}\n"
                result += f"  Executions: {entry['execution_count']}\n"
                result += f"  Success Rate: {entry['success_rate']:.1%}\n\n"

            return result

        elif action == "rollback":
            if not target_version:
                return "Error: target_version is required for rollback"

            rolled_back = cot_manager.rollback_to_version(cot_name, target_version)

            if not rolled_back:
                return f"Error: Version '{target_version}' not found for '{cot_name}'"

            cot_manager.set_current_cot(rolled_back)

            return f"✓ Rolled back '{cot_name}' to version {target_version}\nLoaded as current CoT."

        elif action == "compare":
            history = cot_manager.get_version_history(cot_name)

            if len(history) < 2:
                return f"Only {len(history)} version(s) available, cannot compare"

            # 比较最新两个版本
            v1, v2 = history[0], history[1]

            result = f"=== Comparing Versions ===\n\n"
            result += f"Version {v1['version']} (newer)\n"
            result += f"  Success Rate: {v1['success_rate']:.1%}\n"
            result += f"  Executions: {v1['execution_count']}\n\n"
            result += f"Version {v2['version']} (older)\n"
            result += f"  Success Rate: {v2['success_rate']:.1%}\n"
            result += f"  Executions: {v2['execution_count']}\n\n"

            if v1['success_rate'] > v2['success_rate']:
                result += "Recommendation: Keep newer version (higher success rate)"
            elif v1['success_rate'] < v2['success_rate']:
                result += "Recommendation: Consider rollback (older version has higher success rate)"
            else:
                result += "Recommendation: Versions have similar performance"

            return result

        return f"Unknown action: {action}"


class CombineCoTTool(BaseTool):
    """组合思维链工具 - Phase 4"""

    name = "cot_combine"
    description = "Combine multiple chains of thought using different strategies"
    parameters_schema = {
        "type": "object",
        "properties": {
            "chain_names": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Names of chains to combine",
            },
            "strategy": {
                "type": "string",
                "enum": ["sequential", "merge", "best_of"],
                "description": "Combination strategy",
                "default": "sequential",
            },
            "new_name": {
                "type": "string",
                "description": "Name for the combined chain (optional)",
            },
            "save_result": {
                "type": "boolean",
                "description": "Save the combined chain (default: true)",
                "default": True,
            },
        },
        "required": ["chain_names"],
    }
    timeout = 15
    risk_level = "medium"

    async def execute(
        self,
        chain_names: list[str],
        strategy: str = "sequential",
        new_name: str | None = None,
        save_result: bool = True,
        **kwargs: Any,
    ) -> str:
        """执行工具"""
        cot_manager = kwargs.get("cot_manager")

        if not cot_manager:
            return "Error: Chain of thought manager not available"

        if len(chain_names) < 2:
            return "Error: Need at least 2 chains to combine"

        # 组合
        combined = cot_manager.combine_chains(
            chain_names=chain_names,
            combination_strategy=strategy,
            new_name=new_name,
        )

        if not combined:
            return "Error: Failed to combine chains (check if chains exist)"

        # 保存
        if save_result:
            cot_manager.save_agent_cot(combined)

        result = "=== Chains Combined ===\n\n"
        result += f"Strategy: {strategy}\n"
        result += f"Source chains: {', '.join(chain_names)}\n"
        result += f"Result name: {combined.name}\n"
        result += f"Total phases: {len(combined.phases)}\n"

        if save_result:
            result += "\n✓ Combined chain saved.\n"

        return result


class ExportCoTTool(BaseTool):
    """导出思维链工具 - Phase 4"""

    name = "cot_export"
    description = "Export a chain of thought to various formats (JSON, YAML, Markdown)"
    parameters_schema = {
        "type": "object",
        "properties": {
            "cot_name": {
                "type": "string",
                "description": "Chain of thought name to export",
            },
            "format": {
                "type": "string",
                "enum": ["json", "yaml", "markdown"],
                "description": "Export format",
                "default": "json",
            },
            "include_metadata": {
                "type": "boolean",
                "description": "Include execution metadata (default: true)",
                "default": True,
            },
        },
        "required": ["cot_name"],
    }
    timeout = 10
    risk_level = "low"

    async def execute(
        self,
        cot_name: str,
        format: str = "json",
        include_metadata: bool = True,
        **kwargs: Any,
    ) -> str:
        """执行工具"""
        cot_manager = kwargs.get("cot_manager")

        if not cot_manager:
            return "Error: Chain of thought manager not available"

        exported = cot_manager.export_cot(
            cot_name=cot_name,
            export_format=format,
            include_metadata=include_metadata,
        )

        if not exported:
            return f"Error: Chain '{cot_name}' not found"

        result = f"=== Exported: {cot_name} ({format}) ===\n\n"
        result += exported

        return result


class ImportCoTTool(BaseTool):
    """导入思维链工具 - Phase 4"""

    name = "cot_import"
    description = "Import a chain of thought from JSON or YAML data"
    parameters_schema = {
        "type": "object",
        "properties": {
            "data": {
                "type": "string",
                "description": "Chain of thought data to import (JSON or YAML)",
            },
            "format": {
                "type": "string",
                "enum": ["json", "yaml"],
                "description": "Data format",
                "default": "json",
            },
            "overwrite": {
                "type": "boolean",
                "description": "Overwrite existing chain with same name (default: false)",
                "default": False,
            },
        },
        "required": ["data"],
    }
    timeout = 15
    risk_level = "medium"

    async def execute(
        self,
        data: str,
        format: str = "json",
        overwrite: bool = False,
        **kwargs: Any,
    ) -> str:
        """执行工具"""
        cot_manager = kwargs.get("cot_manager")

        if not cot_manager:
            return "Error: Chain of thought manager not available"

        imported = cot_manager.import_cot(
            data=data,
            format_type=format,
            overwrite=overwrite,
        )

        if not imported:
            return "Error: Failed to import chain (check format or name conflict)"

        result = "=== Chain Imported ===\n\n"
        result += f"Name: {imported.name}\n"
        result += f"Version: {imported.version}\n"
        result += f"Phases: {len(imported.phases)}\n"
        result += f"Source: {imported.source}\n"

        if overwrite:
            result += "\n✓ Existing chain overwritten.\n"
        else:
            result += "\n✓ Saved as new chain.\n"

        return result


class ListAllCoTTool(BaseTool):
    """列出所有思维链工具 - Phase 4"""

    name = "cot_list_all"
    description = "List all available chains of thought (templates and agent-created)"
    parameters_schema = {
        "type": "object",
        "properties": {
            "filter": {
                "type": "string",
                "description": "Filter by name pattern (optional)",
            },
        },
        "required": [],
    }
    timeout = 10
    risk_level = "low"

    async def execute(
        self,
        filter: str | None = None,
        **kwargs: Any,
    ) -> str:
        """执行工具"""
        cot_manager = kwargs.get("cot_manager")

        if not cot_manager:
            return "Error: Chain of thought manager not available"

        all_cots = cot_manager.list_all_cots()

        templates = all_cots["templates"]
        agent_cots = all_cots["agent_cots"]

        # 应用过滤
        if filter:
            filter_lower = filter.lower()
            templates = [t for t in templates if filter_lower in t.lower()]
            agent_cots = [c for c in agent_cots if filter_lower in c.lower()]

        result = "=== All Chains of Thought ===\n\n"

        result += f"Templates ({len(templates)}):\n"
        if templates:
            for name in sorted(templates):
                template = cot_manager.get_template(name)
                if template:
                    result += f"  • {name} (v{template.version})\n"
        else:
            result += "  (none)\n"

        result += f"\nAgent-Created ({len(agent_cots)}):\n"
        if agent_cots:
            for name in sorted(agent_cots):
                cot = cot_manager.get_agent_cot(name)
                if cot:
                    result += f"  • {name} (v{cot.version}, {cot.success_rate:.0%} success)\n"
        else:
            result += "  (none)\n"

        return result


class DeleteCoTTool(BaseTool):
    """删除思维链工具 - Phase 4"""

    name = "cot_delete"
    description = "Delete a chain of thought (agent-created only, templates cannot be deleted)"
    parameters_schema = {
        "type": "object",
        "properties": {
            "cot_name": {
                "type": "string",
                "description": "Chain of thought name to delete",
            },
            "source": {
                "type": "string",
                "enum": ["agent", "template"],
                "description": "Source of the chain (default: agent)",
                "default": "agent",
            },
            "confirm": {
                "type": "boolean",
                "description": "Confirm deletion (required)",
                "default": False,
            },
        },
        "required": ["cot_name", "confirm"],
    }
    timeout = 10
    risk_level = "high"

    async def execute(
        self,
        cot_name: str,
        source: str = "agent",
        confirm: bool = False,
        **kwargs: Any,
    ) -> str:
        """执行工具"""
        cot_manager = kwargs.get("cot_manager")

        if not cot_manager:
            return "Error: Chain of thought manager not available"

        if not confirm:
            return "Error: Deletion not confirmed. Set confirm=true to proceed."

        if source == "template":
            return "Error: Cannot delete template chains. Only agent-created chains can be deleted."

        deleted = cot_manager.delete_cot(cot_name, source)

        if deleted:
            return f"✓ Chain '{cot_name}' deleted successfully."
        else:
            return f"Error: Chain '{cot_name}' not found or could not be deleted."


class CloneCoTTool(BaseTool):
    """克隆思维链工具 - Phase 4"""

    name = "cot_clone"
    description = "Clone an existing chain of thought with a new name"
    parameters_schema = {
        "type": "object",
        "properties": {
            "source_name": {
                "type": "string",
                "description": "Name of the chain to clone",
            },
            "new_name": {
                "type": "string",
                "description": "Name for the cloned chain",
            },
            "source_type": {
                "type": "string",
                "enum": ["template", "agent", "any"],
                "description": "Source type preference (default: any)",
                "default": "any",
            },
        },
        "required": ["source_name", "new_name"],
    }
    timeout = 10
    risk_level = "low"

    async def execute(
        self,
        source_name: str,
        new_name: str,
        source_type: str = "any",
        **kwargs: Any,
    ) -> str:
        """执行工具"""
        cot_manager = kwargs.get("cot_manager")

        if not cot_manager:
            return "Error: Chain of thought manager not available"

        cloned = cot_manager.clone_cot(
            source_name=source_name,
            new_name=new_name,
            source_type=source_type,
        )

        if not cloned:
            return f"Error: Source chain '{source_name}' not found"

        result = "=== Chain Cloned ===\n\n"
        result += f"Source: {source_name}\n"
        result += f"New name: {new_name}\n"
        result += f"Phases: {len(cloned.phases)}\n"
        result += "\n✓ Cloned chain saved and ready to use.\n"

        return result
