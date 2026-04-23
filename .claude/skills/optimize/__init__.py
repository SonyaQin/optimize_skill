"""
Auto-Optimizer Skill for Claude Code

A robust, infinite-loop performance optimization system that treats the LLM
as a "stateless function" while a Python orchestrator manages all state.

Key Features:
- Dual-track verification (unit tests + benchmarks)
- Statistical benchmarking with Welch's t-test
- Graveyard of failed optimizations (prevents amnesia loop)
- Git sandbox isolation via worktrees
"""

__version__ = "1.0.0"
__author__ = "pengfu"

from .workspace_manager import WorkspaceManager
from .graveyard_manager import GraveyardManager

__all__ = [
    "WorkspaceManager",
    "GraveyardManager",
]
