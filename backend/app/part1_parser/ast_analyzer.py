"""
Part 1 — AST Analyzer & Multi-Language Symbol Extractor
========================================================
Extracts structural symbols from source code files:
  • Functions / methods (name, args, decorators, line span, docstring)
  • Classes (name, bases / inheritance, methods, line span)
  • Imports (module, alias, from-import targets)
  • Variables & constants at module scope
  • Cross-file dependency mapping (import graph edges)

Supports two parsing backends:
  1. Python ``ast`` module   — native, zero-dependency Python parsing
  2. Tree-sitter             — multi-language parsing for JS/TS/Java/C++/Go

If tree-sitter is not installed, the analyser gracefully falls back to
Python-only mode and logs a warning.
"""

import ast
import os
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger("repoguard.part1.ast_analyzer")

# ── Try importing Tree-sitter (optional dependency) ──
try:
    import tree_sitter_languages
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    logger.info("tree-sitter-languages not installed — multi-language AST disabled; Python-only mode active.")


# ══════════════════════════════════════════════
#  Data classes for extracted symbols
# ══════════════════════════════════════════════

@dataclass
class FunctionSymbol:
    name: str
    args: List[str] = field(default_factory=list)
    decorators: List[str] = field(default_factory=list)
    return_annotation: Optional[str] = None
    docstring: Optional[str] = None
    start_line: int = 0
    end_line: int = 0
    line_count: int = 0
    is_method: bool = False
    is_async: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "args": self.args,
            "decorators": self.decorators,
            "return_annotation": self.return_annotation,
            "docstring": self.docstring,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "line_count": self.line_count,
            "is_method": self.is_method,
            "is_async": self.is_async,
        }


@dataclass
class ClassSymbol:
    name: str
    bases: List[str] = field(default_factory=list)
    methods: List[str] = field(default_factory=list)
    decorators: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    start_line: int = 0
    end_line: int = 0
    line_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "bases": self.bases,
            "methods": self.methods,
            "decorators": self.decorators,
            "docstring": self.docstring,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "line_count": self.line_count,
        }


@dataclass
class ImportSymbol:
    module: Optional[str]
    names: List[str] = field(default_factory=list)
    alias: Optional[str] = None
    is_from_import: bool = False
    line: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module": self.module,
            "names": self.names,
            "alias": self.alias,
            "is_from_import": self.is_from_import,
            "line": self.line,
        }


@dataclass
class VariableSymbol:
    name: str
    annotation: Optional[str] = None
    line: int = 0
    is_constant: bool = False  # ALL_CAPS naming convention

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "annotation": self.annotation,
            "line": self.line,
            "is_constant": self.is_constant,
        }


@dataclass
class FileAnalysis:
    """Complete analysis result for a single source file."""
    filepath: str
    language: str
    valid: bool = True
    error: Optional[str] = None
    functions: List[FunctionSymbol] = field(default_factory=list)
    classes: List[ClassSymbol] = field(default_factory=list)
    imports: List[ImportSymbol] = field(default_factory=list)
    variables: List[VariableSymbol] = field(default_factory=list)
    total_lines: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filepath": self.filepath,
            "language": self.language,
            "valid": self.valid,
            "error": self.error,
            "total_lines": self.total_lines,
            "functions": [f.to_dict() for f in self.functions],
            "classes": [c.to_dict() for c in self.classes],
            "imports": [i.to_dict() for i in self.imports],
            "variables": [v.to_dict() for v in self.variables],
            "summary": {
                "function_count": len(self.functions),
                "class_count": len(self.classes),
                "import_count": len(self.imports),
                "variable_count": len(self.variables),
            },
        }


# ══════════════════════════════════════════════
#  Python AST Parser  (native, always available)
# ══════════════════════════════════════════════

class PythonASTParser:
    """Deep Python AST analysis using the built-in ``ast`` module."""

    def parse(self, code: str, filepath: str = "<string>") -> FileAnalysis:
        result = FileAnalysis(filepath=filepath, language="python")
        result.total_lines = len(code.splitlines())

        try:
            tree = ast.parse(code, filename=filepath)
        except SyntaxError as exc:
            result.valid = False
            result.error = f"SyntaxError at line {exc.lineno}: {exc.msg}"
            return result

        result.functions = self._extract_functions(tree)
        result.classes = self._extract_classes(tree)
        result.imports = self._extract_imports(tree)
        result.variables = self._extract_variables(tree)
        return result

    # ── functions / methods ───────────────────

    @staticmethod
    def _extract_functions(tree: ast.Module) -> List[FunctionSymbol]:
        functions: List[FunctionSymbol] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Determine if this is a method (inside a ClassDef)
                is_method = False
                for potential_class in ast.walk(tree):
                    if isinstance(potential_class, ast.ClassDef):
                        if node in ast.iter_child_nodes(potential_class):
                            is_method = True
                            break

                args = []
                for arg in node.args.args:
                    args.append(arg.arg)

                decorators = []
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Name):
                        decorators.append(dec.id)
                    elif isinstance(dec, ast.Attribute):
                        decorators.append(ast.dump(dec))
                    elif isinstance(dec, ast.Call):
                        if isinstance(dec.func, ast.Name):
                            decorators.append(dec.func.id)

                return_ann = None
                if node.returns:
                    try:
                        return_ann = ast.unparse(node.returns)
                    except Exception:
                        return_ann = str(node.returns)

                docstring = ast.get_docstring(node)

                end_line = getattr(node, "end_lineno", node.lineno)
                functions.append(FunctionSymbol(
                    name=node.name,
                    args=args,
                    decorators=decorators,
                    return_annotation=return_ann,
                    docstring=docstring,
                    start_line=node.lineno,
                    end_line=end_line,
                    line_count=end_line - node.lineno + 1,
                    is_method=is_method,
                    is_async=isinstance(node, ast.AsyncFunctionDef),
                ))
        return functions

    # ── classes ───────────────────────────────

    @staticmethod
    def _extract_classes(tree: ast.Module) -> List[ClassSymbol]:
        classes: List[ClassSymbol] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases = []
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        bases.append(base.id)
                    elif isinstance(base, ast.Attribute):
                        try:
                            bases.append(ast.unparse(base))
                        except Exception:
                            bases.append(str(base))

                methods = []
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        methods.append(item.name)

                decorators = []
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Name):
                        decorators.append(dec.id)

                docstring = ast.get_docstring(node)
                end_line = getattr(node, "end_lineno", node.lineno)

                classes.append(ClassSymbol(
                    name=node.name,
                    bases=bases,
                    methods=methods,
                    decorators=decorators,
                    docstring=docstring,
                    start_line=node.lineno,
                    end_line=end_line,
                    line_count=end_line - node.lineno + 1,
                ))
        return classes

    # ── imports ───────────────────────────────

    @staticmethod
    def _extract_imports(tree: ast.Module) -> List[ImportSymbol]:
        imports: List[ImportSymbol] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(ImportSymbol(
                        module=alias.name,
                        names=[alias.name],
                        alias=alias.asname,
                        is_from_import=False,
                        line=node.lineno,
                    ))
            elif isinstance(node, ast.ImportFrom):
                names = [a.name for a in node.names]
                imports.append(ImportSymbol(
                    module=node.module,
                    names=names,
                    is_from_import=True,
                    line=node.lineno,
                ))
        return imports

    # ── module-level variables ────────────────

    @staticmethod
    def _extract_variables(tree: ast.Module) -> List[VariableSymbol]:
        variables: List[VariableSymbol] = []
        for node in ast.iter_child_nodes(tree):
            # x = ...
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        variables.append(VariableSymbol(
                            name=target.id,
                            line=node.lineno,
                            is_constant=target.id.isupper(),
                        ))
            # x: int = ...
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                ann = None
                try:
                    ann = ast.unparse(node.annotation)
                except Exception:
                    pass
                variables.append(VariableSymbol(
                    name=node.target.id,
                    annotation=ann,
                    line=node.lineno,
                    is_constant=node.target.id.isupper(),
                ))
        return variables


# ══════════════════════════════════════════════
#  Tree-sitter Multi-Language Parser
# ══════════════════════════════════════════════

# Tree-sitter node type → symbol queries per language
_TS_LANGUAGE_QUERIES: Dict[str, Dict[str, List[str]]] = {
    "javascript": {
        "function_types": ["function_declaration", "arrow_function", "method_definition"],
        "class_types":    ["class_declaration"],
        "import_types":   ["import_statement"],
        "variable_types": ["variable_declaration", "lexical_declaration"],
    },
    "typescript": {
        "function_types": ["function_declaration", "arrow_function", "method_definition"],
        "class_types":    ["class_declaration"],
        "import_types":   ["import_statement"],
        "variable_types": ["variable_declaration", "lexical_declaration"],
    },
    "java": {
        "function_types": ["method_declaration", "constructor_declaration"],
        "class_types":    ["class_declaration", "interface_declaration"],
        "import_types":   ["import_declaration"],
        "variable_types": ["field_declaration", "local_variable_declaration"],
    },
    "cpp": {
        "function_types": ["function_definition"],
        "class_types":    ["class_specifier", "struct_specifier"],
        "import_types":   ["preproc_include"],
        "variable_types": ["declaration"],
    },
    "go": {
        "function_types": ["function_declaration", "method_declaration"],
        "class_types":    ["type_declaration"],
        "import_types":   ["import_declaration"],
        "variable_types": ["var_declaration", "const_declaration", "short_var_declaration"],
    },
}


class TreeSitterParser:
    """
    Multi-language AST parser backed by tree-sitter.
    Extracts functions, classes, imports, and variables from
    JavaScript, TypeScript, Java, C++, and Go source files.
    """

    SUPPORTED_LANGUAGES = frozenset(_TS_LANGUAGE_QUERIES.keys())

    def __init__(self):
        if not TREE_SITTER_AVAILABLE:
            raise ImportError(
                "tree-sitter-languages is required for multi-language parsing. "
                "Install with: pip install tree-sitter-languages"
            )

    def parse(self, code: str, language: str, filepath: str = "<string>") -> FileAnalysis:
        result = FileAnalysis(filepath=filepath, language=language)
        result.total_lines = len(code.splitlines())

        if language not in self.SUPPORTED_LANGUAGES:
            result.valid = False
            result.error = f"Unsupported language for Tree-sitter: {language}"
            return result

        try:
            parser = tree_sitter_languages.get_parser(language)
            tree = parser.parse(code.encode("utf-8"))
        except Exception as exc:
            result.valid = False
            result.error = f"Tree-sitter parse error: {exc}"
            return result

        queries = _TS_LANGUAGE_QUERIES[language]
        root_node = tree.root_node

        result.functions = self._extract_nodes_as_functions(root_node, queries["function_types"], code)
        result.classes = self._extract_nodes_as_classes(root_node, queries["class_types"], code)
        result.imports = self._extract_nodes_as_imports(root_node, queries["import_types"], code)
        result.variables = self._extract_nodes_as_variables(root_node, queries["variable_types"], code)
        return result

    def _walk(self, node, target_types: List[str]):
        """Depth-first traversal yielding nodes that match target types."""
        if node.type in target_types:
            yield node
        for child in node.children:
            yield from self._walk(child, target_types)

    def _get_child_by_type(self, node, child_type: str):
        """Return the first child of a specific type, or None."""
        for child in node.children:
            if child.type == child_type:
                return child
        return None

    def _node_text(self, node, code: str) -> str:
        """Extract source text for a tree-sitter node."""
        return code[node.start_byte:node.end_byte]

    def _extract_nodes_as_functions(self, root, type_names, code) -> List[FunctionSymbol]:
        functions = []
        for node in self._walk(root, type_names):
            name_node = self._get_child_by_type(node, "identifier") or self._get_child_by_type(node, "property_identifier")
            name = self._node_text(name_node, code) if name_node else "<anonymous>"

            # Try extracting parameter names
            args = []
            params_node = self._get_child_by_type(node, "formal_parameters") or \
                          self._get_child_by_type(node, "parameter_list") or \
                          self._get_child_by_type(node, "parameters")
            if params_node:
                for child in params_node.children:
                    if child.type in ("identifier", "required_parameter", "optional_parameter",
                                      "parameter_declaration", "formal_parameter"):
                        id_node = self._get_child_by_type(child, "identifier")
                        if id_node:
                            args.append(self._node_text(id_node, code))
                        elif child.type == "identifier":
                            args.append(self._node_text(child, code))

            functions.append(FunctionSymbol(
                name=name,
                args=args,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                line_count=node.end_point[0] - node.start_point[0] + 1,
            ))
        return functions

    def _extract_nodes_as_classes(self, root, type_names, code) -> List[ClassSymbol]:
        classes = []
        for node in self._walk(root, type_names):
            name_node = self._get_child_by_type(node, "identifier") or self._get_child_by_type(node, "type_identifier")
            name = self._node_text(name_node, code) if name_node else "<anonymous>"

            # Extract method names inside the class body
            methods = []
            body_node = self._get_child_by_type(node, "class_body") or self._get_child_by_type(node, "declaration_list")
            if body_node:
                for child in body_node.children:
                    if child.type in ("method_definition", "method_declaration", "function_definition"):
                        m_name_node = self._get_child_by_type(child, "identifier") or \
                                      self._get_child_by_type(child, "property_identifier")
                        if m_name_node:
                            methods.append(self._node_text(m_name_node, code))

            # Extract base classes / superclass
            bases = []
            heritage = self._get_child_by_type(node, "class_heritage") or \
                       self._get_child_by_type(node, "superclass") or \
                       self._get_child_by_type(node, "base_class_clause")
            if heritage:
                for child in heritage.children:
                    if child.type in ("identifier", "type_identifier"):
                        bases.append(self._node_text(child, code))

            classes.append(ClassSymbol(
                name=name,
                bases=bases,
                methods=methods,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                line_count=node.end_point[0] - node.start_point[0] + 1,
            ))
        return classes

    def _extract_nodes_as_imports(self, root, type_names, code) -> List[ImportSymbol]:
        imports = []
        for node in self._walk(root, type_names):
            text = self._node_text(node, code).strip()
            # Extract module source
            source_node = self._get_child_by_type(node, "string") or \
                          self._get_child_by_type(node, "scoped_identifier") or \
                          self._get_child_by_type(node, "string_literal")
            module = self._node_text(source_node, code).strip("'\"") if source_node else text

            imports.append(ImportSymbol(
                module=module,
                names=[module],
                is_from_import="from" in text.lower() if text else False,
                line=node.start_point[0] + 1,
            ))
        return imports

    def _extract_nodes_as_variables(self, root, type_names, code) -> List[VariableSymbol]:
        variables = []
        for node in self._walk(root, type_names):
            # Try to get the variable name
            name_node = self._get_child_by_type(node, "identifier") or \
                        self._get_child_by_type(node, "variable_declarator")
            if name_node:
                if name_node.type == "variable_declarator":
                    inner = self._get_child_by_type(name_node, "identifier")
                    if inner:
                        name_node = inner
                name = self._node_text(name_node, code)
                variables.append(VariableSymbol(
                    name=name,
                    line=node.start_point[0] + 1,
                    is_constant=name.isupper(),
                ))
        return variables


# ══════════════════════════════════════════════
#  Dependency Mapper — cross-file import graph
# ══════════════════════════════════════════════

@dataclass
class DependencyEdge:
    """A directed edge: source_file imports target_module."""
    source_file: str
    target_module: str
    import_names: List[str] = field(default_factory=list)
    line: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source_file,
            "target": self.target_module,
            "names": self.import_names,
            "line": self.line,
        }


class DependencyMapper:
    """
    Builds a cross-file import dependency graph from FileAnalysis results.
    Detects internal (intra-repo) vs. external (third-party) dependencies
    and identifies circular dependency chains.
    """

    def __init__(self):
        self.edges: List[DependencyEdge] = []
        self._internal_modules: set = set()

    def build_from_analyses(
        self,
        analyses: List[FileAnalysis],
        internal_prefix: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Consume a list of FileAnalysis objects and produce a dependency map.

        Args:
            analyses: parsed FileAnalysis results from ASTAnalyzer.
            internal_prefix: if set, modules starting with this prefix are
                             considered internal.  Otherwise, all files in
                             the analysis set define the internal boundary.
        """
        self.edges = []

        # Build set of known internal module names from filepaths
        for analysis in analyses:
            mod_name = self._filepath_to_module(analysis.filepath)
            if mod_name:
                self._internal_modules.add(mod_name)

        for analysis in analyses:
            for imp in analysis.imports:
                if imp.module:
                    is_internal = self._is_internal(imp.module, internal_prefix)
                    self.edges.append(DependencyEdge(
                        source_file=analysis.filepath,
                        target_module=imp.module,
                        import_names=imp.names,
                        line=imp.line,
                    ))

        return self.summary(internal_prefix)

    def summary(self, internal_prefix: Optional[str] = None) -> Dict[str, Any]:
        internal_edges = [e for e in self.edges if self._is_internal(e.target_module, internal_prefix)]
        external_edges = [e for e in self.edges if not self._is_internal(e.target_module, internal_prefix)]

        # Detect circular dependencies (simple cycle detection)
        cycles = self._detect_cycles(internal_edges)

        return {
            "total_dependencies": len(self.edges),
            "internal_dependencies": len(internal_edges),
            "external_dependencies": len(external_edges),
            "circular_dependencies": cycles,
            "has_circular_deps": len(cycles) > 0,
            "edges": [e.to_dict() for e in self.edges],
        }

    def _is_internal(self, module_name: str, prefix: Optional[str]) -> bool:
        if prefix:
            return module_name.startswith(prefix)
        return module_name in self._internal_modules

    @staticmethod
    def _filepath_to_module(filepath: str) -> Optional[str]:
        """Convert 'backend/app/part1_parser/ingestion.py' → 'backend.app.part1_parser.ingestion'."""
        p = filepath.replace("\\", "/")
        if p.endswith(".py"):
            p = p[:-3]
            return p.replace("/", ".")
        return None

    def _detect_cycles(self, edges: List[DependencyEdge]) -> List[List[str]]:
        """Find simple cycles in the internal dependency graph via DFS."""
        graph: Dict[str, List[str]] = {}
        for edge in edges:
            src = edge.source_file
            tgt = edge.target_module
            graph.setdefault(src, []).append(tgt)

        visited: set = set()
        rec_stack: set = set()
        cycles: List[List[str]] = []

        def dfs(node: str, path: List[str]):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbour in graph.get(node, []):
                if neighbour not in visited:
                    dfs(neighbour, path)
                elif neighbour in rec_stack:
                    # Found a cycle
                    cycle_start = path.index(neighbour) if neighbour in path else -1
                    if cycle_start >= 0:
                        cycles.append(path[cycle_start:] + [neighbour])

            path.pop()
            rec_stack.discard(node)

        for node in graph:
            if node not in visited:
                dfs(node, [])

        return cycles


# ══════════════════════════════════════════════
#  ASTAnalyzer — unified entry point
# ══════════════════════════════════════════════

class ASTAnalyzer:
    """
    Part 1 — Unified AST analysis facade.

    Routes to the appropriate backend parser:
      • Python  → ``PythonASTParser`` (always available)
      • JS/TS/Java/C++/Go → ``TreeSitterParser`` (requires tree-sitter-languages)

    Usage::

        analyzer = ASTAnalyzer()
        result = analyzer.analyze_code(source_code, language="python", filepath="app.py")
        result = analyzer.analyze_code(js_code, language="javascript", filepath="index.js")
    """

    def __init__(self):
        self._python_parser = PythonASTParser()
        self._ts_parser: Optional[TreeSitterParser] = None
        if TREE_SITTER_AVAILABLE:
            self._ts_parser = TreeSitterParser()

        self._dep_mapper = DependencyMapper()

    @property
    def supported_languages(self) -> List[str]:
        langs = ["python"]
        if self._ts_parser:
            langs.extend(sorted(TreeSitterParser.SUPPORTED_LANGUAGES))
        return langs

    def analyze_code(self, code: str, language: str, filepath: str = "<string>") -> FileAnalysis:
        """Analyse a single source string and return extracted symbols."""
        if language == "python":
            return self._python_parser.parse(code, filepath)

        if self._ts_parser and language in TreeSitterParser.SUPPORTED_LANGUAGES:
            return self._ts_parser.parse(code, language, filepath)

        # Fallback: return a minimal result indicating unsupported language
        return FileAnalysis(
            filepath=filepath,
            language=language,
            valid=False,
            error=f"No parser available for language '{language}'. "
                  f"Supported: {self.supported_languages}",
        )

    def analyze_file(self, filepath: str, language: str) -> FileAnalysis:
        """Read and analyse a file from disk."""
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as fh:
                code = fh.read()
        except OSError as exc:
            return FileAnalysis(filepath=filepath, language=language, valid=False, error=str(exc))
        return self.analyze_code(code, language, filepath)

    def analyze_repository(self, file_nodes) -> Dict[str, Any]:
        """
        Analyse all source files from a RepoIngestor's file_tree.

        Args:
            file_nodes: list of FileNode objects from ingestion.

        Returns:
            dict with per-file analyses plus aggregated statistics.
        """
        analyses: List[FileAnalysis] = []
        errors: List[Dict[str, str]] = []

        for node in file_nodes:
            if node.language is None:
                continue
            result = self.analyze_file(node.absolute_path, node.language)
            analyses.append(result)
            if not result.valid:
                errors.append({"file": node.relative_path, "error": result.error or "unknown"})

        # Build dependency map
        dep_map = self._dep_mapper.build_from_analyses(analyses)

        return {
            "total_files_analyzed": len(analyses),
            "total_functions": sum(len(a.functions) for a in analyses),
            "total_classes": sum(len(a.classes) for a in analyses),
            "total_imports": sum(len(a.imports) for a in analyses),
            "total_variables": sum(len(a.variables) for a in analyses),
            "parse_errors": errors,
            "dependency_map": dep_map,
            "analyses": [a.to_dict() for a in analyses],
        }

    # Legacy compat — keep the old method name working
    def parse_python_code(self, code: str) -> Dict[str, Any]:
        """Legacy API: parse Python code and return flat dict."""
        result = self._python_parser.parse(code)
        return {
            "valid": result.valid,
            "error": result.error,
            "classes": [c.name for c in result.classes],
            "functions": [f.name for f in result.functions],
            "imports": [i.module for i in result.imports if i.module],
        }
