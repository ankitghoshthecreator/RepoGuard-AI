"""
Part 1 — Repository Ingestion Engine
=====================================
Multi-source repository ingestion supporting:
  • GitHub remote repositories (cloned via GitPython)
  • Local directory scanning
  • ZIP archive extraction
Produces a normalised file-tree manifest with per-file metadata
(language, byte-size, line-count) that downstream modules consume.
"""

import os
import shutil
import zipfile
import tempfile
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

try:
    from git import Repo as GitRepo, InvalidGitRepositoryError, GitCommandError
except ImportError:
    GitRepo = None  # graceful fallback when gitpython is not installed

# ──────────────────────────────────────────────
# Language detection by file extension
# ──────────────────────────────────────────────
EXTENSION_LANGUAGE_MAP: Dict[str, str] = {
    ".py":   "python",
    ".js":   "javascript",
    ".jsx":  "javascript",
    ".ts":   "typescript",
    ".tsx":  "typescript",
    ".java": "java",
    ".cpp":  "cpp",
    ".cc":   "cpp",
    ".cxx":  "cpp",
    ".c":    "c",
    ".h":    "c",
    ".hpp":  "cpp",
    ".go":   "go",
    ".rs":   "rust",
    ".rb":   "ruby",
    ".php":  "php",
    ".cs":   "csharp",
    ".swift":"swift",
    ".kt":  "kotlin",
    ".scala":"scala",
    ".md":   "markdown",
    ".json": "json",
    ".yaml": "yaml",
    ".yml":  "yaml",
    ".toml": "toml",
    ".xml":  "xml",
    ".html": "html",
    ".css":  "css",
    ".sql":  "sql",
    ".sh":   "shell",
    ".bat":  "batch",
    ".ps1":  "powershell",
    ".dockerfile": "dockerfile",
}

# Directories that should always be skipped during traversal
IGNORED_DIRECTORIES = frozenset({
    ".git", ".svn", ".hg",
    "node_modules", "__pycache__", ".mypy_cache", ".pytest_cache",
    "venv", ".venv", "env", ".env",
    ".tox", ".nox",
    "dist", "build", ".eggs", "*.egg-info",
    ".idea", ".vscode",
    "qdrant_data", "neo4j_data",
})

# Binary / non-parseable extensions to skip
BINARY_EXTENSIONS = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg",
    ".woff", ".woff2", ".ttf", ".eot",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
    ".exe", ".dll", ".so", ".dylib", ".o", ".a",
    ".pyc", ".pyo", ".class", ".jar",
    ".mp3", ".mp4", ".avi", ".mov", ".wav",
    ".sqlite", ".db",
})


def detect_language(filepath: str) -> Optional[str]:
    """Return the language identifier for a file path, or None if unknown."""
    ext = Path(filepath).suffix.lower()
    # Special-case Dockerfiles
    if Path(filepath).name.lower() in ("dockerfile", "dockerfile.dev", "dockerfile.prod"):
        return "dockerfile"
    return EXTENSION_LANGUAGE_MAP.get(ext)


def is_ignored_dir(dirname: str) -> bool:
    """Check whether a directory name should be skipped."""
    return dirname in IGNORED_DIRECTORIES or dirname.startswith(".")


def is_binary_file(filepath: str) -> bool:
    """Quick check based on extension to skip binary files."""
    return Path(filepath).suffix.lower() in BINARY_EXTENSIONS


def safe_line_count(filepath: str) -> int:
    """Count lines in a text file, returning 0 on decode errors."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as fh:
            return sum(1 for _ in fh)
    except (OSError, UnicodeDecodeError):
        return 0


def safe_read(filepath: str) -> Optional[str]:
    """Read a text file safely, returning None on failure."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        return None


def file_hash(filepath: str) -> str:
    """Compute SHA-256 of a file for dedup / caching."""
    sha = hashlib.sha256()
    try:
        with open(filepath, "rb") as fh:
            for chunk in iter(lambda: fh.read(8192), b""):
                sha.update(chunk)
    except OSError:
        return ""
    return sha.hexdigest()


# ══════════════════════════════════════════════
#  FileNode — metadata record for a single file
# ══════════════════════════════════════════════
class FileNode:
    """Lightweight metadata container for one repository file."""

    __slots__ = (
        "absolute_path", "relative_path", "language",
        "size_bytes", "line_count", "sha256",
    )

    def __init__(self, absolute_path: str, repo_root: str):
        self.absolute_path = absolute_path
        self.relative_path = os.path.relpath(absolute_path, repo_root)
        self.language = detect_language(absolute_path)
        self.size_bytes = os.path.getsize(absolute_path) if os.path.isfile(absolute_path) else 0
        self.line_count = safe_line_count(absolute_path) if not is_binary_file(absolute_path) else 0
        self.sha256 = file_hash(absolute_path)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.relative_path,
            "language": self.language,
            "size_bytes": self.size_bytes,
            "line_count": self.line_count,
            "sha256": self.sha256,
        }


# ══════════════════════════════════════════════
#  RepoIngestor — main ingestion orchestrator
# ══════════════════════════════════════════════
class RepoIngestor:
    """
    Part 1 — Multi-source repository ingestor.

    Supports three ingestion modes:
        1. ``from_github(url, branch)``  — clone a remote GitHub repo
        2. ``from_local(path)``          — scan a local directory
        3. ``from_zip(zip_path)``        — extract and scan a ZIP archive

    After ingestion the ``file_tree`` attribute holds a list of
    ``FileNode`` objects, and ``manifest()`` returns a serialisable dict.
    """

    def __init__(self):
        self.repo_root: Optional[str] = None
        self.source_type: Optional[str] = None
        self.file_tree: List[FileNode] = []
        self._temp_dirs: List[str] = []  # track temp dirs for cleanup

    # ── public factory helpers ────────────────

    def from_github(self, url: str, branch: str = "main", target_dir: Optional[str] = None) -> "RepoIngestor":
        """Clone a GitHub repository and ingest it."""
        if GitRepo is None:
            raise ImportError(
                "GitPython is required for GitHub ingestion. "
                "Install it with: pip install gitpython"
            )
        clone_dest = target_dir or tempfile.mkdtemp(prefix="repoguard_")
        if not target_dir:
            self._temp_dirs.append(clone_dest)

        try:
            GitRepo.clone_from(url, clone_dest, branch=branch, depth=1)
        except GitCommandError as exc:
            raise RuntimeError(f"Failed to clone {url} (branch={branch}): {exc}") from exc

        self.repo_root = clone_dest
        self.source_type = "github"
        self._scan()
        return self

    def from_local(self, path: str) -> "RepoIngestor":
        """Ingest an existing local directory."""
        path = os.path.abspath(path)
        if not os.path.isdir(path):
            raise FileNotFoundError(f"Directory does not exist: {path}")
        self.repo_root = path
        self.source_type = "local"
        self._scan()
        return self

    def from_zip(self, zip_path: str) -> "RepoIngestor":
        """Extract a ZIP archive to a temp directory and ingest."""
        zip_path = os.path.abspath(zip_path)
        if not zipfile.is_zipfile(zip_path):
            raise ValueError(f"Not a valid ZIP file: {zip_path}")

        extract_dir = tempfile.mkdtemp(prefix="repoguard_zip_")
        self._temp_dirs.append(extract_dir)

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)

        # If the ZIP contains a single root folder, use that as repo root
        top_entries = os.listdir(extract_dir)
        if len(top_entries) == 1 and os.path.isdir(os.path.join(extract_dir, top_entries[0])):
            self.repo_root = os.path.join(extract_dir, top_entries[0])
        else:
            self.repo_root = extract_dir

        self.source_type = "zip"
        self._scan()
        return self

    # ── core scanning logic ───────────────────

    def _scan(self) -> None:
        """Walk the repo directory tree and build the file manifest."""
        self.file_tree = []
        for dirpath, dirnames, filenames in os.walk(self.repo_root):
            # Prune ignored directories in-place so os.walk doesn't descend
            dirnames[:] = [d for d in dirnames if not is_ignored_dir(d)]

            for fname in filenames:
                full_path = os.path.join(dirpath, fname)
                if is_binary_file(full_path):
                    continue
                node = FileNode(full_path, self.repo_root)
                self.file_tree.append(node)

    # ── accessors ─────────────────────────────

    def get_files_by_language(self, language: str) -> List[FileNode]:
        """Filter the file tree to a specific language."""
        return [f for f in self.file_tree if f.language == language]

    def get_source_files(self) -> List[FileNode]:
        """Return only files with a recognised programming language."""
        return [f for f in self.file_tree if f.language is not None]

    def read_file(self, relative_path: str) -> Optional[str]:
        """Read the contents of a file by its relative path."""
        abs_path = os.path.join(self.repo_root, relative_path)
        return safe_read(abs_path)

    @property
    def language_stats(self) -> Dict[str, int]:
        """Return {language: file_count} breakdown."""
        stats: Dict[str, int] = {}
        for node in self.file_tree:
            lang = node.language or "unknown"
            stats[lang] = stats.get(lang, 0) + 1
        return stats

    @property
    def total_lines(self) -> int:
        return sum(f.line_count for f in self.file_tree)

    # ── serialisation ─────────────────────────

    def manifest(self) -> Dict[str, Any]:
        """Return a serialisable summary of the ingested repository."""
        return {
            "status": "success",
            "source_type": self.source_type,
            "repo_root": self.repo_root,
            "total_files": len(self.file_tree),
            "total_source_files": len(self.get_source_files()),
            "total_lines": self.total_lines,
            "language_breakdown": self.language_stats,
            "ingested_at": datetime.utcnow().isoformat(),
            "files": [f.to_dict() for f in self.file_tree],
        }

    # ── cleanup ───────────────────────────────

    def cleanup(self) -> None:
        """Remove any temporary directories created during ingestion."""
        for td in self._temp_dirs:
            if os.path.isdir(td):
                shutil.rmtree(td, ignore_errors=True)
        self._temp_dirs.clear()

    def __del__(self):
        self.cleanup()

    def __repr__(self) -> str:
        return (
            f"<RepoIngestor source={self.source_type} "
            f"files={len(self.file_tree)} "
            f"lines={self.total_lines}>"
        )
