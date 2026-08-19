"""
Diff Engine — Side-by-Side Code Comparison

Generates rich, structured diffs between original and migrated code.
Supports: unified diff, side-by-side HTML, and semantic diff (ignoring
whitespace/comment changes to focus on logic differences).
"""
import difflib
from typing import List, Dict
from dataclasses import dataclass
from src.models.config import MigratedFile


@dataclass
class DiffResult:
    """Structured diff between original and migrated code."""
    file_path: str
    original_language: str
    target_language: str
    lines_added: int
    lines_removed: int
    lines_unchanged: int
    change_ratio: float  # 0.0 = identical, 1.0 = completely different
    unified_diff: str
    semantic_changes: List[Dict[str, str]]


class DiffEngine:
    """
    Generates detailed diffs between original and migrated files.
    """

    def generate_diff(self, file: MigratedFile) -> DiffResult:
        """Generate a comprehensive diff for a single file."""
        original_lines = file.original_content.splitlines(keepends=True)
        migrated_lines = file.migrated_content.splitlines(keepends=True)

        # Unified diff
        unified = list(difflib.unified_diff(
            original_lines,
            migrated_lines,
            fromfile=f"original/{file.original_path}",
            tofile=f"migrated/{file.new_path}",
            lineterm="",
        ))

        # Count changes
        added = sum(1 for line in unified if line.startswith("+") and not line.startswith("+++"))
        removed = sum(1 for line in unified if line.startswith("-") and not line.startswith("---"))

        # Sequence matcher for similarity ratio
        matcher = difflib.SequenceMatcher(None, file.original_content, file.migrated_content)
        similarity = matcher.ratio()

        # Semantic changes (high-level structural differences)
        semantic = self._extract_semantic_changes(original_lines, migrated_lines)

        return DiffResult(
            file_path=file.original_path,
            original_language=file.original_path.rsplit(".", 1)[-1] if "." in file.original_path else "unknown",
            target_language=file.target_language,
            lines_added=added,
            lines_removed=removed,
            lines_unchanged=max(len(original_lines) - removed, 0),
            change_ratio=1.0 - similarity,
            unified_diff="".join(unified),
            semantic_changes=semantic,
        )

    def generate_batch_diff(self, files: List[MigratedFile]) -> List[DiffResult]:
        """Generate diffs for all migrated files."""
        return [self.generate_diff(f) for f in files]

    def generate_html_report(self, diffs: List[DiffResult]) -> str:
        """Generate an HTML side-by-side diff report."""
        html_parts = [
            "<!DOCTYPE html><html><head><title>Migration Diff Report</title>",
            "<style>",
            "body { font-family: 'JetBrains Mono', monospace; margin: 20px; background: #1e1e2e; color: #cdd6f4; }",
            ".file-header { background: #313244; padding: 12px; border-radius: 8px; margin: 20px 0 10px; }",
            ".diff-container { background: #181825; border-radius: 8px; padding: 16px; overflow-x: auto; }",
            ".added { background: rgba(166,227,161,0.1); color: #a6e3a1; }",
            ".removed { background: rgba(243,139,168,0.1); color: #f38ba8; }",
            ".stats { display: flex; gap: 20px; margin: 10px 0; }",
            ".stat { padding: 8px 16px; border-radius: 6px; background: #313244; }",
            "</style></head><body>",
            "<h1>🔄 Migration Diff Report</h1>",
        ]

        total_added = sum(d.lines_added for d in diffs)
        total_removed = sum(d.lines_removed for d in diffs)
        avg_change = sum(d.change_ratio for d in diffs) / max(len(diffs), 1) * 100

        html_parts.append(f"<div class='stats'>")
        html_parts.append(f"<div class='stat'>📁 Files: {len(diffs)}</div>")
        html_parts.append(f"<div class='stat added'>+ {total_added} lines</div>")
        html_parts.append(f"<div class='stat removed'>- {total_removed} lines</div>")
        html_parts.append(f"<div class='stat'>Δ {avg_change:.1f}% changed</div>")
        html_parts.append(f"</div>")

        for diff in diffs:
            html_parts.append(f"<div class='file-header'><strong>{diff.file_path}</strong> → <em>{diff.target_language}</em> (Δ {diff.change_ratio*100:.1f}%)</div>")
            html_parts.append(f"<div class='diff-container'><pre>")
            for line in diff.unified_diff.split("\n"):
                css_class = "added" if line.startswith("+") else "removed" if line.startswith("-") else ""
                escaped = line.replace("<", "&lt;").replace(">", "&gt;")
                html_parts.append(f"<span class='{css_class}'>{escaped}</span>")
            html_parts.append(f"</pre></div>")

        html_parts.append("</body></html>")
        return "\n".join(html_parts)

    def _extract_semantic_changes(self, original: List[str], migrated: List[str]) -> List[Dict[str, str]]:
        """Identify high-level structural changes (functions added/removed, etc.)."""
        changes = []
        import re
        orig_funcs = set(re.findall(r'(?:def|function|func|fn)\s+(\w+)', "".join(original)))
        migr_funcs = set(re.findall(r'(?:def|function|func|fn)\s+(\w+)', "".join(migrated)))

        for f in migr_funcs - orig_funcs:
            changes.append({"type": "function_added", "name": f})
        for f in orig_funcs - migr_funcs:
            changes.append({"type": "function_removed_or_renamed", "name": f})

        return changes
