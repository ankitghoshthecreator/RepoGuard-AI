"""
Part 1: Code Ingestion, AST & Static Analysis Engine
=====================================================
Modules:
  • ingestion       — Multi-source repository ingestion (GitHub, local, ZIP)
  • ast_analyzer    — Python AST + Tree-sitter multi-language symbol extraction
  • static_scanner  — Security vulnerability scanner + code quality analyser
"""
from .ingestion import RepoIngestor, FileNode, detect_language
from .ast_analyzer import (
    ASTAnalyzer,
    PythonASTParser,
    DependencyMapper,
    FileAnalysis,
    FunctionSymbol,
    ClassSymbol,
    ImportSymbol,
    VariableSymbol,
)
from .static_scanner import (
    StaticSecurityScanner,
    StaticCodeAnalyzer,
    UnifiedScanner,
    Finding,
)

__all__ = [
    # Ingestion
    "RepoIngestor",
    "FileNode",
    "detect_language",
    # AST Analysis
    "ASTAnalyzer",
    "PythonASTParser",
    "DependencyMapper",
    "FileAnalysis",
    "FunctionSymbol",
    "ClassSymbol",
    "ImportSymbol",
    "VariableSymbol",
    # Scanners
    "StaticSecurityScanner",
    "StaticCodeAnalyzer",
    "UnifiedScanner",
    "Finding",
]
