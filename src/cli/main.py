"""
Repo Refactor Engine — CLI Entry Point

A powerful CLI tool built with Typer that orchestrates the entire
repository migration pipeline: Ingest → Analyze → Migrate → Validate → Output.
"""
import typer
from typing import Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from src.ingestion.github_loader import GitHubRepoLoader
from src.analysis.code_analyzer import CodebaseAnalyzer
from src.migration.migration_orchestrator import MigrationOrchestrator
from src.validation.dependency_validator import DependencyValidator
from src.output.repo_writer import RepoWriter
from src.models.config import MigrationConfig

app = typer.Typer(
    name="refactor-engine",
    help="🔄 AI-Powered Full Repository Refactoring Engine — Migrate entire codebases across languages and frameworks.",
    add_completion=False,
)
console = Console()


@app.command()
def migrate(
    repo_url: str = typer.Argument(..., help="GitHub repository URL to migrate (e.g., https://github.com/org/repo)"),
    target_language: str = typer.Option(..., "--target", "-t", help="Target language or framework (e.g., 'typescript', 'go', 'rust', 'python-fastapi')"),
    output_dir: str = typer.Option("./output", "--output", "-o", help="Directory to write the migrated repository"),
    branch: str = typer.Option("main", "--branch", "-b", help="Branch to clone and migrate"),
    claude_model: str = typer.Option("claude-sonnet-4-20250514", "--claude-model", help="Claude model for code comprehension"),
    codex_model: str = typer.Option("gpt-4o", "--codex-model", help="OpenAI model for code translation"),
    max_file_size_kb: int = typer.Option(500, "--max-file-size", help="Skip files larger than this (KB)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Analyze without performing migration"),
    preserve_tests: bool = typer.Option(True, "--preserve-tests/--skip-tests", help="Migrate test files as well"),
    parallel_workers: int = typer.Option(4, "--workers", "-w", help="Number of parallel migration workers"),
):
    """
    🚀 Migrate an entire GitHub repository to a new language or framework.

    This command clones the target repository, builds a full dependency graph
    using AST analysis, feeds the codebase context to Claude for deep comprehension,
    then uses Codex/GPT-4 to translate each module while preserving inter-file
    dependencies and import chains.

    Examples:
        refactor-engine migrate https://github.com/expressjs/express --target typescript
        refactor-engine migrate https://github.com/django/django --target go --workers 8
        refactor-engine migrate https://github.com/company/legacy-java-app --target python-fastapi --dry-run
    """
    config = MigrationConfig(
        repo_url=repo_url,
        target_language=target_language,
        output_dir=output_dir,
        branch=branch,
        claude_model=claude_model,
        codex_model=codex_model,
        max_file_size_kb=max_file_size_kb,
        dry_run=dry_run,
        preserve_tests=preserve_tests,
        parallel_workers=parallel_workers,
    )

    console.print("\n[bold blue]🔄 Repo Refactor Engine v1.0.0[/bold blue]\n")

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:

        # Phase 1: Ingestion
        task = progress.add_task("[cyan]Phase 1/5: Cloning & ingesting repository...", total=None)
        loader = GitHubRepoLoader(config)
        repo_files = loader.load()
        progress.update(task, description=f"[green]✓ Phase 1: Ingested {len(repo_files)} files")

        # Phase 2: Analysis
        task = progress.add_task("[cyan]Phase 2/5: Building dependency graph & AST analysis...", total=None)
        analyzer = CodebaseAnalyzer(config)
        analysis_result = analyzer.analyze(repo_files)
        progress.update(task, description=f"[green]✓ Phase 2: Mapped {len(analysis_result.dependency_graph)} dependency edges")

        if config.dry_run:
            console.print("\n[yellow]🔍 Dry run complete. Analysis results printed above. No migration performed.[/yellow]")
            raise typer.Exit()

        # Phase 3: Migration
        task = progress.add_task("[cyan]Phase 3/5: AI-powered code translation...", total=None)
        orchestrator = MigrationOrchestrator(config)
        migrated_files = orchestrator.migrate(repo_files, analysis_result)
        progress.update(task, description=f"[green]✓ Phase 3: Translated {len(migrated_files)} files to {target_language}")

        # Phase 4: Validation
        task = progress.add_task("[cyan]Phase 4/5: Validating dependencies & import chains...", total=None)
        validator = DependencyValidator(config)
        validation_report = validator.validate(migrated_files, analysis_result)
        progress.update(task, description=f"[green]✓ Phase 4: {validation_report.passed_checks}/{validation_report.total_checks} checks passed")

        # Phase 5: Output
        task = progress.add_task("[cyan]Phase 5/5: Writing migrated repository...", total=None)
        writer = RepoWriter(config)
        writer.write(migrated_files, validation_report)
        progress.update(task, description=f"[green]✓ Phase 5: Repository written to {output_dir}")

    console.print(f"\n[bold green]🎉 Migration complete![/bold green]")
    console.print(f"   Source: {repo_url}")
    console.print(f"   Target: {target_language}")
    console.print(f"   Output: {output_dir}")
    console.print(f"   Files migrated: {len(migrated_files)}")
    console.print(f"   Validation: {validation_report.passed_checks}/{validation_report.total_checks} passed\n")


@app.command()
def analyze(
    repo_url: str = typer.Argument(..., help="GitHub repository URL to analyze"),
    branch: str = typer.Option("main", "--branch", "-b"),
):
    """
    📊 Analyze a repository's structure, dependencies, and complexity without migrating.

    Useful for understanding a legacy codebase before committing to a full migration.
    Outputs language distribution, dependency graph, cyclomatic complexity, and coupling metrics.
    """
    config = MigrationConfig(repo_url=repo_url, target_language="analysis-only", branch=branch)
    loader = GitHubRepoLoader(config)
    repo_files = loader.load()

    analyzer = CodebaseAnalyzer(config)
    result = analyzer.analyze(repo_files)

    console.print(f"\n[bold]📊 Repository Analysis: {repo_url}[/bold]")
    console.print(f"   Total files: {len(repo_files)}")
    console.print(f"   Languages detected: {', '.join(result.languages)}")
    console.print(f"   Dependency edges: {len(result.dependency_graph)}")
    console.print(f"   Avg cyclomatic complexity: {result.avg_complexity:.2f}")
    console.print(f"   Circular dependencies: {len(result.circular_deps)}\n")


@app.command()
def supported():
    """📋 List all supported migration paths (source → target)."""
    migrations = {
        "JavaScript/Node.js": ["TypeScript", "Go", "Rust", "Python"],
        "Python (Django/Flask)": ["FastAPI", "Go (Gin)", "TypeScript (NestJS)"],
        "Java (Spring Boot)": ["Kotlin (Spring)", "Go", "Python (FastAPI)", "TypeScript (NestJS)"],
        "Ruby (Rails)": ["Python (Django)", "TypeScript (NestJS)", "Go"],
        "PHP (Laravel)": ["Python (FastAPI)", "TypeScript (NestJS)", "Go"],
        "C# (.NET)": ["Go", "TypeScript", "Rust"],
    }
    console.print("\n[bold]📋 Supported Migration Paths[/bold]\n")
    for source, targets in migrations.items():
        console.print(f"  [cyan]{source}[/cyan] → {', '.join(targets)}")
    console.print()


if __name__ == "__main__":
    app()
