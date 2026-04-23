#!/usr/bin/env python3
"""
Workspace Manager - Strict Git Sandbox Isolation

This module provides strong consistency Git operations for the optimization loop.
All operations are performed in isolated Git worktrees to prevent workspace corruption.
"""

import os
import subprocess
import json
import time
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass
import shutil


@dataclass
class WorktreeInfo:
    """Information about a Git worktree"""
    path: Path
    branch: str
    commit: str


class WorkspaceManager:
    """
    Manages Git worktrees for isolated optimization experiments.

    Key principles:
    1. Every optimization runs in an isolated worktree
    2. Failed experiments are completely discarded
    3. Main branch is never directly modified
    4. All state changes go through Git
    """

    def __init__(self, repo_root: Path, main_branch: str = "main"):
        self.repo_root = Path(repo_root).resolve()
        self.main_branch = main_branch
        self.worktrees_dir = self.repo_root / ".opt-worktrees"
        self.current_worktree: Optional[WorktreeInfo] = None

        # Ensure worktrees directory exists
        self.worktrees_dir.mkdir(exist_ok=True)

    def _run_git(self, *args, cwd: Optional[Path] = None) -> Tuple[bool, str]:
        """Execute a git command and return (success, output)"""
        cmd = ["git"] + list(args)
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd or self.repo_root,
                capture_output=True,
                text=True,
                timeout=60
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "Git command timed out"
        except Exception as e:
            return False, str(e)

    def create_checkpoint(self, message: str = "checkpoint: before optimization") -> Tuple[bool, str]:
        """Create a checkpoint commit on current branch"""
        # Stage all changes
        success, output = self._run_git("add", "-A")
        if not success:
            return False, f"Failed to stage changes: {output}"

        # Create commit (allow empty)
        success, output = self._run_git("commit", "-m", message, "--allow-empty")
        if not success and "nothing to commit" not in output:
            return False, f"Failed to create checkpoint: {output}"

        return True, "Checkpoint created"

    def create_isolated_worktree(self, name: Optional[str] = None) -> Tuple[bool, Optional[WorktreeInfo]]:
        """
        Create an isolated Git worktree for experimentation.

        Returns:
            (success, worktree_info) tuple
        """
        if name is None:
            name = f"opt-run-{int(time.time())}"

        worktree_path = self.worktrees_dir / name
        branch_name = f"opt-temp-{name}"

        # Create new branch and worktree
        success, output = self._run_git(
            "worktree", "add", "-b", branch_name,
            str(worktree_path), "HEAD"
        )

        if not success:
            return False, None

        # Get current commit hash
        success, commit = self._run_git("rev-parse", "HEAD", cwd=worktree_path)
        commit = commit.strip() if success else "unknown"

        worktree_info = WorktreeInfo(
            path=worktree_path,
            branch=branch_name,
            commit=commit
        )
        self.current_worktree = worktree_info

        return True, worktree_info

    def apply_diff(self, diff_content: str, worktree: Optional[WorktreeInfo] = None) -> Tuple[bool, str]:
        """
        Apply a diff to the specified worktree (or current worktree).

        Returns:
            (success, message) tuple
        """
        target = worktree or self.current_worktree
        if target is None:
            return False, "No worktree specified"

        # Write diff to temp file
        diff_file = target.path / ".temp.patch"
        diff_file.write_text(diff_content)

        try:
            # Apply the patch
            success, output = self._run_git(
                "apply", "--check", str(diff_file),
                cwd=target.path
            )
            if not success:
                return False, f"Patch would not apply cleanly: {output}"

            # Actually apply
            success, output = self._run_git(
                "apply", str(diff_file),
                cwd=target.path
            )
            if not success:
                return False, f"Failed to apply patch: {output}"

            return True, "Patch applied successfully"
        finally:
            # Clean up temp file
            if diff_file.exists():
                diff_file.unlink()

    def run_tests_in_worktree(
        self,
        test_command: str,
        worktree: Optional[WorktreeInfo] = None,
        timeout: int = 300
    ) -> Tuple[bool, str, str]:
        """
        Run tests in the specified worktree.

        Returns:
            (success, stdout, stderr) tuple
        """
        target = worktree or self.current_worktree
        if target is None:
            return False, "", "No worktree specified"

        try:
            result = subprocess.run(
                test_command,
                shell=True,
                cwd=target.path,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", f"Test command timed out after {timeout}s"
        except Exception as e:
            return False, "", str(e)

    def commit_in_worktree(
        self,
        message: str,
        worktree: Optional[WorktreeInfo] = None
    ) -> Tuple[bool, str]:
        """Commit changes in the worktree"""
        target = worktree or self.current_worktree
        if target is None:
            return False, "No worktree specified"

        success, output = self._run_git("add", "-A", cwd=target.path)
        if not success:
            return False, f"Failed to stage: {output}"

        success, output = self._run_git(
            "commit", "-m", message,
            cwd=target.path
        )
        return success, output

    def merge_to_main(
        self,
        worktree: Optional[WorktreeInfo] = None,
        commit_message: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Merge successful optimization back to main branch.

        Returns:
            (success, message) tuple
        """
        target = worktree or self.current_worktree
        if target is None:
            return False, "No worktree specified"

        if commit_message is None:
            commit_message = f"optimize: merged from {target.branch}"

        # Switch to main branch
        success, output = self._run_git("checkout", self.main_branch)
        if not success:
            return False, f"Failed to checkout main: {output}"

        # Merge the worktree branch
        success, output = self._run_git(
            "merge", target.branch,
            "-m", commit_message,
            "--no-ff"
        )
        if not success:
            # Rollback
            self._run_git("merge", "--abort")
            return False, f"Merge failed: {output}"

        return True, "Successfully merged to main"

    def discard_worktree(self, worktree: Optional[WorktreeInfo] = None) -> Tuple[bool, str]:
        """
        Discard a worktree and its branch (used when optimization fails).

        Returns:
            (success, message) tuple
        """
        target = worktree or self.current_worktree
        if target is None:
            return True, "No worktree to discard"

        # Remove worktree
        success, output = self._run_git(
            "worktree", "remove", "--force",
            str(target.path)
        )
        if not success:
            # Try manual removal
            if target.path.exists():
                shutil.rmtree(target.path, ignore_errors=True)

        # Delete the branch
        self._run_git("branch", "-D", target.branch)

        if target == self.current_worktree:
            self.current_worktree = None

        return True, "Worktree discarded"

    def reset_to_checkpoint(self, commit_hash: Optional[str] = None) -> Tuple[bool, str]:
        """
        Reset main branch to a checkpoint (hard reset).

        Args:
            commit_hash: Specific commit to reset to, or HEAD~1 if None

        Returns:
            (success, message) tuple
        """
        target = commit_hash or "HEAD~1"

        # Ensure we're on main branch
        self._run_git("checkout", self.main_branch)

        success, output = self._run_git("reset", "--hard", target)
        if not success:
            return False, f"Reset failed: {output}"

        return True, f"Reset to {target}"

    def get_current_commit(self) -> str:
        """Get current commit hash on main branch"""
        success, commit = self._run_git("rev-parse", "HEAD")
        return commit.strip() if success else "unknown"

    def get_diff(self, worktree: Optional[WorktreeInfo] = None) -> str:
        """Get diff between worktree and main branch"""
        target = worktree or self.current_worktree
        if target is None:
            return ""

        success, diff = self._run_git(
            "diff", "HEAD",
            cwd=target.path
        )
        return diff if success else ""

    def cleanup_all_worktrees(self) -> int:
        """
        Remove all optimization worktrees.

        Returns:
            Number of worktrees removed
        """
        count = 0
        if self.worktrees_dir.exists():
            for item in self.worktrees_dir.iterdir():
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                    count += 1

        # Clean up git worktree references
        self._run_git("worktree", "prune")

        return count

    def get_status(self) -> dict:
        """Get current workspace status"""
        success, branch = self._run_git("branch", "--show-current")
        success2, status = self._run_git("status", "--porcelain")

        return {
            "branch": branch.strip() if success else "unknown",
            "commit": self.get_current_commit(),
            "has_changes": len(status.strip()) > 0 if success2 else False,
            "has_active_worktree": self.current_worktree is not None
        }


if __name__ == "__main__":
    # Test the workspace manager
    import sys

    ws = WorkspaceManager(Path.cwd())

    print("Current status:", json.dumps(ws.get_status(), indent=2))

    # Test worktree creation
    success, worktree = ws.create_isolated_worktree("test")
    if success:
        print(f"Created worktree at: {worktree.path}")
        ws.discard_worktree(worktree)
        print("Worktree cleaned up")
