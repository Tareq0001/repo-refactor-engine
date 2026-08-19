"""
Python Language Adapter — Deep AST-Based Analysis

Uses Python's built-in `ast` module for true Abstract Syntax Tree parsing,
not regex heuristics. This is what separates a toy tool from a production one.
"""
import ast
import re
from typing import Dict, List
from src.plugins.adapters.base import LanguageAdapter, AdapterRegistry


class PythonAdapter(LanguageAdapter):

    @property
    def name(self) -> str:
        return "python"

    @property
    def file_extensions(self) -> List[str]:
        return [".py"]

    def extract_imports(self, content: str) -> List[Dict[str, str]]:
        """Use AST to extract all import statements."""
        imports = []
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append({
                            "module": alias.name,
                            "alias": alias.asname or alias.name,
                            "type": "absolute",
                            "line": node.lineno,
                        })
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for alias in node.names:
                        imports.append({
                            "module": module,
                            "name": alias.name,
                            "alias": alias.asname or alias.name,
                            "type": "relative" if node.level > 0 else "absolute",
                            "level": node.level,
                            "line": node.lineno,
                        })
        except SyntaxError:
            # Fallback to regex for files with syntax errors
            for match in re.finditer(r'^(?:from\s+([\w.]+)\s+)?import\s+([\w., ]+)', content, re.MULTILINE):
                imports.append({"module": match.group(1) or match.group(2), "type": "regex_fallback"})
        return imports

    def extract_exports(self, content: str) -> List[Dict[str, str]]:
        """Extract __all__ definitions and top-level public symbols."""
        exports = []
        try:
            tree = ast.parse(content)
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == "__all__":
                            if isinstance(node.value, (ast.List, ast.Tuple)):
                                for elt in node.value.elts:
                                    if isinstance(elt, ast.Constant):
                                        exports.append({"name": elt.value, "type": "explicit_export"})
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not node.name.startswith("_"):
                        exports.append({"name": node.name, "type": "function"})
                if isinstance(node, ast.ClassDef):
                    if not node.name.startswith("_"):
                        exports.append({"name": node.name, "type": "class"})
        except SyntaxError:
            pass
        return exports

    def extract_classes(self, content: str) -> List[Dict]:
        """Extract class definitions with methods, bases, and decorators."""
        classes = []
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    methods = []
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            params = [
                                {"name": arg.arg, "annotation": ast.dump(arg.annotation) if arg.annotation else None}
                                for arg in item.args.args
                            ]
                            methods.append({
                                "name": item.name,
                                "params": params,
                                "is_async": isinstance(item, ast.AsyncFunctionDef),
                                "decorators": [ast.dump(d) for d in item.decorator_list],
                                "line": item.lineno,
                            })
                    classes.append({
                        "name": node.name,
                        "bases": [ast.dump(b) for b in node.bases],
                        "methods": methods,
                        "decorators": [ast.dump(d) for d in node.decorator_list],
                        "line": node.lineno,
                    })
        except SyntaxError:
            pass
        return classes

    def extract_functions(self, content: str) -> List[Dict]:
        """Extract top-level function signatures."""
        functions = []
        try:
            tree = ast.parse(content)
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    params = []
                    for arg in node.args.args:
                        params.append({
                            "name": arg.arg,
                            "annotation": ast.dump(arg.annotation) if arg.annotation else None,
                        })
                    functions.append({
                        "name": node.name,
                        "params": params,
                        "return_type": ast.dump(node.returns) if node.returns else None,
                        "is_async": isinstance(node, ast.AsyncFunctionDef),
                        "decorators": [ast.dump(d) for d in node.decorator_list],
                        "line": node.lineno,
                        "docstring": ast.get_docstring(node),
                    })
        except SyntaxError:
            pass
        return functions

    def get_type_mapping(self, target_language: str) -> Dict[str, str]:
        """Map Python types to target language types."""
        mappings = {
            "typescript": {
                "str": "string", "int": "number", "float": "number",
                "bool": "boolean", "None": "null", "list": "Array",
                "dict": "Record", "tuple": "readonly []", "set": "Set",
                "Optional": "| null", "Any": "any", "bytes": "Buffer",
            },
            "go": {
                "str": "string", "int": "int64", "float": "float64",
                "bool": "bool", "None": "nil", "list": "[]",
                "dict": "map", "bytes": "[]byte", "Any": "interface{}",
            },
            "rust": {
                "str": "String", "int": "i64", "float": "f64",
                "bool": "bool", "None": "None", "list": "Vec",
                "dict": "HashMap", "bytes": "Vec<u8>", "Any": "Box<dyn Any>",
            },
        }
        return mappings.get(target_language, {})


# Auto-register
AdapterRegistry.register(PythonAdapter())
