"""
Unit tests for the Code Analyzer module.
"""
import pytest
from src.models.config import RepoFile, FileType, MigrationConfig
from src.analysis.code_analyzer import CodebaseAnalyzer


@pytest.fixture
def config():
    return MigrationConfig(repo_url="https://github.com/test/repo", target_language="typescript")


@pytest.fixture
def sample_files():
    return [
        RepoFile(
            path="src/index.js",
            content='const express = require("express");\nconst app = express();\nconst router = require("./routes/api");\napp.use("/api", router);\napp.listen(3000);',
            language="javascript",
            file_type=FileType.SOURCE,
        ),
        RepoFile(
            path="src/routes/api.js",
            content='const express = require("express");\nconst { getUsers } = require("../services/userService");\nconst router = express.Router();\nrouter.get("/users", getUsers);\nmodule.exports = router;',
            language="javascript",
            file_type=FileType.SOURCE,
        ),
        RepoFile(
            path="src/services/userService.js",
            content='const { db } = require("../db/connection");\nfunction getUsers(req, res) {\n  if (req.query.active) {\n    return res.json(db.users.filter(u => u.active));\n  }\n  return res.json(db.users);\n}\nmodule.exports = { getUsers };',
            language="javascript",
            file_type=FileType.SOURCE,
        ),
        RepoFile(
            path="src/db/connection.js",
            content='const db = { users: [] };\nmodule.exports = { db };',
            language="javascript",
            file_type=FileType.SOURCE,
        ),
        RepoFile(
            path="tests/userService.test.js",
            content='const { getUsers } = require("../src/services/userService");\ndescribe("getUsers", () => {\n  it("should return users", () => {});\n});',
            language="javascript",
            file_type=FileType.TEST,
        ),
    ]


class TestLanguageDetection:
    def test_detects_javascript(self, config, sample_files):
        analyzer = CodebaseAnalyzer(config)
        result = analyzer.analyze(sample_files)
        assert "javascript" in result.languages

    def test_language_order_by_frequency(self, config, sample_files):
        analyzer = CodebaseAnalyzer(config)
        result = analyzer.analyze(sample_files)
        assert result.languages[0] == "javascript"


class TestDependencyGraph:
    def test_builds_dependency_edges(self, config, sample_files):
        analyzer = CodebaseAnalyzer(config)
        result = analyzer.analyze(sample_files)
        assert len(result.dependency_graph) > 0

    def test_detects_express_framework(self, config, sample_files):
        analyzer = CodebaseAnalyzer(config)
        result = analyzer.analyze(sample_files)
        assert result.framework_detected == "express"


class TestEntryPoints:
    def test_finds_index_as_entry(self, config, sample_files):
        analyzer = CodebaseAnalyzer(config)
        result = analyzer.analyze(sample_files)
        assert any("index.js" in ep for ep in result.entry_points)


class TestComplexity:
    def test_complexity_is_positive(self, config, sample_files):
        analyzer = CodebaseAnalyzer(config)
        result = analyzer.analyze(sample_files)
        assert result.avg_complexity >= 0


class TestModuleGrouping:
    def test_groups_by_directory(self, config, sample_files):
        analyzer = CodebaseAnalyzer(config)
        result = analyzer.analyze(sample_files)
        assert "src" in result.module_groups
        assert "tests" in result.module_groups
