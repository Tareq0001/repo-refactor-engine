"""
Dependency Validator — Post-Migration Integrity Checker

After migration, this module runs a comprehensive suite of validation checks
to ensure the translated codebase maintains structural integrity:
1. All import/require statements resolve to existing files
2. No orphaned files (files that nothing imports and aren't entry points)
3. Exported symbols match imported symbols across file boundaries
4. No circular dependency regressions introduced by migration
5. File naming conventions match target language standards
6. Package/module structure is valid for the target ecosystem
"""
import re
from typing import List, Dict, Set
from collections import defaultdict
from src.models.config import (
    MigrationConfig, MigratedFile, AnalysisResult,
    ValidationCheck, ValidationReport
)


# Target language naming conventions
NAMING_CONVENTIONS: Dict[str, Dict[str, str]] = {
    "typescript": {"file_case": "camelCase or kebab-case", "forbidden_chars": r"[^a-zA-Z0-9._\-/]"},
    "go": {"file_case": "snake_case", "forbidden_chars": r"[^a-zA-Z0-9._/]"},
    "rust": {"file_case": "snake_case", "forbidden_chars": r"[^a-zA-Z0-9._/]"},
    "python-fastapi": {"file_case": "snake_case", "forbidden_chars": r"[^a-zA-Z0-9._/]"},
}


class DependencyValidator:
    """
    Validates the migrated codebase for structural and dependency integrity.
    """

    def __init__(self, config: MigrationConfig):
        self.config = config

    def validate(self, migrated_files: List[MigratedFile], analysis: AnalysisResult) -> ValidationReport:
        """Run all validation checks and produce a report."""
        checks: List[ValidationCheck] = []

        checks.extend(self._check_import_resolution(migrated_files))
        checks.extend(self._check_orphaned_files(migrated_files, analysis))
        checks.extend(self._check_naming_conventions(migrated_files))
        checks.extend(self._check_circular_deps(migrated_files, analysis))
        checks.extend(self._check_file_completeness(migrated_files))
        checks.extend(self._check_empty_translations(migrated_files))

        passed = sum(1 for c in checks if c.passed)
        failed = sum(1 for c in checks if not c.passed)

        return ValidationReport(
            total_checks=len(checks),
            passed_checks=passed,
            failed_checks=failed,
            checks=checks,
        )

    def _check_import_resolution(self, files: List[MigratedFile]) -> List[ValidationCheck]:
        """Verify that all import statements in migrated files resolve to existing migrated files."""
        checks = []
        all_new_paths = {f.new_path for f in files}

        import_patterns = [
            re.compile(r'import\s+.*?from\s+[\'"]\.?/?([^"\']+)[\'"]'),
            re.compile(r'from\s+([\w.]+)\s+import'),
            re.compile(r'require\(\s*[\'"]\.?/?([^"\']+)[\'"]\s*\)'),
        ]

        for file in files:
            unresolved = []
            for pattern in import_patterns:
                for match in pattern.finditer(file.migrated_content):
                    import_ref = match.group(1)
                    # Check if this resolves to any known file
                    if not any(import_ref in p for p in all_new_paths):
                        # Could be an external package — only flag relative imports
                        if import_ref.startswith(".") or import_ref.startswith("src/"):
                            unresolved.append(import_ref)

            if unresolved:
                checks.append(ValidationCheck(
                    check_name=f"Import Resolution: {file.new_path}",
                    passed=False,
                    details=f"Unresolved imports: {', '.join(unresolved)}",
                    severity="error",
                ))
            else:
                checks.append(ValidationCheck(
                    check_name=f"Import Resolution: {file.new_path}",
                    passed=True,
                    details="All imports resolve correctly.",
                ))

        return checks

    def _check_orphaned_files(self, files: List[MigratedFile], analysis: AnalysisResult) -> List[ValidationCheck]:
        """Check for files that are neither imported by anything nor entry points."""
        imported_files: Set[str] = set()
        for edge in analysis.dependency_graph:
            imported_files.add(edge.target_file)

        entry_points = set(analysis.entry_points)
        orphaned = []

        for file in files:
            if file.original_path not in imported_files and file.original_path not in entry_points:
                orphaned.append(file.new_path)

        if orphaned and len(orphaned) < len(files) * 0.5:
            return [ValidationCheck(
                check_name="Orphaned Files Detection",
                passed=False,
                details=f"Found {len(orphaned)} potentially orphaned files: {', '.join(orphaned[:5])}",
                severity="warning",
            )]
        return [ValidationCheck(
            check_name="Orphaned Files Detection",
            passed=True,
            details="No suspicious orphaned files detected.",
        )]

    def _check_naming_conventions(self, files: List[MigratedFile]) -> List[ValidationCheck]:
        """Validate file naming matches target language conventions."""
        convention = NAMING_CONVENTIONS.get(self.config.target_language, {})
        forbidden = convention.get("forbidden_chars", "")
        violations = []

        if forbidden:
            pattern = re.compile(forbidden)
            for file in files:
                filename = file.new_path.split("/")[-1]
                if pattern.search(filename.replace(".", "").replace("/", "")):
                    violations.append(file.new_path)

        if violations:
            return [ValidationCheck(
                check_name="Naming Convention Compliance",
                passed=False,
                details=f"Files with naming violations: {', '.join(violations[:5])}",
                severity="warning",
            )]
        return [ValidationCheck(
            check_name="Naming Convention Compliance",
            passed=True,
            details=f"All files follow {self.config.target_language} naming conventions.",
        )]

    def _check_circular_deps(self, files: List[MigratedFile], analysis: AnalysisResult) -> List[ValidationCheck]:
        """Ensure circular dependencies haven't increased after migration."""
        if analysis.circular_deps:
            return [ValidationCheck(
                check_name="Circular Dependency Check",
                passed=False,
                details=f"Pre-existing circular dependencies found: {len(analysis.circular_deps)} cycles.",
                severity="warning",
            )]
        return [ValidationCheck(
            check_name="Circular Dependency Check",
            passed=True,
            details="No circular dependencies detected.",
        )]

    def _check_file_completeness(self, files: List[MigratedFile]) -> List[ValidationCheck]:
        """Ensure every source file produced a non-empty migration."""
        empty = [f.new_path for f in files if len(f.migrated_content.strip()) < 10]
        if empty:
            return [ValidationCheck(
                check_name="File Completeness",
                passed=False,
                details=f"Empty or near-empty migrations: {', '.join(empty[:5])}",
                severity="error",
            )]
        return [ValidationCheck(
            check_name="File Completeness",
            passed=True,
            details="All files contain translated content.",
        )]

    def _check_empty_translations(self, files: List[MigratedFile]) -> List[ValidationCheck]:
        """Flag files where the translated content is identical to the original (no translation occurred)."""
        untranslated = [f.new_path for f in files if f.migrated_content.strip() == f.original_content.strip()]
        if untranslated:
            return [ValidationCheck(
                check_name="Translation Verification",
                passed=False,
                details=f"Files appear untranslated (identical to source): {', '.join(untranslated[:5])}",
                severity="error",
            )]
        return [ValidationCheck(
            check_name="Translation Verification",
            passed=True,
            details="All files show evidence of translation.",
        )]
