"""
Test Suite — Part 1: Code Ingestion, AST & Static Analysis Engine
==================================================================
"""
import os
import tempfile
import zipfile
import textwrap
import pytest

from backend.app.part1_parser.ingestion import (
    RepoIngestor, FileNode, detect_language,
    is_ignored_dir, is_binary_file,
)
from backend.app.part1_parser.ast_analyzer import (
    ASTAnalyzer, PythonASTParser, DependencyMapper, FileAnalysis,
)
from backend.app.part1_parser.static_scanner import (
    StaticSecurityScanner, StaticCodeAnalyzer, UnifiedScanner, Finding,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Ingestion Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestLanguageDetection:
    def test_python_extension(self):
        assert detect_language("app/main.py") == "python"

    def test_javascript_extension(self):
        assert detect_language("src/index.js") == "javascript"

    def test_typescript_extension(self):
        assert detect_language("src/App.tsx") == "typescript"

    def test_java_extension(self):
        assert detect_language("Main.java") == "java"

    def test_cpp_extension(self):
        assert detect_language("solver.cpp") == "cpp"

    def test_go_extension(self):
        assert detect_language("main.go") == "go"

    def test_unknown_extension(self):
        assert detect_language("README") is None

    def test_dockerfile_detection(self):
        assert detect_language("Dockerfile") == "dockerfile"


class TestIgnoredDirectories:
    def test_git_ignored(self):
        assert is_ignored_dir(".git") is True

    def test_node_modules_ignored(self):
        assert is_ignored_dir("node_modules") is True

    def test_venv_ignored(self):
        assert is_ignored_dir("venv") is True

    def test_normal_dir_not_ignored(self):
        assert is_ignored_dir("backend") is False

    def test_dotdir_ignored(self):
        assert is_ignored_dir(".mypy_cache") is True


class TestBinaryFileDetection:
    def test_png_is_binary(self):
        assert is_binary_file("logo.png") is True

    def test_py_is_not_binary(self):
        assert is_binary_file("main.py") is False

    def test_zip_is_binary(self):
        assert is_binary_file("archive.zip") is True


class TestRepoIngestorLocal:
    def test_ingest_local_directory(self, tmp_path):
        # Create a small mock repo
        (tmp_path / "main.py").write_text("print('hello')\n", encoding="utf-8")
        (tmp_path / "utils.py").write_text("def helper(): pass\n", encoding="utf-8")
        sub = tmp_path / "lib"
        sub.mkdir()
        (sub / "core.py").write_text("x = 1\n", encoding="utf-8")

        ingestor = RepoIngestor()
        ingestor.from_local(str(tmp_path))

        assert len(ingestor.file_tree) >= 3
        assert ingestor.source_type == "local"
        assert ingestor.total_lines >= 3

        manifest = ingestor.manifest()
        assert manifest["status"] == "success"
        assert manifest["total_files"] >= 3

    def test_language_stats(self, tmp_path):
        (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
        (tmp_path / "b.py").write_text("y = 2\n", encoding="utf-8")
        (tmp_path / "c.js").write_text("const z = 3;\n", encoding="utf-8")

        ingestor = RepoIngestor()
        ingestor.from_local(str(tmp_path))

        stats = ingestor.language_stats
        assert stats.get("python", 0) == 2
        assert stats.get("javascript", 0) == 1

    def test_get_files_by_language(self, tmp_path):
        (tmp_path / "a.py").write_text("x=1\n", encoding="utf-8")
        (tmp_path / "b.js").write_text("x=1\n", encoding="utf-8")

        ingestor = RepoIngestor()
        ingestor.from_local(str(tmp_path))

        py_files = ingestor.get_files_by_language("python")
        assert len(py_files) == 1
        assert py_files[0].language == "python"

    def test_invalid_directory_raises(self):
        ingestor = RepoIngestor()
        with pytest.raises(FileNotFoundError):
            ingestor.from_local("/this/path/does/not/exist")


class TestRepoIngestorZip:
    def test_ingest_zip_archive(self, tmp_path):
        # Create files and zip them
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "app.py").write_text("print('app')\n", encoding="utf-8")
        (src_dir / "util.py").write_text("def util(): pass\n", encoding="utf-8")

        zip_path = str(tmp_path / "repo.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            for f in src_dir.iterdir():
                zf.write(f, arcname=f"project/{f.name}")

        ingestor = RepoIngestor()
        ingestor.from_zip(zip_path)

        assert ingestor.source_type == "zip"
        assert len(ingestor.file_tree) >= 2
        ingestor.cleanup()

    def test_invalid_zip_raises(self, tmp_path):
        bad_file = tmp_path / "not_a_zip.txt"
        bad_file.write_text("hello", encoding="utf-8")

        ingestor = RepoIngestor()
        with pytest.raises(ValueError, match="Not a valid ZIP"):
            ingestor.from_zip(str(bad_file))


class TestFileNode:
    def test_file_node_metadata(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("line1\nline2\nline3\n", encoding="utf-8")

        node = FileNode(str(f), str(tmp_path))
        assert node.language == "python"
        assert node.line_count == 3
        assert node.size_bytes > 0
        assert len(node.sha256) == 64  # SHA-256 hex digest

        d = node.to_dict()
        assert "path" in d
        assert d["language"] == "python"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  AST Analyzer Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestPythonASTParser:
    def test_parse_functions(self):
        code = textwrap.dedent("""\
            def greet(name: str) -> str:
                \"\"\"Say hello.\"\"\"
                return f"Hello {name}"

            async def fetch_data(url):
                pass
        """)
        parser = PythonASTParser()
        result = parser.parse(code)

        assert result.valid is True
        assert len(result.functions) == 2

        greet = result.functions[0]
        assert greet.name == "greet"
        assert "name" in greet.args
        assert greet.return_annotation == "str"
        assert greet.docstring == "Say hello."
        assert greet.is_async is False

        fetch = result.functions[1]
        assert fetch.name == "fetch_data"
        assert fetch.is_async is True

    def test_parse_classes_with_inheritance(self):
        code = textwrap.dedent("""\
            class Animal:
                \"\"\"Base animal class.\"\"\"
                def speak(self):
                    pass

            class Dog(Animal):
                def speak(self):
                    return "Woof"

                def fetch(self, item):
                    pass
        """)
        parser = PythonASTParser()
        result = parser.parse(code)

        assert len(result.classes) == 2
        animal = result.classes[0]
        assert animal.name == "Animal"
        assert animal.bases == []
        assert "speak" in animal.methods
        assert animal.docstring == "Base animal class."

        dog = result.classes[1]
        assert dog.name == "Dog"
        assert "Animal" in dog.bases
        assert "speak" in dog.methods
        assert "fetch" in dog.methods

    def test_parse_imports(self):
        code = textwrap.dedent("""\
            import os
            import sys
            from pathlib import Path
            from typing import List, Dict
        """)
        parser = PythonASTParser()
        result = parser.parse(code)

        assert result.valid is True
        modules = [i.module for i in result.imports]
        assert "os" in modules
        assert "sys" in modules
        assert "pathlib" in modules
        assert "typing" in modules

        # Check from-import names
        typing_imp = [i for i in result.imports if i.module == "typing"][0]
        assert "List" in typing_imp.names
        assert "Dict" in typing_imp.names
        assert typing_imp.is_from_import is True

    def test_parse_module_variables(self):
        code = textwrap.dedent("""\
            MAX_RETRIES = 3
            DEFAULT_TIMEOUT: int = 30
            app_name = "RepoGuard"
        """)
        parser = PythonASTParser()
        result = parser.parse(code)

        names = [v.name for v in result.variables]
        assert "MAX_RETRIES" in names
        assert "DEFAULT_TIMEOUT" in names
        assert "app_name" in names

        max_r = [v for v in result.variables if v.name == "MAX_RETRIES"][0]
        assert max_r.is_constant is True

        timeout = [v for v in result.variables if v.name == "DEFAULT_TIMEOUT"][0]
        assert timeout.annotation == "int"

    def test_syntax_error_returns_invalid(self):
        code = "def broken(:\n    pass"
        parser = PythonASTParser()
        result = parser.parse(code)

        assert result.valid is False
        assert "SyntaxError" in result.error

    def test_decorators_extracted(self):
        code = textwrap.dedent("""\
            import functools

            @staticmethod
            def helper():
                pass

            @functools.lru_cache
            def cached():
                pass
        """)
        parser = PythonASTParser()
        result = parser.parse(code)

        helper = [f for f in result.functions if f.name == "helper"][0]
        assert "staticmethod" in helper.decorators


class TestASTAnalyzerUnified:
    def test_analyze_python_code(self):
        analyzer = ASTAnalyzer()
        code = "def foo(): pass\nclass Bar: pass\n"
        result = analyzer.analyze_code(code, "python", "test.py")

        assert result.valid is True
        assert len(result.functions) == 1
        assert len(result.classes) == 1

    def test_supported_languages_includes_python(self):
        analyzer = ASTAnalyzer()
        assert "python" in analyzer.supported_languages

    def test_unsupported_language_returns_error(self):
        analyzer = ASTAnalyzer()
        result = analyzer.analyze_code("code", "brainfuck", "test.bf")
        assert result.valid is False

    def test_legacy_parse_python_code(self):
        analyzer = ASTAnalyzer()
        result = analyzer.parse_python_code("def sample_function():\n    pass\n")
        assert result["valid"] is True
        assert "sample_function" in result["functions"]

    def test_analyze_file_from_disk(self, tmp_path):
        f = tmp_path / "mod.py"
        f.write_text("class Engine:\n    def run(self): pass\n", encoding="utf-8")

        analyzer = ASTAnalyzer()
        result = analyzer.analyze_file(str(f), "python")

        assert result.valid is True
        assert len(result.classes) == 1
        assert result.classes[0].name == "Engine"

    def test_file_analysis_serialisation(self):
        analyzer = ASTAnalyzer()
        code = "import os\ndef hello(): pass\n"
        result = analyzer.analyze_code(code, "python", "hello.py")
        d = result.to_dict()

        assert d["filepath"] == "hello.py"
        assert d["language"] == "python"
        assert d["summary"]["function_count"] == 1
        assert d["summary"]["import_count"] == 1


class TestDependencyMapper:
    def test_build_dependency_edges(self):
        fa1 = FileAnalysis(filepath="a.py", language="python")
        from backend.app.part1_parser.ast_analyzer import ImportSymbol
        fa1.imports = [
            ImportSymbol(module="os", names=["os"], line=1),
            ImportSymbol(module="b", names=["b"], is_from_import=True, line=2),
        ]
        fa2 = FileAnalysis(filepath="b.py", language="python")
        fa2.imports = [
            ImportSymbol(module="sys", names=["sys"], line=1),
        ]

        mapper = DependencyMapper()
        summary = mapper.build_from_analyses([fa1, fa2])

        assert summary["total_dependencies"] == 3
        assert summary["internal_dependencies"] >= 1  # b is internal
        assert isinstance(summary["edges"], list)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Static Scanner Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestStaticSecurityScanner:
    def setup_method(self):
        self.scanner = StaticSecurityScanner()

    def test_detects_hardcoded_api_key(self):
        code = 'api_key = "sk_live_abcdefghijklmnop1234"'
        findings = self.scanner.scan_code(code, "config.py")
        types = [f.type for f in findings]
        assert any("API Key" in t or "Secret" in t or "Token" in t for t in types)

    def test_detects_hardcoded_password(self):
        code = 'password = "super_secret_pass"'
        findings = self.scanner.scan_code(code, "auth.py")
        types = [f.type for f in findings]
        assert "Hardcoded Password" in types

    def test_detects_aws_access_key(self):
        code = 'aws_key = "AKIAIOSFODNN7EXAMPLE"'
        findings = self.scanner.scan_code(code, "deploy.py")
        types = [f.type for f in findings]
        assert "AWS Access Key ID" in types

    def test_detects_sql_injection(self):
        code = 'cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")'
        findings = self.scanner.scan_code(code, "db.py")
        types = [f.type for f in findings]
        assert any("SQL Injection" in t for t in types)

    def test_detects_command_injection_os_system(self):
        code = 'os.system("rm -rf " + user_input)'
        findings = self.scanner.scan_code(code, "cleanup.py")
        types = [f.type for f in findings]
        assert any("Command Injection" in t or "os.system" in t for t in types)

    def test_detects_eval(self):
        code = 'result = eval(user_input)'
        findings = self.scanner.scan_code(code, "parser.py")
        types = [f.type for f in findings]
        assert any("eval" in t for t in types)

    def test_detects_unsafe_pickle(self):
        code = 'data = pickle.loads(raw_bytes)'
        findings = self.scanner.scan_code(code, "loader.py")
        types = [f.type for f in findings]
        assert any("pickle" in t for t in types)

    def test_detects_unsafe_yaml(self):
        code = 'config = yaml.load(file_content)'
        findings = self.scanner.scan_code(code, "config.py")
        types = [f.type for f in findings]
        assert any("YAML" in t or "yaml" in t for t in types)

    def test_detects_weak_crypto_md5(self):
        code = 'digest = hashlib.md5(data)'
        findings = self.scanner.scan_code(code, "hash.py")
        types = [f.type for f in findings]
        assert any("MD5" in t for t in types)

    def test_detects_ssl_verify_false(self):
        code = 'requests.get(url, verify=False)'
        findings = self.scanner.scan_code(code, "http.py")
        types = [f.type for f in findings]
        assert any("SSL" in t or "TLS" in t for t in types)

    def test_clean_code_no_findings(self):
        code = textwrap.dedent("""\
            import os

            def get_env_key():
                return os.environ.get("API_KEY")
        """)
        findings = self.scanner.scan_code(code, "clean.py")
        security_findings = [f for f in findings if f.category == "security"]
        assert len(security_findings) == 0

    def test_findings_have_cwe(self):
        code = 'password = "letmein123"'
        findings = self.scanner.scan_code(code, "test.py")
        if findings:
            assert findings[0].cwe is not None

    def test_findings_sorted_by_severity(self):
        code = textwrap.dedent("""\
            password = "secret123"
            cursor.execute(f"SELECT * FROM t WHERE id = {x}")
            digest = hashlib.md5(data)
        """)
        findings = self.scanner.scan_code(code, "mixed.py")
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
        for i in range(len(findings) - 1):
            assert severity_order.get(findings[i].severity, 5) <= severity_order.get(findings[i + 1].severity, 5)


class TestStaticCodeAnalyzer:
    def setup_method(self):
        self.analyzer = StaticCodeAnalyzer(
            max_function_lines=10,
            max_nesting_depth=3,
            max_complexity=5,
        )

    def test_detects_unreachable_code(self):
        code = textwrap.dedent("""\
            def example():
                return 42
                    print("never reached")
        """)
        findings = self.analyzer.analyze_code(code, "dead.py")
        types = [f.type for f in findings]
        assert "Unreachable Code" in types

    def test_detects_long_function(self):
        lines = ["def long_function():"]
        for i in range(20):
            lines.append(f"    x_{i} = {i}")
        code = "\n".join(lines)

        findings = self.analyzer.analyze_code(code, "long.py")
        types = [f.type for f in findings]
        assert "Long Function" in types

    def test_detects_deep_nesting(self):
        code = textwrap.dedent("""\
            def nested():
                if True:
                    if True:
                        if True:
                            if True:
                                print("too deep")
        """)
        findings = self.analyzer.analyze_code(code, "deep.py")
        types = [f.type for f in findings]
        assert "Deep Nesting" in types

    def test_detects_naming_violation_function(self):
        code = "def BadFunctionName(): pass\n"
        findings = self.analyzer.analyze_code(code, "naming.py")
        types = [f.type for f in findings]
        assert "Naming Convention Violation" in types

    def test_detects_naming_violation_class(self):
        code = "class bad_class_name: pass\n"
        findings = self.analyzer.analyze_code(code, "naming.py")
        types = [f.type for f in findings]
        assert "Naming Convention Violation" in types

    def test_clean_code_passes(self):
        code = textwrap.dedent("""\
            def short_func():
                return 1

            class GoodClass:
                pass
        """)
        findings = self.analyzer.analyze_code(code, "clean.py")
        # Should have no serious findings
        real_findings = [f for f in findings if f.severity in ("CRITICAL", "HIGH", "MEDIUM")]
        assert len(real_findings) == 0


class TestUnifiedScanner:
    def test_aggregated_report(self):
        code = textwrap.dedent("""\
            password = "admin123"

            def very_long_function():
                x1 = 1
                x2 = 2
                x3 = 3
                x4 = 4
                x5 = 5
                x6 = 6
                x7 = 7
                x8 = 8
                x9 = 9
                x10 = 10
                x11 = 11
                return x11
        """)
        scanner = UnifiedScanner(max_function_lines=10)
        report = scanner.scan_code(code, "mixed.py")

        assert report["total_findings"] > 0
        assert "security_findings" in report
        assert "quality_findings" in report
        assert "health_score" in report
        assert 0 <= report["health_score"] <= 100

    def test_health_score_perfect_on_clean_code(self):
        code = "x = 1\n"
        scanner = UnifiedScanner()
        report = scanner.scan_code(code, "clean.py")
        assert report["health_score"] == 100.0

    def test_scan_file_from_disk(self, tmp_path):
        f = tmp_path / "vuln.py"
        f.write_text('api_key = "AKIAIOSFODNN7EXAMPLEX"\n', encoding="utf-8")

        scanner = UnifiedScanner()
        report = scanner.scan_file(str(f))
        assert report["total_findings"] > 0


class TestFinding:
    def test_finding_to_dict(self):
        f = Finding(
            file="test.py", line=10,
            type="Hardcoded Secret", severity="HIGH",
            category="security",
            description="Secret found.",
            evidence="api_key = 'abc'",
            cwe="CWE-798",
            fix_suggestion="Use env vars.",
        )
        d = f.to_dict()
        assert d["file"] == "test.py"
        assert d["cwe"] == "CWE-798"
        assert d["fix_suggestion"] == "Use env vars."
