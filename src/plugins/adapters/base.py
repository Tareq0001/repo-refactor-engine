"""
Language Adapter Plugin System — Extensible Architecture

Provides a base class and registry for language-specific adapters.
Each adapter knows how to:
1. Parse AST for its language
2. Extract imports/exports
3. Map types to target language equivalents
4. Generate idiomatic code patterns
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Type, Optional
from src.models.config import RepoFile


class LanguageAdapter(ABC):
    """Base class for all language adapters."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Language identifier (e.g., 'python', 'javascript')."""
        ...

    @property
    @abstractmethod
    def file_extensions(self) -> List[str]:
        """Supported file extensions."""
        ...

    @abstractmethod
    def extract_imports(self, content: str) -> List[Dict[str, str]]:
        """Extract import statements with metadata."""
        ...

    @abstractmethod
    def extract_exports(self, content: str) -> List[Dict[str, str]]:
        """Extract exported symbols (functions, classes, variables)."""
        ...

    @abstractmethod
    def extract_classes(self, content: str) -> List[Dict]:
        """Extract class definitions with methods and properties."""
        ...

    @abstractmethod
    def extract_functions(self, content: str) -> List[Dict]:
        """Extract function signatures with parameters and return types."""
        ...

    @abstractmethod
    def get_type_mapping(self, target_language: str) -> Dict[str, str]:
        """Map this language's types to the target language's types."""
        ...

    def compute_complexity(self, content: str) -> float:
        """Estimate cyclomatic complexity. Override for language-specific logic."""
        branch_keywords = {'if', 'else', 'elif', 'for', 'while', 'case', 'catch', 'except', 'switch', 'match', 'try'}
        import re
        words = re.findall(r'\b\w+\b', content)
        return sum(1 for w in words if w in branch_keywords)


class AdapterRegistry:
    """Registry for language adapters. Supports dynamic plugin loading."""

    _adapters: Dict[str, LanguageAdapter] = {}

    @classmethod
    def register(cls, adapter: LanguageAdapter):
        """Register a language adapter."""
        cls._adapters[adapter.name] = adapter
        for ext in adapter.file_extensions:
            cls._adapters[ext] = adapter

    @classmethod
    def get(cls, language_or_ext: str) -> Optional[LanguageAdapter]:
        """Retrieve an adapter by language name or file extension."""
        return cls._adapters.get(language_or_ext)

    @classmethod
    def list_supported(cls) -> List[str]:
        """List all registered language names."""
        return list(set(a.name for a in cls._adapters.values()))
