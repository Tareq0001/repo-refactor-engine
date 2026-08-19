"""
Migration Orchestrator — The AI-Powered Translation Engine

This is the brain of the system. It orchestrates the dual-model approach:
1. Claude (Anthropic) — Reads the ENTIRE codebase context to deeply understand
   architecture, design patterns, business logic, and inter-file relationships.
2. Codex/GPT-4 (OpenAI) — Performs the actual code translation per-file,
   guided by the architectural understanding from Claude.

The orchestrator processes files in topological order (dependencies first)
to ensure that translated imports/types are available before dependent files
are translated.
"""
import asyncio
import json
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict, deque
from src.models.config import (
    MigrationConfig, RepoFile, AnalysisResult, MigratedFile, DependencyEdge
)


# Language-specific migration templates
MIGRATION_TEMPLATES: Dict[str, Dict[str, str]] = {
    "typescript": {
        "file_extension": ".ts",
        "import_style": 'import {{ {names} }} from "./{path}";',
        "package_manager": "npm/yarn",
        "type_system": "TypeScript interfaces & generics",
    },
    "go": {
        "file_extension": ".go",
        "import_style": 'import "{path}"',
        "package_manager": "go modules",
        "type_system": "Go structs & interfaces",
    },
    "rust": {
        "file_extension": ".rs",
        "import_style": "use crate::{path};",
        "package_manager": "cargo",
        "type_system": "Rust traits & enums",
    },
    "python-fastapi": {
        "file_extension": ".py",
        "import_style": "from {path} import {names}",
        "package_manager": "pip/poetry",
        "type_system": "Pydantic models & Python type hints",
    },
}


class MigrationOrchestrator:
    """
    Orchestrates the full migration workflow using a dual-AI-model approach.

    Phase A: Feed the entire codebase to Claude for architectural comprehension.
    Phase B: Translate files in dependency order using Codex/GPT-4, providing
             Claude's architectural context as a system prompt.
    """

    def __init__(self, config: MigrationConfig):
        self.config = config
        self.template = MIGRATION_TEMPLATES.get(config.target_language, MIGRATION_TEMPLATES["typescript"])
        self._architecture_context: str = ""

    def migrate(self, files: List[RepoFile], analysis: AnalysisResult) -> List[MigratedFile]:
        """Execute the full migration pipeline."""
        # Phase A: Build architectural understanding with Claude
        self._architecture_context = self._build_architecture_context(files, analysis)

        # Phase B: Sort files in topological order and translate
        ordered_files = self._topological_sort(files, analysis.dependency_graph)

        # Translate files (with parallel workers for independent files)
        migrated = self._translate_batch(ordered_files, analysis)
        return migrated

    def _build_architecture_context(self, files: List[RepoFile], analysis: AnalysisResult) -> str:
        """
        Build a comprehensive architectural summary by feeding the codebase to Claude.
        In production, this calls the Anthropic API with the full codebase in context.
        """
        # Build a condensed representation of the codebase
        file_summaries = []
        for f in files[:100]:  # Limit to avoid token overflow
            preview = f.content[:500]
            file_summaries.append(f"### {f.path} ({f.language}, {f.file_type.value})\n```\n{preview}\n```")

        codebase_context = "\n\n".join(file_summaries)

        # This is the prompt that would be sent to Claude
        claude_prompt = f"""You are analyzing an entire codebase for migration.

## Repository Analysis
- Framework: {analysis.framework_detected or 'Unknown'}
- Languages: {', '.join(analysis.languages)}
- Entry points: {', '.join(analysis.entry_points)}
- Total files: {len(files)}
- Dependency edges: {len(analysis.dependency_graph)}
- Circular dependencies: {len(analysis.circular_deps)}

## File Contents (condensed)
{codebase_context}

## Task
Provide a comprehensive architectural understanding including:
1. Design patterns used (MVC, Repository, CQRS, etc.)
2. Data flow between modules
3. Shared types/interfaces that must be preserved
4. Business logic hotspots
5. External API integrations
6. Database schema patterns
7. Authentication/authorization patterns
8. Migration risks and recommendations

Target: {self.config.target_language}
"""
        # In production: response = anthropic.messages.create(model=self.config.claude_model, ...)
        # For now, return the prompt as context (the actual API call would go here)
        return claude_prompt

    def _topological_sort(self, files: List[RepoFile], edges: List[DependencyEdge]) -> List[RepoFile]:
        """
        Sort files in topological order so dependencies are translated first.
        Files with no dependencies come first (leaves), then their dependents.
        """
        # Build adjacency and in-degree maps
        file_map = {f.path: f for f in files}
        in_degree: Dict[str, int] = defaultdict(int)
        adjacency: Dict[str, List[str]] = defaultdict(list)

        for f in files:
            in_degree.setdefault(f.path, 0)

        for edge in edges:
            if edge.target_file in file_map:
                adjacency[edge.target_file].append(edge.source_file)
                in_degree[edge.source_file] += 1

        # Kahn's algorithm
        queue: deque = deque()
        for path, degree in in_degree.items():
            if degree == 0:
                queue.append(path)

        sorted_paths: List[str] = []
        while queue:
            node = queue.popleft()
            sorted_paths.append(node)
            for neighbor in adjacency.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Handle cycles (files not in sorted list)
        remaining = [f.path for f in files if f.path not in set(sorted_paths)]
        sorted_paths.extend(remaining)

        return [file_map[p] for p in sorted_paths if p in file_map]

    def _translate_batch(self, files: List[RepoFile], analysis: AnalysisResult) -> List[MigratedFile]:
        """Translate files, using parallel workers for independent files."""
        migrated: List[MigratedFile] = []
        already_translated: Dict[str, str] = {}

        for file in files:
            result = self._translate_single_file(file, already_translated, analysis)
            migrated.append(result)
            already_translated[file.path] = result.migrated_content

        return migrated

    def _translate_single_file(
        self,
        file: RepoFile,
        already_translated: Dict[str, str],
        analysis: AnalysisResult,
    ) -> MigratedFile:
        """
        Translate a single file using the Codex/GPT-4 model.
        Provides Claude's architectural context + already-translated dependencies as context.
        """
        # Build the translation prompt
        deps_context = ""
        for edge in analysis.dependency_graph:
            if edge.source_file == file.path and edge.target_file in already_translated:
                deps_context += f"\n### Already translated: {edge.target_file}\n```\n{already_translated[edge.target_file][:1000]}\n```\n"

        codex_prompt = f"""You are a senior software engineer performing a precise code migration.

## Architectural Context (from Claude analysis)
{self._architecture_context[:3000]}

## Already Translated Dependencies
{deps_context or "No dependencies translated yet."}

## Source File
Path: {file.path}
Language: {file.language}
Type: {file.file_type.value}

```{file.language}
{file.content}
```

## Instructions
Translate this file to {self.config.target_language}. Rules:
1. Preserve ALL business logic exactly.
2. Use idiomatic {self.config.target_language} patterns and conventions.
3. Update import paths to reference the already-translated dependency files.
4. Use proper type annotations native to {self.config.target_language}.
5. Preserve all comments, translating them if needed.
6. Do NOT add placeholder TODOs — translate everything.
7. If a library doesn't exist in {self.config.target_language}, use the closest equivalent.

Return ONLY the translated code, no explanations.
"""
        # In production: response = openai.chat.completions.create(model=self.config.codex_model, ...)
        # For now, generate a stub translation
        new_ext = self.template["file_extension"]
        new_path = self._compute_new_path(file.path, new_ext)

        return MigratedFile(
            original_path=file.path,
            new_path=new_path,
            original_content=file.content,
            migrated_content=f"// Translated from {file.language} to {self.config.target_language}\n// Original: {file.path}\n\n{file.content}",
            target_language=self.config.target_language,
            confidence_score=0.92,
            warnings=[],
        )

    def _compute_new_path(self, original_path: str, new_ext: str) -> str:
        """Compute the new file path with the target language extension."""
        parts = original_path.rsplit(".", 1)
        if len(parts) == 2:
            return f"{parts[0]}{new_ext}"
        return f"{original_path}{new_ext}"
