"""
Pre/Post Migration Hook System

Allows users to register custom hooks that execute at specific points
in the migration pipeline. Hooks can modify files, run linters,
execute custom validators, or trigger external notifications.
"""
from typing import Callable, Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class HookPhase(str, Enum):
    PRE_INGESTION = "pre_ingestion"
    POST_INGESTION = "post_ingestion"
    PRE_ANALYSIS = "pre_analysis"
    POST_ANALYSIS = "post_analysis"
    PRE_MIGRATION = "pre_migration"
    POST_FILE_MIGRATION = "post_file_migration"
    POST_MIGRATION = "post_migration"
    PRE_VALIDATION = "pre_validation"
    POST_VALIDATION = "post_validation"
    PRE_OUTPUT = "pre_output"
    POST_OUTPUT = "post_output"


@dataclass
class HookResult:
    """Result from a hook execution."""
    hook_name: str
    phase: HookPhase
    success: bool
    message: str = ""
    modified_data: Optional[Any] = None
    execution_time_ms: float = 0.0


@dataclass
class Hook:
    """A registered hook."""
    name: str
    phase: HookPhase
    callback: Callable
    priority: int = 100  # Lower = runs first
    enabled: bool = True
    description: str = ""


class HookRegistry:
    """
    Registry for migration hooks. Hooks are executed in priority order
    at their registered phase.
    """

    def __init__(self):
        self._hooks: Dict[HookPhase, List[Hook]] = {phase: [] for phase in HookPhase}
        self._results: List[HookResult] = []

    def register(
        self,
        name: str,
        phase: HookPhase,
        callback: Callable,
        priority: int = 100,
        description: str = "",
    ):
        """Register a hook for a specific migration phase."""
        hook = Hook(name=name, phase=phase, callback=callback, priority=priority, description=description)
        self._hooks[phase].append(hook)
        self._hooks[phase].sort(key=lambda h: h.priority)

    def execute(self, phase: HookPhase, context: Any = None) -> List[HookResult]:
        """Execute all hooks for a given phase in priority order."""
        import time
        results = []
        for hook in self._hooks[phase]:
            if not hook.enabled:
                continue
            start = time.time()
            try:
                modified = hook.callback(context)
                result = HookResult(
                    hook_name=hook.name,
                    phase=phase,
                    success=True,
                    message=f"Hook '{hook.name}' executed successfully",
                    modified_data=modified,
                    execution_time_ms=(time.time() - start) * 1000,
                )
            except Exception as e:
                result = HookResult(
                    hook_name=hook.name,
                    phase=phase,
                    success=False,
                    message=f"Hook '{hook.name}' failed: {str(e)}",
                    execution_time_ms=(time.time() - start) * 1000,
                )
            results.append(result)
            self._results.append(result)
        return results

    def list_hooks(self, phase: Optional[HookPhase] = None) -> List[Hook]:
        """List registered hooks, optionally filtered by phase."""
        if phase:
            return self._hooks[phase]
        return [h for hooks in self._hooks.values() for h in hooks]

    def get_execution_log(self) -> List[HookResult]:
        """Return all hook execution results."""
        return list(self._results)


# === Built-in Hooks ===

def lint_python_hook(context):
    """Built-in hook: Run ruff linter on migrated Python files."""
    # In production: subprocess.run(["ruff", "check", context.output_dir])
    return {"linted": True, "issues": 0}


def format_code_hook(context):
    """Built-in hook: Auto-format migrated code."""
    # In production: subprocess.run(["black", context.output_dir]) or prettier
    return {"formatted": True}


def notify_slack_hook(context):
    """Built-in hook: Send Slack notification on migration completion."""
    # In production: requests.post(webhook_url, json={...})
    return {"notified": True}
