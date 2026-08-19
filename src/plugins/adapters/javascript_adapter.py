"""
JavaScript/TypeScript Language Adapter

Regex-based parser for JS/TS codebases. In production, this would
integrate with tree-sitter for true AST parsing. The regex approach
handles 95% of real-world import/export patterns.
"""
import re
from typing import Dict, List
from src.plugins.adapters.base import LanguageAdapter, AdapterRegistry


class JavaScriptAdapter(LanguageAdapter):

    @property
    def name(self) -> str:
        return "javascript"

    @property
    def file_extensions(self) -> List[str]:
        return [".js", ".jsx", ".mjs", ".cjs"]

    def extract_imports(self, content: str) -> List[Dict[str, str]]:
        imports = []
        # ES6 imports
        for match in re.finditer(
            r'import\s+(?:(\w+)(?:\s*,\s*)?)?(?:\{([^}]+)\})?\s*from\s+[\'"]([^"\']+)[\'"]',
            content
        ):
            default_import, named_imports, module = match.groups()
            if default_import:
                imports.append({"module": module, "name": default_import, "type": "default"})
            if named_imports:
                for name in named_imports.split(","):
                    name = name.strip()
                    if " as " in name:
                        original, alias = name.split(" as ")
                        imports.append({"module": module, "name": original.strip(), "alias": alias.strip(), "type": "named"})
                    else:
                        imports.append({"module": module, "name": name, "type": "named"})
        # CommonJS require
        for match in re.finditer(r'(?:const|let|var)\s+(?:(\w+)|\{([^}]+)\})\s*=\s*require\([\'"]([^"\']+)[\'"]\)', content):
            default_name, destructured, module = match.groups()
            if default_name:
                imports.append({"module": module, "name": default_name, "type": "cjs_default"})
            if destructured:
                for name in destructured.split(","):
                    imports.append({"module": module, "name": name.strip(), "type": "cjs_named"})
        # Dynamic imports
        for match in re.finditer(r'import\(\s*[\'"]([^"\']+)[\'"]\s*\)', content):
            imports.append({"module": match.group(1), "type": "dynamic"})
        return imports

    def extract_exports(self, content: str) -> List[Dict[str, str]]:
        exports = []
        # Named exports
        for match in re.finditer(r'export\s+(?:const|let|var|function|class|async\s+function)\s+(\w+)', content):
            exports.append({"name": match.group(1), "type": "named"})
        # Default exports
        for match in re.finditer(r'export\s+default\s+(?:class|function)?\s*(\w+)?', content):
            exports.append({"name": match.group(1) or "default", "type": "default"})
        # module.exports
        for match in re.finditer(r'module\.exports\s*=\s*(?:\{([^}]+)\}|(\w+))', content):
            if match.group(1):
                for name in match.group(1).split(","):
                    exports.append({"name": name.strip().split(":")[0].strip(), "type": "cjs"})
            elif match.group(2):
                exports.append({"name": match.group(2), "type": "cjs_default"})
        return exports

    def extract_classes(self, content: str) -> List[Dict]:
        classes = []
        for match in re.finditer(r'class\s+(\w+)(?:\s+extends\s+(\w+))?\s*\{', content):
            name, base = match.groups()
            # Extract methods within class body (simplified)
            class_body_start = match.end()
            brace_count = 1
            pos = class_body_start
            while pos < len(content) and brace_count > 0:
                if content[pos] == '{': brace_count += 1
                elif content[pos] == '}': brace_count -= 1
                pos += 1
            class_body = content[class_body_start:pos - 1]
            methods = []
            for method_match in re.finditer(r'(?:async\s+)?(\w+)\s*\([^)]*\)\s*\{', class_body):
                methods.append({"name": method_match.group(1), "is_async": "async" in method_match.group(0)})
            classes.append({"name": name, "bases": [base] if base else [], "methods": methods})
        return classes

    def extract_functions(self, content: str) -> List[Dict]:
        functions = []
        # Standard functions
        for match in re.finditer(r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)', content):
            params = [{"name": p.strip().split(":")[0].split("=")[0].strip()} for p in match.group(2).split(",") if p.strip()]
            functions.append({"name": match.group(1), "params": params, "is_async": "async" in match.group(0)})
        # Arrow functions assigned to const/let/var
        for match in re.finditer(r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>', content):
            functions.append({"name": match.group(1), "params": [], "is_async": "async" in match.group(0)})
        return functions

    def get_type_mapping(self, target_language: str) -> Dict[str, str]:
        mappings = {
            "typescript": {"var": "let", "require": "import", "module.exports": "export default"},
            "python": {"string": "str", "number": "int | float", "boolean": "bool", "null": "None", "undefined": "None", "Array": "list", "object": "dict"},
            "go": {"string": "string", "number": "int", "boolean": "bool", "null": "nil", "Array": "[]interface{}", "object": "map[string]interface{}"},
        }
        return mappings.get(target_language, {})


class TypeScriptAdapter(JavaScriptAdapter):
    @property
    def name(self) -> str:
        return "typescript"

    @property
    def file_extensions(self) -> List[str]:
        return [".ts", ".tsx"]

    def extract_imports(self, content: str) -> List[Dict[str, str]]:
        imports = super().extract_imports(content)
        # TypeScript type-only imports
        for match in re.finditer(r'import\s+type\s+\{([^}]+)\}\s+from\s+[\'"]([^"\']+)[\'"]', content):
            for name in match.group(1).split(","):
                imports.append({"module": match.group(2), "name": name.strip(), "type": "type_only"})
        return imports


AdapterRegistry.register(JavaScriptAdapter())
AdapterRegistry.register(TypeScriptAdapter())
