"""
Integration test for the full migration pipeline.
Tests the end-to-end flow: Ingest → Analyze → Migrate → Validate → Output.
"""
import pytest
import os
import tempfile
from src.models.config import MigrationConfig, RepoFile, FileType
from src.analysis.code_analyzer import CodebaseAnalyzer
from src.validation.dependency_validator import DependencyValidator
from src.diff.diff_engine import DiffEngine
from src.ai.cache.semantic_cache import SemanticCache
from src.rollback.rollback_manager import RollbackManager
from src.observability.logger import MigrationLogger, MetricsCollector
from src.plugins.hooks.hook_system import HookRegistry, HookPhase
from src.plugins.adapters.python_adapter import PythonAdapter
from src.plugins.adapters.javascript_adapter import JavaScriptAdapter


class TestPythonAdapter:
    def test_extract_imports_from_ast(self):
        adapter = PythonAdapter()
        code = """
import os
import json
from typing import List, Dict
from src.models.config import MigrationConfig
from ..utils import helper
"""
        imports = adapter.extract_imports(code)
        assert len(imports) >= 4
        modules = [i["module"] for i in imports]
        assert "os" in modules
        assert "typing" in modules

    def test_extract_classes(self):
        adapter = PythonAdapter()
        code = """
class MyService:
    def __init__(self, db):
        self.db = db

    async def get_users(self) -> list:
        return []

    def _private_method(self):
        pass
"""
        classes = adapter.extract_classes(code)
        assert len(classes) == 1
        assert classes[0]["name"] == "MyService"
        assert len(classes[0]["methods"]) == 3

    def test_extract_functions(self):
        adapter = PythonAdapter()
        code = """
def process_data(input_file: str, output_dir: str) -> bool:
    \"\"\"Process the data file.\"\"\"
    return True

async def fetch_remote(url: str) -> dict:
    pass
"""
        functions = adapter.extract_functions(code)
        assert len(functions) == 2
        assert functions[0]["name"] == "process_data"
        assert functions[0]["docstring"] == "Process the data file."
        assert functions[1]["is_async"] is True

    def test_type_mapping_to_typescript(self):
        adapter = PythonAdapter()
        mapping = adapter.get_type_mapping("typescript")
        assert mapping["str"] == "string"
        assert mapping["int"] == "number"
        assert mapping["dict"] == "Record"


class TestJavaScriptAdapter:
    def test_extract_es6_imports(self):
        adapter = JavaScriptAdapter()
        code = """
import React from 'react';
import { useState, useEffect } from 'react';
import axios from 'axios';
"""
        imports = adapter.extract_imports(code)
        assert len(imports) >= 3

    def test_extract_commonjs_requires(self):
        adapter = JavaScriptAdapter()
        code = """
const express = require('express');
const { Router } = require('express');
const path = require('path');
"""
        imports = adapter.extract_imports(code)
        assert len(imports) >= 3

    def test_extract_exports(self):
        adapter = JavaScriptAdapter()
        code = """
export const API_URL = 'http://localhost';
export function handleRequest(req, res) {}
export default class AppController {}
module.exports = { helper, utils };
"""
        exports = adapter.extract_exports(code)
        assert len(exports) >= 4


class TestSemanticCache:
    def test_cache_hit(self):
        cache = SemanticCache(max_size=10)
        cache.set("key1", "response1")
        assert cache.get("key1") == "response1"

    def test_cache_miss(self):
        cache = SemanticCache()
        assert cache.get("nonexistent") is None

    def test_lru_eviction(self):
        cache = SemanticCache(max_size=2)
        cache.set("a", "1")
        cache.set("b", "2")
        cache.set("c", "3")  # Should evict "a"
        assert cache.get("a") is None
        assert cache.get("b") == "2"
        assert cache.get("c") == "3"

    def test_stats(self):
        cache = SemanticCache()
        cache.set("k", "v")
        cache.get("k")  # hit
        cache.get("miss")  # miss
        stats = cache.stats
        assert stats["hits"] == 1
        assert stats["misses"] == 1


class TestDiffEngine:
    def test_generates_diff(self):
        from src.models.config import MigratedFile
        engine = DiffEngine()
        file = MigratedFile(
            original_path="app.py",
            new_path="app.ts",
            original_content="def hello():\n    print('hello')\n",
            migrated_content="function hello(): void {\n    console.log('hello');\n}\n",
            target_language="typescript",
            confidence_score=0.95,
        )
        result = engine.generate_diff(file)
        assert result.lines_added > 0
        assert result.lines_removed > 0
        assert 0.0 <= result.change_ratio <= 1.0


class TestHookSystem:
    def test_register_and_execute_hook(self):
        registry = HookRegistry()
        called = {"value": False}

        def my_hook(context):
            called["value"] = True
            return {"processed": True}

        registry.register("test_hook", HookPhase.POST_MIGRATION, my_hook)
        results = registry.execute(HookPhase.POST_MIGRATION)

        assert len(results) == 1
        assert results[0].success is True
        assert called["value"] is True

    def test_hooks_execute_in_priority_order(self):
        registry = HookRegistry()
        order = []

        registry.register("second", HookPhase.PRE_ANALYSIS, lambda ctx: order.append("second"), priority=200)
        registry.register("first", HookPhase.PRE_ANALYSIS, lambda ctx: order.append("first"), priority=100)

        registry.execute(HookPhase.PRE_ANALYSIS)
        assert order == ["first", "second"]


class TestObservability:
    def test_metrics_counter(self):
        metrics = MetricsCollector()
        metrics.increment("files_translated")
        metrics.increment("files_translated")
        assert metrics.counters["files_translated"] == 2.0

    def test_logger_span(self):
        logger = MigrationLogger(run_id="test-123")
        with logger.span("test_operation", file="test.py"):
            pass
        trace = logger.get_trace()
        assert len(trace) == 1
        assert trace[0]["operation"] == "test_operation"
        assert trace[0]["status"] == "ok"


class TestRollbackManager:
    def test_create_and_list_points(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = os.path.join(tmpdir, "source")
            os.makedirs(source)
            with open(os.path.join(source, "test.txt"), "w") as f:
                f.write("hello")

            manager = RollbackManager(rollback_dir=os.path.join(tmpdir, "rollbacks"))
            point = manager.create_rollback_point("phase1", source, "Before migration")

            assert len(manager.list_points()) == 1
            assert point.file_count == 1
