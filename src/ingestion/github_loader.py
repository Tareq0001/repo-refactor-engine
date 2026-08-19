"""
GitHub Repository Loader — Ingestion Module

Responsible for cloning a GitHub repository, traversing its file tree,
detecting languages, classifying file types, and returning a structured
list of RepoFile objects for downstream analysis.
"""
import os
import subprocess
import tempfile
import hashlib
from pathlib import Path
from typing import List, Dict, Set
from src.models.config import MigrationConfig, RepoFile, FileType

# Language detection by file extension
EXTENSION_LANGUAGE_MAP: Dict[str, str] = {
    ".py": "python", ".js": "javascript", ".ts": "typescript", ".tsx": "typescript",
    ".jsx": "javascript", ".java": "java", ".kt": "kotlin", ".go": "go",
    ".rs": "rust", ".rb": "ruby", ".php": "php", ".cs": "csharp",
    ".cpp": "cpp", ".c": "c", ".h": "c", ".hpp": "cpp",
    ".swift": "swift", ".scala": "scala", ".r": "r",
    ".sql": "sql", ".html": "html", ".css": "css", ".scss": "scss",
    ".yaml": "yaml", ".yml": "yaml", ".json": "json", ".toml": "toml",
    ".xml": "xml", ".md": "markdown", ".sh": "bash", ".bat": "batch",
}

# Directories to always skip
IGNORE_DIRS: Set[str] = {
    "node_modules", ".git", "__pycache__", ".venv", "venv", "dist",
    "build", ".next", ".nuxt", "target", "bin", "obj", ".idea",
    ".vscode", ".gradle", ".mvn", "vendor", "Pods",
}

# Test file patterns
TEST_PATTERNS = {"test_", "_test.", ".test.", ".spec.", "_spec.", "tests/", "__tests__/"}


class GitHubRepoLoader:
    """
    Clones a GitHub repository to a temporary directory, walks the file tree,
    and produces a list of RepoFile objects with metadata.
    """

    def __init__(self, config: MigrationConfig):
        self.config = config
        self.temp_dir = tempfile.mkdtemp(prefix="refactor_engine_")
        self.repo_dir = os.path.join(self.temp_dir, "repo")

    def load(self) -> List[RepoFile]:
        """Clone the repository and load all relevant files."""
        self._clone_repo()
        return self._walk_and_load()

    def _clone_repo(self):
        """Git clone the target repository."""
        cmd = [
            "git", "clone",
            "--branch", self.config.branch,
            "--depth", "1",  # Shallow clone for speed
            "--single-branch",
            self.config.repo_url,
            self.repo_dir,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to clone repository: {result.stderr}")

    def _walk_and_load(self) -> List[RepoFile]:
        """Recursively walk the cloned repo and build RepoFile objects."""
        files: List[RepoFile] = []

        for root, dirs, filenames in os.walk(self.repo_dir):
            # Prune ignored directories in-place
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

            for filename in filenames:
                abs_path = os.path.join(root, filename)
                rel_path = os.path.relpath(abs_path, self.repo_dir)
                size_bytes = os.path.getsize(abs_path)

                # Skip files exceeding size limit
                if size_bytes > self.config.max_file_size_kb * 1024:
                    continue

                # Skip binary files
                if self._is_binary(abs_path):
                    continue

                ext = Path(filename).suffix.lower()
                language = EXTENSION_LANGUAGE_MAP.get(ext, "unknown")

                # Skip non-code files unless they're configs
                if language == "unknown" and ext not in {".env", ".gitignore", ".dockerignore", ".editorconfig"}:
                    continue

                try:
                    with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                except Exception:
                    continue

                file_type = self._classify_file_type(rel_path, ext, language)

                # Skip test files if configured
                if file_type == FileType.TEST and not self.config.preserve_tests:
                    continue

                files.append(RepoFile(
                    path=rel_path.replace("\\", "/"),
                    content=content,
                    language=language,
                    file_type=file_type,
                    size_bytes=size_bytes,
                ))

        return files

    def _classify_file_type(self, path: str, ext: str, language: str) -> FileType:
        """Classify a file into source, test, config, doc, or asset."""
        path_lower = path.lower()

        if any(pattern in path_lower for pattern in TEST_PATTERNS):
            return FileType.TEST

        if ext in {".md", ".rst", ".txt"} or "docs/" in path_lower:
            return FileType.DOCUMENTATION

        if ext in {".yaml", ".yml", ".json", ".toml", ".xml", ".ini", ".cfg", ".env"}:
            return FileType.CONFIG

        if language in {"unknown"}:
            return FileType.ASSET

        if ext in {".sh", ".bat"} or any(
            build_file in path_lower
            for build_file in {"makefile", "dockerfile", "docker-compose", "jenkinsfile", ".github/"}
        ):
            return FileType.BUILD

        return FileType.SOURCE

    @staticmethod
    def _is_binary(filepath: str) -> bool:
        """Check if a file is binary by reading the first 8192 bytes."""
        try:
            with open(filepath, "rb") as f:
                chunk = f.read(8192)
                return b"\x00" in chunk
        except Exception:
            return True

    def cleanup(self):
        """Remove the temporary clone directory."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
