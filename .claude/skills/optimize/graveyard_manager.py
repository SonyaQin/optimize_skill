#!/usr/bin/env python3
"""
Graveyard Manager - The "Graveyard of Failed Optimizations"

This module prevents the "Amnesia Loop" problem where LLM repeatedly proposes
the same failed optimization strategies. It maintains a record of failed
attempts and their reasons, which are injected into prompts to warn the LLM.

Key concept: Treat every LLM-generated code as "toxic" until proven good.
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
import re


@dataclass
class GraveEntry:
    """A single entry in the graveyard of failed optimizations"""
    timestamp: str
    file_path: str
    diff_hash: str
    diff_content: str
    failure_type: str  # "unit_test", "benchmark", "syntax", "semantic", "no_improvement"
    failure_reason: str
    error_details: Optional[str] = None
    benchmark_before: Optional[Dict[str, float]] = None
    benchmark_after: Optional[Dict[str, float]] = None
    # Semantic embedding for similarity search (optional future enhancement)
    optimization_type: Optional[str] = None  # e.g., "caching", "algorithm", "memory"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class GraveyardManager:
    """
    Manages the graveyard of failed optimizations.

    The graveyard serves two purposes:
    1. Prevents the LLM from retrying the same failed approach
    2. Provides learning data for understanding what doesn't work
    """

    def __init__(self, graveyard_path: Optional[Path] = None):
        if graveyard_path is None:
            graveyard_path = Path.cwd() / "optimization_graveyard.json"
        self.graveyard_path = Path(graveyard_path)
        self.entries: List[GraveEntry] = []
        self._load()

    def _load(self):
        """Load graveyard from disk"""
        if self.graveyard_path.exists():
            try:
                with open(self.graveyard_path, 'r') as f:
                    data = json.load(f)
                    self.entries = [GraveEntry(**e) for e in data.get("entries", [])]
            except (json.JSONDecodeError, KeyError):
                self.entries = []
        else:
            self.entries = []

    def _save(self):
        """Save graveyard to disk"""
        data = {
            "version": 1,
            "last_updated": datetime.now().isoformat(),
            "total_entries": len(self.entries),
            "entries": [e.to_dict() for e in self.entries]
        }
        with open(self.graveyard_path, 'w') as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def compute_diff_hash(diff_content: str) -> str:
        """Compute a hash of the diff content for deduplication"""
        # Normalize whitespace and remove line numbers for hashing
        normalized = re.sub(r'\s+', ' ', diff_content.strip())
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def bury(
        self,
        file_path: str,
        diff_content: str,
        failure_type: str,
        failure_reason: str,
        error_details: Optional[str] = None,
        benchmark_before: Optional[Dict[str, float]] = None,
        benchmark_after: Optional[Dict[str, float]] = None,
        optimization_type: Optional[str] = None
    ) -> GraveEntry:
        """
        Add a failed optimization to the graveyard.

        Returns:
            The created GraveEntry
        """
        entry = GraveEntry(
            timestamp=datetime.now().isoformat(),
            file_path=str(file_path),
            diff_hash=self.compute_diff_hash(diff_content),
            diff_content=diff_content,
            failure_type=failure_type,
            failure_reason=failure_reason,
            error_details=error_details,
            benchmark_before=benchmark_before,
            benchmark_after=benchmark_after,
            optimization_type=optimization_type
        )

        self.entries.append(entry)
        self._save()

        return entry

    def is_duplicate_failure(self, diff_content: str, similarity_threshold: float = 0.8) -> bool:
        """
        Check if this diff has already been tried and failed.

        Args:
            diff_content: The diff to check
            similarity_threshold: For future fuzzy matching (currently exact)

        Returns:
            True if this exact diff has already failed
        """
        diff_hash = self.compute_diff_hash(diff_content)
        return any(e.diff_hash == diff_hash for e in self.entries)

    def get_similar_failures(
        self,
        file_path: str,
        optimization_type: Optional[str] = None,
        limit: int = 5
    ) -> List[GraveEntry]:
        """
        Get recent failures for a specific file or optimization type.

        This is used to inject into the LLM prompt to prevent repeating mistakes.
        """
        relevant = []

        for entry in reversed(self.entries):
            # Match by file path
            if file_path and entry.file_path == file_path:
                relevant.append(entry)
            # Match by optimization type
            elif optimization_type and entry.optimization_type == optimization_type:
                relevant.append(entry)

            if len(relevant) >= limit:
                break

        return relevant

    def get_warning_prompt(
        self,
        file_path: str,
        max_entries: int = 5
    ) -> str:
        """
        Generate a warning prompt section with recent failures.

        This is injected into the LLM prompt to warn against repeating mistakes.
        """
        failures = self.get_similar_failures(file_path, limit=max_entries)

        if not failures:
            return ""

        warning = "\n## ⚠️ Previous Failed Attempts - DO NOT REPEAT\n\n"
        warning += "The following optimization strategies have already been tried and failed:\n\n"

        for i, entry in enumerate(failures, 1):
            warning += f"### Failed Attempt {i}\n"
            warning += f"- **Type**: {entry.optimization_type or 'Unknown'}\n"
            warning += f"- **Why it failed**: {entry.failure_reason}\n"
            if entry.error_details:
                # Truncate long error details
                details = entry.error_details[:200] + "..." if len(entry.error_details) > 200 else entry.error_details
                warning += f"- **Error**: {details}\n"
            warning += f"- **Diff preview**: ```\n{entry.diff_content[:150]}...\n```\n\n"

        warning += "**DO NOT propose similar optimizations. Think of a completely different approach.**\n"

        return warning

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the graveyard"""
        if not self.entries:
            return {
                "total": 0,
                "by_type": {},
                "by_file": {}
            }

        by_type: Dict[str, int] = {}
        by_file: Dict[str, int] = {}

        for entry in self.entries:
            by_type[entry.failure_type] = by_type.get(entry.failure_type, 0) + 1
            by_file[entry.file_path] = by_file.get(entry.file_path, 0) + 1

        return {
            "total": len(self.entries),
            "by_type": by_type,
            "by_file": by_file,
            "oldest": self.entries[0].timestamp if self.entries else None,
            "newest": self.entries[-1].timestamp if self.entries else None
        }

    def clear_for_file(self, file_path: str):
        """
        Clear graveyard entries for a specific file.

        This should be called after a successful optimization is merged,
        because the codebase has changed and old failures may no longer be relevant.
        """
        original_count = len(self.entries)
        self.entries = [e for e in self.entries if e.file_path != file_path]

        if len(self.entries) < original_count:
            self._save()

    def clear_all(self):
        """Clear the entire graveyard"""
        self.entries = []
        self._save()

    def prune_old_entries(self, max_entries: int = 100):
        """
        Keep only the most recent entries to prevent the graveyard from growing too large.
        """
        if len(self.entries) > max_entries:
            self.entries = self.entries[-max_entries:]
            self._save()

    def export_for_analysis(self, output_path: Path):
        """Export graveyard data for analysis"""
        import csv

        with open(output_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'file_path', 'failure_type', 'failure_reason',
                'optimization_type', 'diff_hash'
            ])

            for entry in self.entries:
                writer.writerow([
                    entry.timestamp,
                    entry.file_path,
                    entry.failure_type,
                    entry.failure_reason,
                    entry.optimization_type or '',
                    entry.diff_hash
                ])


if __name__ == "__main__":
    # Test the graveyard manager
    gm = GraveyardManager(Path.cwd() / ".test_graveyard.json")

    # Add a test entry
    entry = gm.bury(
        file_path="test.py",
        diff_content="- old line\n+ new line",
        failure_type="unit_test",
        failure_reason="Test failed: assertion error",
        optimization_type="caching"
    )

    print(f"Buried entry: {entry.diff_hash}")
    print(f"Statistics: {gm.get_statistics()}")

    # Get warning prompt
    print(gm.get_warning_prompt("test.py"))

    # Cleanup test
    (Path.cwd() / ".test_graveyard.json").unlink(missing_ok=True)
