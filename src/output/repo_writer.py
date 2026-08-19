"""
Repository Writer — Output Module

Writes the migrated codebase to disk with proper directory structure,
generates a migration report, creates a new package manifest for the
target language, and optionally initializes a git repository.
"""
import os
import json
from datetime import datetime, timezone
from typing import List
from src.models.config import MigrationConfig, MigratedFile, ValidationReport


class RepoWriter:
    """
    Writes migrated files to the output directory and generates
    accompanying metadata, reports, and package configuration.
    """

    def __init__(self, config: MigrationConfig):
        self.config = config

    def write(self, files: List[MigratedFile], report: ValidationReport):
        """Write all migrated files and generate reports."""
        os.makedirs(self.config.output_dir, exist_ok=True)

        self._write_migrated_files(files)
        self._write_migration_report(files, report)
        self._write_package_manifest(files)
        self._write_migration_map(files)

    def _write_migrated_files(self, files: List[MigratedFile]):
        """Write each migrated file to the output directory."""
        for file in files:
            output_path = os.path.join(self.config.output_dir, file.new_path)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(file.migrated_content)

    def _write_migration_report(self, files: List[MigratedFile], report: ValidationReport):
        """Generate a detailed markdown migration report."""
        report_path = os.path.join(self.config.output_dir, "MIGRATION_REPORT.md")

        avg_confidence = sum(f.confidence_score for f in files) / max(len(files), 1)
        files_with_warnings = [f for f in files if f.warnings]

        content = f"""# Migration Report

Generated: {datetime.now(timezone.utc).isoformat()}

## Summary
| Metric | Value |
|--------|-------|
| Source Repository | `{self.config.repo_url}` |
| Target Language | `{self.config.target_language}` |
| Files Migrated | {len(files)} |
| Average Confidence | {avg_confidence:.1%} |
| Validation Passed | {report.passed_checks}/{report.total_checks} |
| Success Rate | {report.success_rate:.1f}% |

## Validation Results
"""
        for check in report.checks:
            icon = "✅" if check.passed else "❌"
            content += f"- {icon} **{check.check_name}** ({check.severity}): {check.details}\n"

        if files_with_warnings:
            content += "\n## Files with Warnings\n"
            for f in files_with_warnings:
                content += f"\n### `{f.new_path}`\n"
                for w in f.warnings:
                    content += f"- ⚠️ {w}\n"

        content += f"\n## File Mapping\n| Original | Migrated | Confidence |\n|----------|----------|------------|\n"
        for f in files:
            content += f"| `{f.original_path}` | `{f.new_path}` | {f.confidence_score:.0%} |\n"

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _write_package_manifest(self, files: List[MigratedFile]):
        """Generate a package manifest appropriate for the target language."""
        manifests = {
            "typescript": ("package.json", json.dumps({
                "name": "migrated-project",
                "version": "1.0.0",
                "description": f"Migrated from {self.config.repo_url}",
                "main": "index.ts",
                "scripts": {"build": "tsc", "start": "node dist/index.js", "test": "jest"},
                "devDependencies": {"typescript": "^5.0.0", "@types/node": "^20.0.0", "jest": "^29.0.0"},
            }, indent=2)),
            "go": ("go.mod", f"module migrated-project\n\ngo 1.21\n"),
            "rust": ("Cargo.toml", '[package]\nname = "migrated-project"\nversion = "0.1.0"\nedition = "2021"\n'),
            "python-fastapi": ("pyproject.toml", f'[project]\nname = "migrated-project"\nversion = "1.0.0"\ndescription = "Migrated from {self.config.repo_url}"\nrequires-python = ">=3.11"\ndependencies = ["fastapi", "uvicorn", "pydantic"]\n'),
        }

        if self.config.target_language in manifests:
            filename, content = manifests[self.config.target_language]
            manifest_path = os.path.join(self.config.output_dir, filename)
            if not os.path.exists(manifest_path):
                with open(manifest_path, "w", encoding="utf-8") as f:
                    f.write(content)

    def _write_migration_map(self, files: List[MigratedFile]):
        """Write a JSON mapping of original → migrated file paths."""
        mapping = {
            "migration_date": datetime.now(timezone.utc).isoformat(),
            "source": self.config.repo_url,
            "target": self.config.target_language,
            "file_map": [
                {
                    "original": f.original_path,
                    "migrated": f.new_path,
                    "confidence": f.confidence_score,
                    "warnings": f.warnings,
                }
                for f in files
            ],
        }
        map_path = os.path.join(self.config.output_dir, ".migration_map.json")
        with open(map_path, "w", encoding="utf-8") as f:
            json.dump(mapping, f, indent=2)
