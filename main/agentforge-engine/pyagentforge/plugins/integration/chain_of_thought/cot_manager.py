"""
思维链管理器

负责思维链的加载、存储、验证和执行跟踪。
"""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import (
    ChainOfThought,
    Constraint,
    ConstraintType,
    ConstraintViolation,
    CoTExecutionTrace,
    CoTPhase,
)

logger = logging.getLogger(__name__)


class ChainOfThoughtManager:
    """思维链管理器"""

    def __init__(
        self,
        templates_dir: Path | None = None,
        agent_cot_dir: Path | None = None,
    ):
        """
        初始化思维链管理器

        Args:
            templates_dir: 用户预设模板目录
            agent_cot_dir: Agent 自生成思维链目录
        """
        self._templates: dict[str, ChainOfThought] = {}
        self._agent_cots: dict[str, ChainOfThought] = {}
        self._current_cot: ChainOfThought | None = None
        self._execution_trace: CoTExecutionTrace | None = None

        # 设置目录路径
        self._templates_dir = templates_dir
        self._agent_cot_dir = agent_cot_dir

        # 加载预设模板
        if self._templates_dir:
            self._load_templates()

    def _load_templates(self) -> None:
        """加载所有预设模板"""
        if not self._templates_dir or not self._templates_dir.exists():
            logger.info("Templates directory not found, skipping template loading")
            return

        for file_path in self._templates_dir.glob("*.json"):
            try:
                with open(file_path, encoding="utf-8") as f:
                    data = json.load(f)
                cot = ChainOfThought.from_dict(data)
                self._templates[cot.name] = cot
                logger.info(f"Loaded CoT template: {cot.name}")
            except Exception as e:
                logger.warning(f"Failed to load template {file_path}: {e}")

    def get_template(self, name: str) -> ChainOfThought | None:
        """获取预设模板"""
        return self._templates.get(name)

    def list_templates(self) -> list[str]:
        """列出所有预设模板名称"""
        return list(self._templates.keys())

    def get_agent_cot(self, name: str, agent_id: str | None = None) -> ChainOfThought | None:
        """获取 Agent 自生成的思维链"""
        key = f"{agent_id}/{name}" if agent_id else name
        return self._agent_cots.get(key)

    def save_agent_cot(self, cot: ChainOfThought, agent_id: str | None = None) -> None:
        """保存 Agent 自生成的思维链"""
        key = f"{agent_id}/{cot.name}" if agent_id else cot.name
        self._agent_cots[key] = cot

        # 持久化到文件
        if self._agent_cot_dir:
            self._agent_cot_dir.mkdir(parents=True, exist_ok=True)
            if agent_id:
                file_dir = self._agent_cot_dir / agent_id
                file_dir.mkdir(parents=True, exist_ok=True)
                file_path = file_dir / f"{cot.name}.json"
            else:
                file_path = self._agent_cot_dir / f"{cot.name}.json"

            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(cot.to_dict(), f, indent=2, ensure_ascii=False)
                logger.info(f"Saved agent CoT: {key}")
            except Exception as e:
                logger.warning(f"Failed to save agent CoT {key}: {e}")

    def load_cot(
        self,
        task_type: str,
        agent_id: str | None = None,
        prefer_agent: bool = True,
    ) -> ChainOfThought | None:
        """
        加载思维链

        优先级：
        1. Agent 自生成（如果 prefer_agent=True）
        2. 用户预设模板

        Args:
            task_type: 任务类型（如 debugging, code_review）
            agent_id: Agent ID（用于获取 Agent 自生成的思维链）
            prefer_agent: 是否优先使用 Agent 自生成的思维链

        Returns:
            加载的思维链，如果没有则返回 None
        """
        # 优先尝试 Agent 自生成
        if prefer_agent:
            agent_cot = self.get_agent_cot(task_type, agent_id)
            if agent_cot is None and not agent_id and task_type in self._agent_cots:
                agent_cot = self._agent_cots[task_type]
            if agent_cot is None and self._agent_cot_dir:
                candidate_path = (
                    self._agent_cot_dir / agent_id / f"{task_type}.json"
                    if agent_id
                    else self._agent_cot_dir / f"{task_type}.json"
                )
                if candidate_path.exists():
                    try:
                        with open(candidate_path, encoding="utf-8") as f:
                            data = json.load(f)
                        agent_cot = ChainOfThought.from_dict(data)
                        key = f"{agent_id}/{task_type}" if agent_id else task_type
                        self._agent_cots[key] = agent_cot
                    except Exception as e:
                        logger.warning(f"Failed to load agent CoT {candidate_path}: {e}")
            if agent_cot:
                logger.info(f"Using agent-generated CoT: {task_type}")
                self._current_cot = agent_cot
                return agent_cot

        # 尝试预设模板
        template = self.get_template(task_type)
        if template:
            logger.info(f"Using template CoT: {task_type}")
            self._current_cot = template
            return template

        logger.warning(f"No CoT found for task type: {task_type}")
        return None

    def set_current_cot(self, cot: ChainOfThought) -> None:
        """设置当前思维链"""
        self._current_cot = cot
        logger.info(f"Set current CoT: {cot.name}")

    def get_current_cot(self) -> ChainOfThought | None:
        """获取当前思维链"""
        return self._current_cot

    def start_execution(self, session_id: str) -> CoTExecutionTrace | None:
        """
        开始执行跟踪

        Args:
            session_id: 会话 ID

        Returns:
            执行轨迹
        """
        if not self._current_cot:
            logger.warning("No current CoT set, cannot start execution trace")
            return None

        self._execution_trace = CoTExecutionTrace(
            cot_name=self._current_cot.name,
            session_id=session_id,
        )

        # 更新执行计数
        self._current_cot.execution_count += 1

        logger.info(f"Started CoT execution trace: {self._current_cot.name}")
        return self._execution_trace

    def record_phase_result(self, phase_name: str, result: Any) -> None:
        """记录阶段执行结果"""
        if self._execution_trace:
            self._execution_trace.add_phase_result(phase_name, result)

    def record_violation(self, violation: ConstraintViolation) -> None:
        """记录约束违反"""
        if self._execution_trace:
            self._execution_trace.add_violation(violation)

    def record_plan(self, plan_steps: list[dict[str, Any]]) -> None:
        """记录执行计划"""
        if self._execution_trace:
            self._execution_trace.plan_steps = plan_steps

    def complete_execution(self, success: bool, reflection: str | None = None) -> None:
        """完成执行"""
        if self._execution_trace:
            self._execution_trace.complete(success, reflection)

            # 更新成功率
            if self._current_cot:
                total = self._current_cot.execution_count
                current_successes = int(self._current_cot.success_rate * (total - 1))
                if success:
                    current_successes += 1
                self._current_cot.success_rate = current_successes / total

                # 如果是 Agent 自生成的思维链，更新保存
                if self._current_cot.source == "agent":
                    self.save_agent_cot(self._current_cot)

    def get_execution_trace(self) -> CoTExecutionTrace | None:
        """获取当前执行轨迹"""
        return self._execution_trace

    def validate_plan_against_cot(
        self,
        plan_steps: list[dict[str, Any]],
    ) -> tuple[bool, list[ConstraintViolation]]:
        """
        验证计划是否符合当前思维链的约束

        Args:
            plan_steps: 计划步骤列表

        Returns:
            (是否通过验证, 约束违反列表)
        """
        if not self._current_cot:
            return True, []

        violations = []

        # 构建计划数据用于验证
        plan_data = {
            "steps": plan_steps,
            "step_count": len(plan_steps),
            "has_validation": any(
                step.get("validation")
                or step.get("verify")
                or any(
                    keyword in str(step.get("description", ""))
                    for keyword in ["验证", "校验", "确认", "测试", "验收", "verify", "validation", "test"]
                )
                for step in plan_steps
            ),
        }

        # 验证每个阶段的约束
        for phase in self._current_cot.phases:
            for constraint in phase.constraints:
                is_valid, details = self._validate_constraint(
                    constraint, plan_data, plan_steps
                )
                if not is_valid:
                    violations.append(ConstraintViolation(
                        phase_name=phase.name,
                        constraint_description=constraint.description,
                        constraint_type=constraint.constraint_type,
                        violation_details=details,
                    ))

        # 检查是否有硬约束违反
        has_hard_violation = any(
            v.constraint_type == ConstraintType.HARD
            for v in violations
        )

        return not has_hard_violation, violations

    def _validate_constraint(
        self,
        constraint: Constraint,
        plan_data: dict[str, Any],
        plan_steps: list[dict[str, Any]],
    ) -> tuple[bool, str]:
        """验证单个约束"""
        # 如果有自定义验证器，使用它
        if constraint.validator:
            return constraint.validate(plan_data)

        # 内置常见约束检查
        desc = constraint.description.lower()

        # 检查步骤数量约束
        if "步骤" in desc and "不超过" in desc:
            import re
            match = re.search(r"(\d+)", constraint.description)
            if match:
                max_steps = int(match.group(1))
                if len(plan_steps) > max_steps:
                    return False, f"Plan has {len(plan_steps)} steps, max allowed is {max_steps}"

        # 检查验证步骤约束
        if ("验证" in desc or "可验证" in desc) and not plan_data["has_validation"]:
            return False, "Plan lacks validation steps"

        return True, ""

    def generate_system_prompt_extension(self) -> str:
        """
        生成用于 system prompt 的思维链指导

        Returns:
            添加到 system prompt 的思维链指导文本
        """
        if not self._current_cot:
            return ""

        cot = self._current_cot
        lines = [
            f"\n## 思维链指导: {cot.name}",
            f"{cot.description}\n",
            "请按照以下阶段进行思考和执行:\n",
        ]

        for i, phase in enumerate(cot.get_ordered_phases(), 1):
            required = "（必需）" if phase.is_required else "（可选）"
            lines.append(f"### 阶段 {i}: {phase.name} {required}")
            lines.append(phase.prompt)

            if phase.constraints:
                lines.append("\n约束:")
                for c in phase.constraints:
                    type_marker = {
                        ConstraintType.HARD: "❗",
                        ConstraintType.SOFT: "⚠️",
                        ConstraintType.FORMAT: "📝",
                    }.get(c.constraint_type, "")
                    lines.append(f"  {type_marker} {c.description}")

            lines.append("")

        return "\n".join(lines)

    def update_cot_from_reflection(
        self,
        reflection: str,
        success: bool,
    ) -> None:
        """
        根据反思更新思维链

        Args:
            reflection: 反思内容
            success: 执行是否成功
        """
        if not self._current_cot:
            return

        # 简单实现：如果执行成功且反思提到某个阶段有用，可以增加权重
        # 更复杂的实现可以使用 LLM 来分析和提取改进建议
        self._current_cot.updated_at = self._current_cot.updated_at

        # 如果是 Agent 自生成的，更新保存
        if self._current_cot.source == "agent":
            self.save_agent_cot(self._current_cot)

    def analyze_and_update_from_trace(
        self,
        analysis_type: str = "auto",
    ) -> dict[str, Any]:
        """
        从执行轨迹分析并更新思维链

        Args:
            analysis_type: 分析类型 (auto, deep, quick)

        Returns:
            分析结果和建议
        """
        if not self._execution_trace or not self._current_cot:
            return {"error": "No execution trace or CoT available"}

        trace = self._execution_trace
        cot = self._current_cot

        analysis = {
            "cot_name": cot.name,
            "success": trace.success,
            "violations_count": len(trace.violations),
            "phases_executed": len(trace.phase_results),
            "hard_violations": sum(
                1 for v in trace.violations
                if v.constraint_type == ConstraintType.HARD
            ),
            "soft_violations": sum(
                1 for v in trace.violations
                if v.constraint_type == ConstraintType.SOFT
            ),
            "suggestions": [],
            "phase_insights": {},
        }

        # 分析阶段效果
        for phase_name, _result in trace.phase_results.items():
            phase = cot.get_phase(phase_name)
            if phase:
                # 检查该阶段是否有违反
                phase_violations = [
                    v for v in trace.violations
                    if v.phase_name == phase_name
                ]

                insight = {
                    "had_violations": len(phase_violations) > 0,
                    "violation_types": [
                        v.constraint_type.value for v in phase_violations
                    ],
                }

                # 生成改进建议
                if phase_violations:
                    suggestions = []
                    for v in phase_violations:
                        suggestions.append(
                            f"考虑调整 '{phase_name}' 阶段的约束: {v.constraint_description}"
                        )
                    insight["suggestions"] = suggestions
                    analysis["suggestions"].extend(suggestions)

                analysis["phase_insights"][phase_name] = insight

        # 整体建议
        if not trace.success:
            analysis["suggestions"].append(
                "执行未成功完成，建议检查约束是否过于严格"
            )

        if analysis["hard_violations"] > 0:
            analysis["suggestions"].append(
                f"发现 {analysis['hard_violations']} 个硬约束违反，"
                "考虑将部分硬约束降级为软约束"
            )

        # 自动更新（如果启用）
        if analysis_type == "auto" and trace.success:
            self._auto_update_cot(analysis)

        return analysis

    def _auto_update_cot(self, analysis: dict[str, Any]) -> None:
        """根据分析自动更新思维链"""
        if not self._current_cot:
            return

        cot = self._current_cot

        # 如果成功率高，增加执行计数（已在 complete_execution 中处理）
        # 如果某些阶段没有违反，可以考虑降低约束严格度
        for phase_name, insight in analysis.get("phase_insights", {}).items():
            phase = cot.get_phase(phase_name)
            if phase and not insight.get("had_violations", False):
                # 阶段执行顺利，记录到元数据
                if "smooth_phases" not in cot.metadata:
                    cot.metadata["smooth_phases"] = []
                if phase_name not in cot.metadata["smooth_phases"]:
                    cot.metadata["smooth_phases"].append(phase_name)

        cot.updated_at = datetime.now(UTC).isoformat()

        # 保存更新
        if cot.source == "agent":
            self.save_agent_cot(cot)

    def generate_improved_cot(
        self,
        improvements: dict[str, Any],
    ) -> ChainOfThought | None:
        """
        基于改进建议生成新的思维链版本

        Args:
            improvements: 改进配置
                {
                    "adjust_constraints": [
                        {
                            "phase": "plan",
                            "constraint_index": 0,
                            "new_type": "soft",  # hard -> soft
                        }
                    ],
                    "add_phase": {
                        "name": "review",
                        "prompt": "...",
                        "order": 3,
                    },
                    "modify_prompt": {
                        "phase": "execute",
                        "addition": "Always verify before proceeding",
                    }
                }

        Returns:
            新的思维链（原思维链不变）
        """
        if not self._current_cot:
            return None

        # 深拷贝当前思维链
        import copy
        new_cot = copy.deepcopy(self._current_cot)
        new_cot.version = self._increment_version(new_cot.version)
        new_cot.source = "agent"

        # 应用改进
        for adjustment in improvements.get("adjust_constraints", []):
            phase_name = adjustment.get("phase")
            constraint_idx = adjustment.get("constraint_index")
            new_type = adjustment.get("new_type")

            phase = new_cot.get_phase(phase_name)
            if phase and 0 <= constraint_idx < len(phase.constraints):
                phase.constraints[constraint_idx].constraint_type = ConstraintType(new_type)

        # 添加新阶段
        if "add_phase" in improvements:
            phase_data = improvements["add_phase"]
            new_phase = CoTPhase(
                name=phase_data.get("name", "new_phase"),
                prompt=phase_data.get("prompt", ""),
                constraints=[
                    Constraint(
                        description=c.get("description", ""),
                        constraint_type=ConstraintType(c.get("type", "soft")),
                    )
                    for c in phase_data.get("constraints", [])
                ],
                order=phase_data.get("order", len(new_cot.phases)),
                is_required=phase_data.get("is_required", True),
            )
            new_cot.phases.append(new_phase)

        # 修改提示
        for mod in improvements.get("modify_prompt", []):
            phase_name = mod.get("phase")
            addition = mod.get("addition")

            phase = new_cot.get_phase(phase_name)
            if phase and addition:
                phase.prompt += f"\n\n{addition}"

        new_cot.updated_at = datetime.now(UTC).isoformat()

        return new_cot

    def _increment_version(self, version: str) -> str:
        """递增版本号"""
        try:
            parts = version.split(".")
            if len(parts) >= 2:
                minor = int(parts[-1]) + 1
                parts[-1] = str(minor)
                return ".".join(parts)
        except (ValueError, IndexError):
            pass
        return version

    def get_cot_statistics(self) -> dict[str, Any]:
        """
        获取思维链统计信息

        Returns:
            统计数据
        """
        if not self._current_cot:
            return {"error": "No current CoT"}

        cot = self._current_cot

        return {
            "name": cot.name,
            "version": cot.version,
            "source": cot.source,
            "execution_count": cot.execution_count,
            "success_rate": cot.success_rate,
            "phases_count": len(cot.phases),
            "total_constraints": sum(
                len(p.constraints) for p in cot.phases
            ),
            "hard_constraints": sum(
                sum(1 for c in p.constraints if c.constraint_type == ConstraintType.HARD)
                for p in cot.phases
            ),
            "created_at": cot.created_at,
            "updated_at": cot.updated_at,
        }

    def create_cot_from_template(
        self,
        name: str,
        description: str,
        phases: list[dict[str, Any]],
        source: str = "agent",
    ) -> ChainOfThought:
        """
        从模板数据创建思维链

        Args:
            name: 思维链名称
            description: 描述
            phases: 阶段数据列表
            source: 来源标识

        Returns:
            创建的思维链
        """
        cot_phases = []
        for i, phase_data in enumerate(phases):
            constraints = []
            for c in phase_data.get("constraints", []):
                constraints.append(Constraint(
                    description=c.get("description", ""),
                    constraint_type=ConstraintType(c.get("type", "soft")),
                ))

            cot_phases.append(CoTPhase(
                name=phase_data.get("name", f"phase_{i}"),
                prompt=phase_data.get("prompt", ""),
                constraints=constraints,
                order=phase_data.get("order", i),
                is_required=phase_data.get("is_required", True),
            ))

        cot = ChainOfThought(
            name=name,
            description=description,
            phases=cot_phases,
            source=source,
        )

        return cot

    # ============ Phase 4: 高级特性 ============

    def get_version_history(self, cot_name: str) -> list[dict[str, Any]]:
        """
        获取思维链的版本历史

        Args:
            cot_name: 思维链名称

        Returns:
            版本历史列表
        """
        history = []

        # 检查模板版本
        template = self.get_template(cot_name)
        if template:
            history.append({
                "version": template.version,
                "source": "template",
                "updated_at": template.updated_at,
                "execution_count": template.execution_count,
                "success_rate": template.success_rate,
            })

        # 检查 Agent 版本
        agent_cot = self.get_agent_cot(cot_name)
        if agent_cot:
            history.append({
                "version": agent_cot.version,
                "source": "agent",
                "updated_at": agent_cot.updated_at,
                "execution_count": agent_cot.execution_count,
                "success_rate": agent_cot.success_rate,
            })

        # 按 version 排序
        history.sort(key=lambda x: self._parse_version(x["version"]), reverse=True)

        return history

    def _parse_version(self, version: str) -> tuple:
        """解析版本号为可比较的元组"""
        try:
            return tuple(int(p) for p in version.split("."))
        except (ValueError, AttributeError):
            return (0,)

    def rollback_to_version(
        self,
        cot_name: str,
        target_version: str,
    ) -> ChainOfThought | None:
        """
        回滚到指定版本

        Args:
            cot_name: 思维链名称
            target_version: 目标版本号

        Returns:
            回滚后的思维链，如果找不到则返回 None
        """
        # 简化实现：只检查当前可用的版本
        history = self.get_version_history(cot_name)

        for entry in history:
            if entry["version"] == target_version:
                if entry["source"] == "template":
                    return self.get_template(cot_name)
                else:
                    return self.get_agent_cot(cot_name)

        return None

    def combine_chains(
        self,
        chain_names: list[str],
        combination_strategy: str = "sequential",
        new_name: str | None = None,
    ) -> ChainOfThought | None:
        """
        组合多个思维链

        Args:
            chain_names: 要组合的思维链名称列表
            combination_strategy: 组合策略
                - sequential: 按顺序连接所有阶段
                - merge: 合并同名阶段
                - best_of: 选择执行效果最好的阶段
            new_name: 新思维链名称

        Returns:
            组合后的思维链
        """
        chains = []
        for name in chain_names:
            # 优先使用 Agent 版本
            cot = self.get_agent_cot(name) or self.get_template(name)
            if cot:
                chains.append(cot)

        if not chains:
            return None

        if combination_strategy == "sequential":
            return self._combine_sequential(chains, new_name)
        elif combination_strategy == "merge":
            return self._combine_merge(chains, new_name)
        elif combination_strategy == "best_of":
            return self._combine_best_of(chains, new_name)
        else:
            return None

    def _combine_sequential(
        self,
        chains: list[ChainOfThought],
        new_name: str | None,
    ) -> ChainOfThought:
        """顺序组合：将所有阶段按顺序连接"""
        all_phases = []
        order_offset = 0

        for chain in chains:
            for phase in chain.get_ordered_phases():
                # 创建新阶段（避免引用问题）
                import copy
                new_phase = copy.deepcopy(phase)
                new_phase.order += order_offset
                all_phases.append(new_phase)
            order_offset += len(chain.phases)

        return ChainOfThought(
            name=new_name or f"combined_{'_'.join(c.name for c in chains)}",
            description=f"Combined from: {', '.join(c.name for c in chains)}",
            phases=all_phases,
            source="agent",
        )

    def _combine_merge(
        self,
        chains: list[ChainOfThought],
        new_name: str | None,
    ) -> ChainOfThought:
        """合并组合：合并同名阶段"""
        merged_phases = {}

        for chain in chains:
            for phase in chain.phases:
                if phase.name not in merged_phases:
                    merged_phases[phase.name] = phase
                else:
                    # 合并约束
                    existing = merged_phases[phase.name]
                    existing_constraints = [
                        c.description for c in existing.constraints
                    ]
                    for c in phase.constraints:
                        if c.description not in existing_constraints:
                            existing.constraints.append(c)

        return ChainOfThought(
            name=new_name or f"merged_{'_'.join(c.name for c in chains)}",
            description=f"Merged from: {', '.join(c.name for c in chains)}",
            phases=list(merged_phases.values()),
            source="agent",
        )

    def _combine_best_of(
        self,
        chains: list[ChainOfThought],
        new_name: str | None,
    ) -> ChainOfThought:
        """最佳组合：选择成功率最高的阶段"""
        best_phases = {}

        for chain in chains:
            for phase in chain.phases:
                # 计算阶段得分（基于整体成功率）
                score = chain.success_rate * chain.execution_count

                if phase.name not in best_phases:
                    best_phases[phase.name] = (phase, score)
                else:
                    _, existing_score = best_phases[phase.name]
                    if score > existing_score:
                        best_phases[phase.name] = (phase, score)

        return ChainOfThought(
            name=new_name or f"bestof_{'_'.join(c.name for c in chains)}",
            description=f"Best phases from: {', '.join(c.name for c in chains)}",
            phases=[p for p, _ in best_phases.values()],
            source="agent",
        )

    def export_cot(
        self,
        cot_name: str,
        export_format: str = "json",
        include_metadata: bool = True,
    ) -> str | None:
        """
        导出思维链

        Args:
            cot_name: 思维链名称
            export_format: 导出格式 (json, yaml, markdown)
            include_metadata: 是否包含元数据

        Returns:
            导出的字符串，如果找不到则返回 None
        """
        cot = self.get_agent_cot(cot_name) or self.get_template(cot_name)
        if not cot:
            return None

        if export_format == "json":
            import json
            data = cot.to_dict()
            if not include_metadata:
                data = {k: v for k, v in data.items()
                        if k not in ["created_at", "updated_at", "execution_count", "success_rate"]}
            return json.dumps(data, indent=2, ensure_ascii=False)

        elif export_format == "yaml":
            try:
                import yaml
                data = cot.to_dict()
                if not include_metadata:
                    data = {k: v for k, v in data.items()
                            if k not in ["created_at", "updated_at", "execution_count", "success_rate"]}
                return yaml.dump(data, allow_unicode=True, default_flow_style=False)
            except ImportError:
                return "Error: PyYAML not installed"

        elif export_format == "markdown":
            return self._export_as_markdown(cot, include_metadata)

        return None

    def _export_as_markdown(
        self,
        cot: ChainOfThought,
        include_metadata: bool,
    ) -> str:
        """导出为 Markdown 格式"""
        lines = [
            f"# {cot.name}",
            "",
            f"**Description:** {cot.description}",
            "",
        ]

        if include_metadata:
            lines.extend([
                f"- **Version:** {cot.version}",
                f"- **Source:** {cot.source}",
                f"- **Tags:** {', '.join(cot.tags) or 'none'}",
                "",
            ])

        lines.append("## Phases")
        lines.append("")

        for i, phase in enumerate(cot.get_ordered_phases(), 1):
            required = " (required)" if phase.is_required else " (optional)"
            lines.append(f"### {i}. {phase.name}{required}")
            lines.append("")
            lines.append(phase.prompt)
            lines.append("")

            if phase.constraints:
                lines.append("**Constraints:**")
                lines.append("")
                for c in phase.constraints:
                    icon = {
                        ConstraintType.HARD: "❗",
                        ConstraintType.SOFT: "⚠️",
                        ConstraintType.FORMAT: "📝",
                    }.get(c.constraint_type, "")
                    lines.append(f"- {icon} {c.description}")
                lines.append("")

        return "\n".join(lines)

    def import_cot(
        self,
        data: str,
        format_type: str = "json",
        overwrite: bool = False,
    ) -> ChainOfThought | None:
        """
        导入思维链

        Args:
            data: 导入的数据字符串
            format_type: 数据格式 (json, yaml)
            overwrite: 是否覆盖已存在的同名思维链

        Returns:
            导入的思维链，如果失败则返回 None
        """
        try:
            if format_type == "json":
                import json
                parsed = json.loads(data)
            elif format_type == "yaml":
                try:
                    import yaml
                    parsed = yaml.safe_load(data)
                except ImportError:
                    logger.error("PyYAML not installed")
                    return None
            else:
                return None

            cot = ChainOfThought.from_dict(parsed)
            cot.source = "imported"

            # 检查是否已存在
            existing = self.get_agent_cot(cot.name) or self.get_template(cot.name)
            if existing and not overwrite:
                logger.warning(f"CoT '{cot.name}' already exists, use overwrite=True to replace")
                return None

            # 保存
            self.save_agent_cot(cot)
            return cot

        except Exception as e:
            logger.error(f"Failed to import CoT: {e}")
            return None

    def share_cot(self, cot_name: str, share_type: str = "copy") -> str | None:
        """
        分享思维链

        Args:
            cot_name: 思维链名称
            share_type: 分享类型
                - copy: 返回可复制的文本
                - link: 生成分享链接（需要配置）

        Returns:
            分享内容或链接
        """
        cot = self.get_agent_cot(cot_name) or self.get_template(cot_name)
        if not cot:
            return None

        if share_type == "copy":
            return self.export_cot(cot_name, "json", include_metadata=True)
        elif share_type == "link":
            # 简化实现：返回导出内容作为 "链接"
            # 实际实现可以上传到服务器并返回 URL
            return self.export_cot(cot_name, "json", include_metadata=True)

        return None

    def list_all_cots(self) -> dict[str, list[str]]:
        """
        列出所有思维链

        Returns:
            {"templates": [...], "agent_cots": [...]}
        """
        return {
            "templates": self.list_templates(),
            "agent_cots": list(self._agent_cots.keys()),
        }

    def delete_cot(self, cot_name: str, source: str = "agent") -> bool:
        """
        删除思维链

        Args:
            cot_name: 思维链名称
            source: 来源 (agent 或 template)

        Returns:
            是否删除成功
        """
        if source == "agent":
            if cot_name in self._agent_cots:
                del self._agent_cots[cot_name]

                # 删除文件
                if self._agent_cot_dir:
                    for file_path in self._agent_cot_dir.rglob(f"{cot_name}.json"):
                        try:
                            file_path.unlink()
                            logger.info(f"Deleted CoT file: {file_path}")
                        except Exception as e:
                            logger.warning(f"Failed to delete file {file_path}: {e}")

                return True
        elif source == "template" and cot_name in self._templates:
            del self._templates[cot_name]
            return True

        return False

    def clone_cot(
        self,
        source_name: str,
        new_name: str,
        source_type: str = "any",
    ) -> ChainOfThought | None:
        """
        克隆思维链

        Args:
            source_name: 源思维链名称
            new_name: 新名称
            source_type: 源类型 (template, agent, any)

        Returns:
            克隆的思维链
        """
        import copy

        if source_type == "template":
            source = self.get_template(source_name)
        elif source_type == "agent":
            source = self.get_agent_cot(source_name)
        else:
            source = self.get_agent_cot(source_name) or self.get_template(source_name)

        if not source:
            return None

        # 深拷贝
        cloned = copy.deepcopy(source)
        cloned.name = new_name
        cloned.source = "agent"
        cloned.created_at = datetime.now(UTC).isoformat()
        cloned.updated_at = cloned.created_at
        cloned.execution_count = 0
        cloned.success_rate = 0.0

        # 保存
        self.save_agent_cot(cloned)

        return cloned
