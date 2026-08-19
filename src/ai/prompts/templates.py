"""
Prompt Templates — Engineered Prompts for Each Migration Phase

Contains carefully crafted system and user prompts for:
1. Architectural comprehension (Claude)
2. Per-file code translation (Codex/GPT-4)
3. Validation reasoning
4. Documentation generation
"""
from typing import List, Dict


class PromptTemplates:
    """Factory for generating context-aware prompts."""

    @staticmethod
    def architecture_comprehension(
        framework: str,
        languages: List[str],
        entry_points: List[str],
        file_count: int,
        dep_edges: int,
        circular_deps: int,
        file_summaries: str,
        target_language: str,
    ) -> str:
        return f"""You are a Principal Software Architect performing a deep analysis of an entire codebase
for the purpose of migrating it to {target_language}.

## Repository Metadata
- Detected Framework: {framework or 'Unknown'}
- Languages: {', '.join(languages)}
- Entry Points: {', '.join(entry_points[:10])}
- Total Files: {file_count}
- Dependency Edges: {dep_edges}
- Circular Dependencies: {circular_deps}

## Codebase Contents (condensed)
{file_summaries}

## Your Analysis Must Cover
1. **Design Patterns**: MVC, Repository, CQRS, Event-Driven, Microservices, Monolith, etc.
2. **Data Flow**: How data moves between modules (request → controller → service → repo → DB).
3. **Shared Types/Interfaces**: Types that are imported across 3+ files and MUST be translated first.
4. **Business Logic Hotspots**: Core algorithms that require careful, precise translation.
5. **External Integrations**: APIs, databases, message queues, caches.
6. **Auth Patterns**: JWT, OAuth, session-based, API keys.
7. **Error Handling**: Custom error classes, global error handlers, try/catch patterns.
8. **Configuration**: Environment variables, config files, feature flags.
9. **Migration Risks**: Areas that will be hardest to translate (language-specific idioms, reflection, metaprogramming).
10. **Recommended Translation Order**: Which modules should be translated first for cleanest dependency resolution.

Provide your analysis in a structured JSON format with these 10 sections."""

    @staticmethod
    def file_translation(
        file_path: str,
        file_language: str,
        file_content: str,
        target_language: str,
        architecture_context: str,
        translated_dependencies: str,
        type_mappings: Dict[str, str],
        imports_metadata: str,
        exports_metadata: str,
    ) -> str:
        type_map_str = "\n".join(f"  {k} → {v}" for k, v in type_mappings.items())
        return f"""You are performing a precise, production-grade code migration.

## Architectural Context
{architecture_context[:4000]}

## Type Mappings ({file_language} → {target_language})
{type_map_str}

## File Metadata
- Path: {file_path}
- Source Language: {file_language}
- Imports: {imports_metadata}
- Exports: {exports_metadata}

## Already Translated Dependencies
{translated_dependencies or "None yet."}

## Source Code
```{file_language}
{file_content}
```

## Translation Rules
1. Preserve ALL business logic with exact semantic equivalence.
2. Use idiomatic {target_language} patterns (no direct syntax transliteration).
3. Apply the type mappings above for all type annotations.
4. Update import paths to match the translated dependency paths.
5. Preserve all comments, translating natural language if needed.
6. Use proper error handling patterns for {target_language}.
7. If a library has no equivalent, add a TODO comment with the original and suggest alternatives.
8. For async code, use the {target_language} async/await or concurrency model.
9. Generate complete, compilable code — NO placeholders or TODOs for business logic.

Return ONLY the translated code."""

    @staticmethod
    def documentation_generation(
        repo_url: str,
        target_language: str,
        file_count: int,
        validation_summary: str,
    ) -> str:
        return f"""Generate a comprehensive README.md for a migrated codebase.

Original Repository: {repo_url}
Migrated To: {target_language}
Files Translated: {file_count}
Validation: {validation_summary}

Include:
1. Project overview and what changed
2. New tech stack
3. Setup instructions for {target_language}
4. Migration notes and known limitations
5. Original vs. new architecture comparison"""
