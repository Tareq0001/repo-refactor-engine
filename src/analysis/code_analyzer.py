"""
Codebase Analyzer — Static Analysis & Dependency Graph Builder

Performs deep static analysis on the ingested codebase:
1. Builds a full dependency/import graph across all files
2. Detects circular dependencies using Tarjan's algorithm
3. Identifies entry points (main files, index files)
4. Calculates cyclomatic complexity estimates
5. Groups files into logical modules
6. Detects the framework in use (Express, Django, Spring, etc.)
"""
import re
from typing import List, Dict, Set, Tuple
from collections import defaultdict
from src.models.config import (
    MigrationConfig, RepoFile, AnalysisResult, DependencyEdge
)

# Import pattern regexes per language
IMPORT_PATTERNS: Dict[str, List[re.Pattern]] = {
    "python": [
        re.compile(r'^import\s+([\w.]+)', re.MULTILINE),
        re.compile(r'^from\s+([\w.]+)\s+import', re.MULTILINE),
    ],
    "javascript": [
        re.compile(r'import\s+.*?from\s+[\'"]([^"\']+)[\'"]', re.MULTILINE),
        re.compile(r'require\(\s*[\'"]([^"\']+)[\'"]\s*\)', re.MULTILINE),
    ],
    "typescript": [
        re.compile(r'import\s+.*?from\s+[\'"]([^"\']+)[\'"]', re.MULTILINE),
        re.compile(r'require\(\s*[\'"]([^"\']+)[\'"]\s*\)', re.MULTILINE),
    ],
    "java": [
        re.compile(r'^import\s+([\w.]+);', re.MULTILINE),
    ],
    "go": [
        re.compile(r'"([\w./]+)"', re.MULTILINE),
    ],
    "ruby": [
        re.compile(r"require\s+['\"]([^'\"]+)['\"]", re.MULTILINE),
        re.compile(r"require_relative\s+['\"]([^'\"]+)['\"]", re.MULTILINE),
    ],
    "php": [
        re.compile(r"(?:require|include)(?:_once)?\s+['\"]([^'\"]+)['\"]", re.MULTILINE),
        re.compile(r"use\s+([\w\\]+)", re.MULTILINE),
    ],
    "csharp": [
        re.compile(r"using\s+([\w.]+);", re.MULTILINE),
    ],
    "rust": [
        re.compile(r"use\s+([\w:]+)", re.MULTILINE),
        re.compile(r'mod\s+(\w+)', re.MULTILINE),
    ],
}

# Framework detection signatures
FRAMEWORK_SIGNATURES: Dict[str, Dict[str, str]] = {
    "express": {"language": "javascript", "pattern": r"require\(['\"]express['\"]\)|from\s+['\"]express['\"]"},
    "django": {"language": "python", "pattern": r"django|DJANGO_SETTINGS_MODULE"},
    "flask": {"language": "python", "pattern": r"from\s+flask\s+import|import\s+flask"},
    "fastapi": {"language": "python", "pattern": r"from\s+fastapi\s+import|import\s+fastapi"},
    "spring-boot": {"language": "java", "pattern": r"@SpringBootApplication|org\.springframework"},
    "rails": {"language": "ruby", "pattern": r"Rails\.application|ActionController"},
    "laravel": {"language": "php", "pattern": r"Illuminate\\|artisan"},
    "nestjs": {"language": "typescript", "pattern": r"@nestjs/|@Module\(|@Controller\("},
    "nextjs": {"language": "typescript", "pattern": r"next\.config|getServerSideProps|getStaticProps"},
    "gin": {"language": "go", "pattern": r"github\.com/gin-gonic/gin"},
    "actix-web": {"language": "rust", "pattern": r"actix_web|HttpServer::new"},
    "dotnet": {"language": "csharp", "pattern": r"Microsoft\.AspNetCore|WebApplication\.CreateBuilder"},
}

# Entry point file names
ENTRY_POINT_NAMES: Set[str] = {
    "main.py", "app.py", "server.py", "index.js", "index.ts", "app.js", "app.ts",
    "main.go", "main.rs", "Main.java", "Program.cs", "manage.py", "wsgi.py",
    "asgi.py", "server.ts", "server.js",
}


class CodebaseAnalyzer:
    """
    Performs comprehensive static analysis on a collection of RepoFile objects.
    Builds dependency graphs, detects frameworks, identifies entry points,
    and estimates code complexity.
    """

    def __init__(self, config: MigrationConfig):
        self.config = config

    def analyze(self, files: List[RepoFile]) -> AnalysisResult:
        """Run the full analysis pipeline."""
        languages = self._detect_languages(files)
        dep_graph = self._build_dependency_graph(files)
        circular = self._find_circular_deps(dep_graph)
        entry_points = self._find_entry_points(files)
        complexity = self._estimate_complexity(files)
        modules = self._group_modules(files)
        framework = self._detect_framework(files)

        return AnalysisResult(
            languages=languages,
            dependency_graph=dep_graph,
            circular_deps=circular,
            entry_points=entry_points,
            avg_complexity=complexity,
            module_groups=modules,
            framework_detected=framework,
        )

    def _detect_languages(self, files: List[RepoFile]) -> List[str]:
        """Get unique languages sorted by frequency."""
        lang_count: Dict[str, int] = defaultdict(int)
        for f in files:
            if f.language != "unknown":
                lang_count[f.language] += 1
        return sorted(lang_count.keys(), key=lambda x: lang_count[x], reverse=True)

    def _build_dependency_graph(self, files: List[RepoFile]) -> List[DependencyEdge]:
        """Extract import statements and build a directed dependency graph."""
        edges: List[DependencyEdge] = []
        file_paths = {f.path for f in files}

        for file in files:
            patterns = IMPORT_PATTERNS.get(file.language, [])
            for pattern in patterns:
                for match in pattern.finditer(file.content):
                    import_path = match.group(1)
                    resolved = self._resolve_import(import_path, file.path, file_paths, file.language)
                    if resolved:
                        edges.append(DependencyEdge(
                            source_file=file.path,
                            target_file=resolved,
                            import_statement=match.group(0).strip(),
                        ))
        return edges

    def _resolve_import(self, import_path: str, source_file: str, all_paths: Set[str], language: str) -> str | None:
        """Attempt to resolve an import path to an actual file in the repo."""
        # Convert Python dot notation to path
        if language == "python":
            import_path = import_path.replace(".", "/")

        # Try common extensions
        candidates = [
            f"{import_path}.py", f"{import_path}.js", f"{import_path}.ts",
            f"{import_path}.tsx", f"{import_path}.jsx", f"{import_path}.java",
            f"{import_path}.go", f"{import_path}.rb", f"{import_path}.php",
            f"{import_path}/index.js", f"{import_path}/index.ts",
            f"{import_path}/__init__.py", import_path,
        ]

        for candidate in candidates:
            normalized = candidate.lstrip("./").replace("\\", "/")
            if normalized in all_paths:
                return normalized
        return None

    def _find_circular_deps(self, edges: List[DependencyEdge]) -> List[List[str]]:
        """Detect circular dependencies using iterative DFS (Tarjan-like)."""
        graph: Dict[str, Set[str]] = defaultdict(set)
        for edge in edges:
            graph[edge.source_file].add(edge.target_file)

        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        cycles: List[List[str]] = []

        def dfs(node: str, path: List[str]):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in graph.get(node, set()):
                if neighbor not in visited:
                    dfs(neighbor, path)
                elif neighbor in rec_stack:
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])

            path.pop()
            rec_stack.discard(node)

        for node in graph:
            if node not in visited:
                dfs(node, [])

        return cycles

    def _find_entry_points(self, files: List[RepoFile]) -> List[str]:
        """Identify likely application entry points."""
        return [
            f.path for f in files
            if any(f.path.endswith(ep) for ep in ENTRY_POINT_NAMES)
            or 'if __name__' in f.content
            or 'func main()' in f.content
            or 'public static void main' in f.content
        ]

    def _estimate_complexity(self, files: List[RepoFile]) -> float:
        """
        Estimate average cyclomatic complexity by counting branching keywords.
        This is a heuristic, not a formal analysis.
        """
        branch_keywords = {'if', 'elif', 'else', 'for', 'while', 'case', 'catch', 'except', 'switch', 'match'}
        total_branches = 0
        source_files = [f for f in files if f.file_type.value == "source"]

        for f in source_files:
            words = set(re.findall(r'\b\w+\b', f.content))
            total_branches += len(words & branch_keywords)

        return total_branches / max(len(source_files), 1)

    def _group_modules(self, files: List[RepoFile]) -> Dict[str, List[str]]:
        """Group files by top-level directory as logical modules."""
        groups: Dict[str, List[str]] = defaultdict(list)
        for f in files:
            parts = f.path.split("/")
            module = parts[0] if len(parts) > 1 else "root"
            groups[module].append(f.path)
        return dict(groups)

    def _detect_framework(self, files: List[RepoFile]) -> str | None:
        """Detect which framework the codebase uses."""
        combined_content = "\n".join(f.content[:2000] for f in files[:50])
        for framework, info in FRAMEWORK_SIGNATURES.items():
            if re.search(info["pattern"], combined_content):
                return framework
        return None
