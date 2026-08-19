"""
Java Language Adapter

Handles Java-specific parsing: package declarations, import statements,
class/interface extraction, annotations, and type mappings.
"""
import re
from typing import Dict, List
from src.plugins.adapters.base import LanguageAdapter, AdapterRegistry


class JavaAdapter(LanguageAdapter):

    @property
    def name(self) -> str:
        return "java"

    @property
    def file_extensions(self) -> List[str]:
        return [".java"]

    def extract_imports(self, content: str) -> List[Dict[str, str]]:
        imports = []
        for match in re.finditer(r'^import\s+(static\s+)?([\w.]+(?:\.\*)?);', content, re.MULTILINE):
            is_static = bool(match.group(1))
            imports.append({"module": match.group(2), "type": "static" if is_static else "standard"})
        return imports

    def extract_exports(self, content: str) -> List[Dict[str, str]]:
        exports = []
        for match in re.finditer(r'public\s+(?:static\s+)?(?:final\s+)?(?:class|interface|enum|record)\s+(\w+)', content):
            exports.append({"name": match.group(1), "type": "class"})
        for match in re.finditer(r'public\s+(?:static\s+)?[\w<>\[\]]+\s+(\w+)\s*\(', content):
            exports.append({"name": match.group(1), "type": "method"})
        return exports

    def extract_classes(self, content: str) -> List[Dict]:
        classes = []
        for match in re.finditer(
            r'(?:@\w+(?:\([^)]*\))?\s+)*(?:public|private|protected)?\s*(?:abstract|final)?\s*(?:class|interface|record)\s+(\w+)(?:<[^>]+>)?(?:\s+extends\s+([\w.]+))?(?:\s+implements\s+([\w.,\s]+))?\s*\{',
            content
        ):
            name = match.group(1)
            extends = match.group(2)
            implements = [i.strip() for i in match.group(3).split(",")] if match.group(3) else []
            methods = []
            for method_match in re.finditer(
                r'(?:public|private|protected)\s+(?:static\s+)?(?:abstract\s+)?(?:synchronized\s+)?([\w<>\[\]]+)\s+(\w+)\s*\(([^)]*)\)',
                content
            ):
                params = [{"name": p.strip().split()[-1], "type": " ".join(p.strip().split()[:-1])} for p in method_match.group(3).split(",") if p.strip()]
                methods.append({"name": method_match.group(2), "return_type": method_match.group(1), "params": params})
            annotations = re.findall(r'@(\w+)', content[:match.start()])
            classes.append({"name": name, "bases": ([extends] if extends else []) + implements, "methods": methods, "annotations": annotations[-3:] if annotations else []})
        return classes

    def extract_functions(self, content: str) -> List[Dict]:
        functions = []
        for match in re.finditer(
            r'(?:public|private|protected)\s+(?:static\s+)?([\w<>\[\]]+)\s+(\w+)\s*\(([^)]*)\)\s*(?:throws\s+[\w.,\s]+)?\s*\{',
            content
        ):
            params = [{"name": p.strip().split()[-1], "type": " ".join(p.strip().split()[:-1])} for p in match.group(3).split(",") if p.strip()]
            functions.append({"name": match.group(2), "return_type": match.group(1), "params": params})
        return functions

    def get_type_mapping(self, target_language: str) -> Dict[str, str]:
        mappings = {
            "python": {"String": "str", "int": "int", "long": "int", "double": "float", "float": "float", "boolean": "bool", "void": "None", "List": "list", "Map": "dict", "Set": "set", "Optional": "Optional"},
            "go": {"String": "string", "int": "int32", "long": "int64", "double": "float64", "boolean": "bool", "void": "", "List": "[]", "Map": "map"},
            "typescript": {"String": "string", "int": "number", "long": "number", "double": "number", "boolean": "boolean", "void": "void", "List": "Array", "Map": "Map"},
        }
        return mappings.get(target_language, {})


AdapterRegistry.register(JavaAdapter())
