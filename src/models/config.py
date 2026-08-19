"""
Pydantic configuration models for the entire migration pipeline.
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from enum import Enum


class MigrationConfig(BaseModel):
    """Top-level configuration for a migration run."""
    repo_url: str
    target_language: str
    output_dir: str = "./output"
    branch: str = "main"
    claude_model: str = "claude-sonnet-4-20250514"
    codex_model: str = "gpt-4o"
    max_file_size_kb: int = 500
    dry_run: bool = False
    preserve_tests: bool = True
    parallel_workers: int = 4


class FileType(str, Enum):
    SOURCE = "source"
    TEST = "test"
    CONFIG = "config"
    DOCUMENTATION = "documentation"
    ASSET = "asset"
    BUILD = "build"


class RepoFile(BaseModel):
    """Represents a single file ingested from the repository."""
    path: str = Field(..., description="Relative path from repo root")
    content: str = Field(..., description="Raw file content")
    language: str = Field(default="unknown", description="Detected programming language")
    file_type: FileType = Field(default=FileType.SOURCE)
    size_bytes: int = 0
    encoding: str = "utf-8"


class DependencyEdge(BaseModel):
    """Represents an import/dependency relationship between two files."""
    source_file: str = Field(..., description="File that imports/requires")
    target_file: str = Field(..., description="File being imported/required")
    import_statement: str = Field(..., description="Original import/require statement")
    import_type: str = Field(default="static", description="static | dynamic | conditional")


class AnalysisResult(BaseModel):
    """Complete analysis output for a codebase."""
    languages: List[str] = Field(default_factory=list)
    dependency_graph: List[DependencyEdge] = Field(default_factory=list)
    circular_deps: List[List[str]] = Field(default_factory=list)
    entry_points: List[str] = Field(default_factory=list)
    avg_complexity: float = 0.0
    module_groups: Dict[str, List[str]] = Field(default_factory=dict)
    framework_detected: Optional[str] = None


class MigratedFile(BaseModel):
    """A file that has been translated to the target language."""
    original_path: str
    new_path: str
    original_content: str
    migrated_content: str
    target_language: str
    confidence_score: float = Field(ge=0.0, le=1.0, description="AI confidence in the translation")
    warnings: List[str] = Field(default_factory=list)


class ValidationCheck(BaseModel):
    """Result of a single validation check."""
    check_name: str
    passed: bool
    details: str
    severity: str = "info"  # info | warning | error


class ValidationReport(BaseModel):
    """Complete validation report after migration."""
    total_checks: int
    passed_checks: int
    failed_checks: int
    checks: List[ValidationCheck] = Field(default_factory=list)

    @property
    def success_rate(self) -> float:
        return self.passed_checks / max(self.total_checks, 1) * 100
