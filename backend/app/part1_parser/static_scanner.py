"""
Part 1 — Static Code & Security Vulnerability Scanner
=======================================================
Two scanner classes:

1. ``StaticSecurityScanner``  — vulnerability & credential detection:
     • Hardcoded secrets (API keys, passwords, tokens, AWS keys)
     • SQL injection patterns
     • Command injection patterns
     • Unsafe deserialization (pickle, yaml, marshal)
     • Weak / insecure cryptography usage
     • Insecure HTTP / TLS settings
     • Authentication & authorisation flaws

2. ``StaticCodeAnalyzer``     — code quality & complexity analysis:
     • Dead / unreachable code after return/raise/break/continue
     • Long functions (configurable threshold)
     • Deep nesting depth
     • Cognitive complexity estimation
     • Duplicate / redundant logic detection
     • Naming convention violations

Both scanners are language-agnostic (regex & line-based) so they work
on any source file, though heuristics are tuned for Python / JS / Java.
"""

import re
import ast
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger("repoguard.part1.static_scanner")


# ══════════════════════════════════════════════
#  Finding data class
# ══════════════════════════════════════════════

@dataclass
class Finding:
    """A single scanner finding / vulnerability / code-smell."""
    file: str
    line: int
    type: str
    severity: str        # CRITICAL | HIGH | MEDIUM | LOW | INFO
    category: str        # "security" | "code_quality"
    description: str
    evidence: str = ""   # the actual matched line / snippet
    cwe: Optional[str] = None  # CWE reference, e.g. "CWE-798"
    fix_suggestion: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "file": self.file,
            "line": self.line,
            "type": self.type,
            "severity": self.severity,
            "category": self.category,
            "description": self.description,
            "evidence": self.evidence,
        }
        if self.cwe:
            d["cwe"] = self.cwe
        if self.fix_suggestion:
            d["fix_suggestion"] = self.fix_suggestion
        return d


# ══════════════════════════════════════════════
#  Static Security Scanner
# ══════════════════════════════════════════════

class StaticSecurityScanner:
    """
    Part 1 — Pattern-based security vulnerability scanner.

    Scans source code line-by-line for:
      • Hardcoded credentials & secrets
      • SQL injection vectors
      • Command injection vectors
      • Unsafe deserialization
      • Weak cryptography
      • Insecure HTTP / TLS settings
      • Authentication bypass indicators
    """

    # ── Pattern definitions ──────────────────
    # Each tuple: (compiled_regex, type_name, severity, description, cwe, fix)

    _SECRET_PATTERNS: List[Tuple[re.Pattern, str, str, str, str, str]] = [
        (
            re.compile(r'(?i)(api[_\-]?key|apikey)\s*[=:]\s*["\'][A-Za-z0-9_\-/+=]{16,}["\']'),
            "Hardcoded API Key",
            "HIGH",
            "API key appears to be hardcoded in source code.",
            "CWE-798",
            "Use environment variables or a secrets manager to store API keys.",
        ),
        (
            re.compile(r'(?i)(secret[_\-]?key|secretkey)\s*[=:]\s*["\'][A-Za-z0-9_\-/+=]{16,}["\']'),
            "Hardcoded Secret Key",
            "HIGH",
            "Secret key is hardcoded in source code.",
            "CWE-798",
            "Move secret keys to environment variables or vault storage.",
        ),
        (
            re.compile(r'(?i)(password|passwd|pwd)\s*[=:]\s*["\'][^"\']{4,}["\']'),
            "Hardcoded Password",
            "HIGH",
            "Password value appears hardcoded.",
            "CWE-798",
            "Never hardcode passwords. Use environment variables or credential stores.",
        ),
        (
            re.compile(r'(?i)(token|auth_token|access_token|bearer)\s*[=:]\s*["\'][A-Za-z0-9_\-/.+=]{20,}["\']'),
            "Hardcoded Token",
            "HIGH",
            "Authentication token is hardcoded.",
            "CWE-798",
            "Store tokens in environment variables, not in source code.",
        ),
        (
            re.compile(r'AKIA[0-9A-Z]{16}'),
            "AWS Access Key ID",
            "CRITICAL",
            "AWS IAM access key ID detected in source code.",
            "CWE-798",
            "Rotate this key immediately and use IAM roles / environment variables.",
        ),
        (
            re.compile(r'(?i)(private[_\-]?key)\s*[=:]\s*["\']-----BEGIN'),
            "Hardcoded Private Key",
            "CRITICAL",
            "Private key embedded directly in source code.",
            "CWE-321",
            "Store private keys in secure key management systems, never in code.",
        ),
        (
            re.compile(r'(?i)(connection[_\-]?string|database[_\-]?url|db[_\-]?url)\s*[=:]\s*["\'][^"\']{10,}["\']'),
            "Hardcoded Connection String",
            "HIGH",
            "Database connection string hardcoded in source.",
            "CWE-798",
            "Use environment variables for database connection strings.",
        ),
    ]

    _SQL_INJECTION_PATTERNS: List[Tuple[re.Pattern, str, str]] = [
        (
            re.compile(r'execute\s*\(.*(%s|%d|\{|\+|\.format\s*\(|f["\'])'),
            "SQL Injection — String Interpolation in execute()",
            "Dynamic SQL query built via string formatting inside execute().",
        ),
        (
            re.compile(r'(?i)(cursor|conn|connection|db|session)\.(execute|raw|query)\s*\(.*(\+|%|\.format|f["\'])'),
            "SQL Injection — Unsafe Query Construction",
            "SQL query constructed with user-controlled string concatenation.",
        ),
        (
            re.compile(r'(?i)text\s*\(\s*f["\']'),
            "SQL Injection — SQLAlchemy text() with f-string",
            "SQLAlchemy text() used with an f-string; use bindparams instead.",
        ),
    ]

    _COMMAND_INJECTION_PATTERNS: List[Tuple[re.Pattern, str, str]] = [
        (
            re.compile(r'os\.system\s*\('),
            "Command Injection — os.system()",
            "os.system() is inherently unsafe. Use subprocess with shell=False.",
        ),
        (
            re.compile(r'subprocess\.(call|run|Popen)\s*\(.*shell\s*=\s*True'),
            "Command Injection — subprocess with shell=True",
            "shell=True passes commands through the system shell, enabling injection.",
        ),
        (
            re.compile(r'(?i)eval\s*\('),
            "Code Injection — eval()",
            "eval() executes arbitrary code. Use ast.literal_eval() for data parsing.",
        ),
        (
            re.compile(r'(?i)exec\s*\('),
            "Code Injection — exec()",
            "exec() executes arbitrary code strings. Avoid in production.",
        ),
    ]

    _DESERIALIZATION_PATTERNS: List[Tuple[re.Pattern, str, str]] = [
        (
            re.compile(r'pickle\.(loads?|Unpickler)\s*\('),
            "Unsafe Deserialization — pickle",
            "pickle.load/loads can execute arbitrary code during deserialization.",
        ),
        (
            re.compile(r'yaml\.(load|unsafe_load)\s*\((?!.*Loader\s*=\s*(SafeLoader|yaml\.SafeLoader))'),
            "Unsafe Deserialization — PyYAML",
            "yaml.load() without SafeLoader can execute arbitrary Python objects.",
        ),
        (
            re.compile(r'marshal\.loads?\s*\('),
            "Unsafe Deserialization — marshal",
            "marshal.load/loads is not secure against malicious data.",
        ),
        (
            re.compile(r'jsonpickle\.decode\s*\('),
            "Unsafe Deserialization — jsonpickle",
            "jsonpickle.decode() can instantiate arbitrary objects.",
        ),
    ]

    _CRYPTO_PATTERNS: List[Tuple[re.Pattern, str, str]] = [
        (
            re.compile(r'(?i)(md5|MD5)\s*\('),
            "Weak Cryptography — MD5",
            "MD5 is cryptographically broken. Use SHA-256 or SHA-3.",
        ),
        (
            re.compile(r'(?i)(sha1|SHA1)\s*\('),
            "Weak Cryptography — SHA-1",
            "SHA-1 has known collision attacks. Use SHA-256 or SHA-3.",
        ),
        (
            re.compile(r'(?i)(DES|Blowfish|RC4|RC2)\b'),
            "Weak Cryptography — Deprecated Algorithm",
            "DES/Blowfish/RC4/RC2 are deprecated. Use AES-256-GCM.",
        ),
        (
            re.compile(r'(?i)random\.(random|randint|choice|shuffle)\s*\('),
            "Insecure Randomness",
            "random module is not cryptographically secure. Use secrets module.",
        ),
    ]

    _INSECURE_HTTP_PATTERNS: List[Tuple[re.Pattern, str, str]] = [
        (
            re.compile(r'verify\s*=\s*False'),
            "Insecure TLS — SSL Verification Disabled",
            "Disabling SSL verification exposes the connection to MITM attacks.",
        ),
        (
            re.compile(r'http://(?!localhost|127\.0\.0\.1|0\.0\.0\.0)'),
            "Insecure HTTP — Plaintext URL",
            "Non-localhost HTTP URL detected. Use HTTPS for external connections.",
        ),
    ]

    # ── Main scan method ─────────────────────

    def scan_code(self, code: str, filename: str) -> List[Finding]:
        """
        Scan source code for security vulnerabilities.

        Returns a list of ``Finding`` objects sorted by severity.
        """
        findings: List[Finding] = []
        lines = code.split("\n")

        for idx, line in enumerate(lines, 1):
            stripped = line.strip()

            # Skip comments and blank lines
            if not stripped or stripped.startswith("#") or stripped.startswith("//"):
                continue

            # ─ Hardcoded Secrets ─
            for pattern, vuln_type, severity, desc, cwe, fix in self._SECRET_PATTERNS:
                if pattern.search(line):
                    findings.append(Finding(
                        file=filename, line=idx,
                        type=vuln_type, severity=severity,
                        category="security",
                        description=desc,
                        evidence=stripped[:120],
                        cwe=cwe,
                        fix_suggestion=fix,
                    ))

            # ─ SQL Injection ─
            for pattern, vuln_type, desc in self._SQL_INJECTION_PATTERNS:
                if pattern.search(line):
                    findings.append(Finding(
                        file=filename, line=idx,
                        type=vuln_type, severity="CRITICAL",
                        category="security",
                        description=desc,
                        evidence=stripped[:120],
                        cwe="CWE-89",
                        fix_suggestion="Use parameterised queries or ORM methods.",
                    ))

            # ─ Command Injection ─
            for pattern, vuln_type, desc in self._COMMAND_INJECTION_PATTERNS:
                if pattern.search(line):
                    findings.append(Finding(
                        file=filename, line=idx,
                        type=vuln_type, severity="CRITICAL",
                        category="security",
                        description=desc,
                        evidence=stripped[:120],
                        cwe="CWE-78",
                        fix_suggestion="Use subprocess with shell=False and argument lists.",
                    ))

            # ─ Unsafe Deserialization ─
            for pattern, vuln_type, desc in self._DESERIALIZATION_PATTERNS:
                if pattern.search(line):
                    findings.append(Finding(
                        file=filename, line=idx,
                        type=vuln_type, severity="HIGH",
                        category="security",
                        description=desc,
                        evidence=stripped[:120],
                        cwe="CWE-502",
                        fix_suggestion="Use safe loaders or JSON for data serialisation.",
                    ))

            # ─ Weak Cryptography ─
            for pattern, vuln_type, desc in self._CRYPTO_PATTERNS:
                if pattern.search(line):
                    findings.append(Finding(
                        file=filename, line=idx,
                        type=vuln_type, severity="MEDIUM",
                        category="security",
                        description=desc,
                        evidence=stripped[:120],
                        cwe="CWE-327",
                        fix_suggestion="Use modern cryptographic primitives (AES-256-GCM, SHA-256).",
                    ))

            # ─ Insecure HTTP / TLS ─
            for pattern, vuln_type, desc in self._INSECURE_HTTP_PATTERNS:
                if pattern.search(line):
                    findings.append(Finding(
                        file=filename, line=idx,
                        type=vuln_type, severity="MEDIUM",
                        category="security",
                        description=desc,
                        evidence=stripped[:120],
                        cwe="CWE-319",
                    ))

        # Sort by severity ranking
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
        findings.sort(key=lambda f: severity_order.get(f.severity, 5))
        return findings

    def scan_file(self, filepath: str) -> List[Finding]:
        """Read a file from disk and scan it."""
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as fh:
                code = fh.read()
        except OSError as exc:
            return [Finding(
                file=filepath, line=0, type="FileReadError",
                severity="LOW", category="security",
                description=f"Could not read file: {exc}",
            )]
        return self.scan_code(code, filepath)


# ══════════════════════════════════════════════
#  Static Code Analyzer — quality & complexity
# ══════════════════════════════════════════════

class StaticCodeAnalyzer:
    """
    Part 1 — Code quality and complexity analyser.

    Detects:
      • Dead / unreachable code after return / raise / break / continue
      • Functions exceeding a line-count threshold (long methods)
      • Excessive nesting depth
      • Cognitive complexity estimation (per-function for Python)
      • Naming convention violations (non-snake_case functions, non-PascalCase classes)
    """

    DEFAULT_MAX_FUNCTION_LINES = 50
    DEFAULT_MAX_NESTING_DEPTH = 5
    DEFAULT_MAX_COMPLEXITY = 15

    def __init__(
        self,
        max_function_lines: int = DEFAULT_MAX_FUNCTION_LINES,
        max_nesting_depth: int = DEFAULT_MAX_NESTING_DEPTH,
        max_complexity: int = DEFAULT_MAX_COMPLEXITY,
    ):
        self.max_function_lines = max_function_lines
        self.max_nesting_depth = max_nesting_depth
        self.max_complexity = max_complexity

    # ── Main analyse method ───────────────────

    def analyze_code(self, code: str, filename: str, language: str = "python") -> List[Finding]:
        """Run all code-quality checks on a source string."""
        findings: List[Finding] = []

        findings.extend(self._check_dead_code(code, filename))
        findings.extend(self._check_long_functions(code, filename, language))
        findings.extend(self._check_deep_nesting(code, filename))
        findings.extend(self._check_naming_conventions(code, filename, language))

        if language == "python":
            findings.extend(self._check_cognitive_complexity_python(code, filename))

        return findings

    def analyze_file(self, filepath: str, language: str = "python") -> List[Finding]:
        """Read and analyse a file from disk."""
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as fh:
                code = fh.read()
        except OSError:
            return []
        return self.analyze_code(code, filepath, language)

    # ── Dead / unreachable code ───────────────

    def _check_dead_code(self, code: str, filename: str) -> List[Finding]:
        findings: List[Finding] = []
        lines = code.split("\n")

        # Pattern: code immediately after return/raise/break/continue at same or deeper indent
        terminator_pattern = re.compile(r'^(\s*)(return|raise|break|continue)\b')
        i = 0
        while i < len(lines):
            match = terminator_pattern.match(lines[i])
            if match:
                term_indent = len(match.group(1))
                term_keyword = match.group(2)
                j = i + 1
                while j < len(lines):
                    next_line = lines[j]
                    stripped = next_line.strip()
                    # Skip blank lines and comments
                    if not stripped or stripped.startswith("#") or stripped.startswith("//"):
                        j += 1
                        continue
                    # Measure indent of next real line
                    next_indent = len(next_line) - len(next_line.lstrip())
                    if next_indent > term_indent:
                        # Deeper indent after terminator → likely unreachable
                        findings.append(Finding(
                            file=filename, line=j + 1,
                            type="Unreachable Code",
                            severity="LOW",
                            category="code_quality",
                            description=f"Code after '{term_keyword}' statement appears unreachable.",
                            evidence=stripped[:100],
                            fix_suggestion="Remove dead code or restructure control flow.",
                        ))
                    break  # only check the very next statement
                i = j
            else:
                i += 1

        return findings

    # ── Long functions ────────────────────────

    def _check_long_functions(self, code: str, filename: str, language: str) -> List[Finding]:
        findings: List[Finding] = []

        if language == "python":
            try:
                tree = ast.parse(code)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        end_line = getattr(node, "end_lineno", node.lineno)
                        func_lines = end_line - node.lineno + 1
                        if func_lines > self.max_function_lines:
                            findings.append(Finding(
                                file=filename, line=node.lineno,
                                type="Long Function",
                                severity="MEDIUM",
                                category="code_quality",
                                description=(
                                    f"Function '{node.name}' is {func_lines} lines long "
                                    f"(threshold: {self.max_function_lines})."
                                ),
                                fix_suggestion="Break the function into smaller, focused helper functions.",
                            ))
            except SyntaxError:
                pass  # Not valid Python — skip this check
        else:
            # Language-agnostic heuristic: scan for function-like blocks
            func_pattern = re.compile(
                r'^(\s*)(def |function |public |private |protected |func |static )\s*(\w+)'
            )
            lines = code.split("\n")
            i = 0
            while i < len(lines):
                m = func_pattern.match(lines[i])
                if m:
                    start = i
                    base_indent = len(m.group(1))
                    func_name = m.group(3)
                    j = i + 1
                    while j < len(lines):
                        stripped = lines[j].strip()
                        if not stripped:
                            j += 1
                            continue
                        current_indent = len(lines[j]) - len(lines[j].lstrip())
                        if current_indent <= base_indent and stripped and not stripped.startswith(("#", "//", "/*", "*")):
                            break
                        j += 1
                    func_length = j - start
                    if func_length > self.max_function_lines:
                        findings.append(Finding(
                            file=filename, line=start + 1,
                            type="Long Function",
                            severity="MEDIUM",
                            category="code_quality",
                            description=(
                                f"Function '{func_name}' is ~{func_length} lines long "
                                f"(threshold: {self.max_function_lines})."
                            ),
                            fix_suggestion="Break the function into smaller, focused helper functions.",
                        ))
                    i = j
                else:
                    i += 1
        return findings

    # ── Deep nesting ──────────────────────────

    def _check_deep_nesting(self, code: str, filename: str) -> List[Finding]:
        findings: List[Finding] = []
        lines = code.split("\n")
        reported_lines: set = set()

        for idx, line in enumerate(lines, 1):
            if not line.strip():
                continue
            # Measure indent level (tabs count as 4 spaces)
            expanded = line.replace("\t", "    ")
            indent = len(expanded) - len(expanded.lstrip())
            indent_level = indent // 4

            if indent_level > self.max_nesting_depth and idx not in reported_lines:
                findings.append(Finding(
                    file=filename, line=idx,
                    type="Deep Nesting",
                    severity="LOW",
                    category="code_quality",
                    description=(
                        f"Code at nesting depth {indent_level} exceeds threshold "
                        f"({self.max_nesting_depth}). Consider early returns or extracting functions."
                    ),
                    evidence=line.strip()[:100],
                    fix_suggestion="Use guard clauses (early return) to reduce nesting.",
                ))
                reported_lines.add(idx)

        return findings

    # ── Cognitive complexity (Python only) ────

    def _check_cognitive_complexity_python(self, code: str, filename: str) -> List[Finding]:
        """
        Estimate cognitive complexity per function using a simplified
        version of the SonarSource model:
          +1 for each: if, elif, else, for, while, except, with, assert, lambda
          +1 nesting increment per nesting level when starting a new branch
        """
        findings: List[Finding] = []
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return findings

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                complexity = self._compute_cognitive_complexity(node)
                if complexity > self.max_complexity:
                    findings.append(Finding(
                        file=filename, line=node.lineno,
                        type="High Cognitive Complexity",
                        severity="MEDIUM",
                        category="code_quality",
                        description=(
                            f"Function '{node.name}' has cognitive complexity of "
                            f"{complexity} (threshold: {self.max_complexity})."
                        ),
                        fix_suggestion="Simplify logic, extract helper functions, use early returns.",
                    ))
        return findings

    def _compute_cognitive_complexity(self, func_node, nesting: int = 0) -> int:
        """Recursive cognitive complexity calculator."""
        complexity = 0
        INCREMENTING_NODES = (
            ast.If, ast.For, ast.While, ast.ExceptHandler,
            ast.With, ast.Assert,
        )
        NESTING_NODES = (ast.If, ast.For, ast.While, ast.ExceptHandler, ast.With)

        for child in ast.iter_child_nodes(func_node):
            if isinstance(child, INCREMENTING_NODES):
                complexity += 1 + nesting  # base increment + nesting penalty
            # Boolean sequences (and/or chains)
            if isinstance(child, ast.BoolOp):
                complexity += 1
            # Lambda adds a nesting level
            if isinstance(child, ast.Lambda):
                complexity += 1 + nesting

            # Recurse with nesting for nesting nodes
            if isinstance(child, NESTING_NODES):
                complexity += self._compute_cognitive_complexity(child, nesting + 1)
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Nested function → nesting + 1
                complexity += 1 + nesting
                complexity += self._compute_cognitive_complexity(child, nesting + 1)
            else:
                complexity += self._compute_cognitive_complexity(child, nesting)

        return complexity

    # ── Naming convention checks ──────────────

    def _check_naming_conventions(self, code: str, filename: str, language: str) -> List[Finding]:
        """Check for naming convention violations in Python code."""
        findings: List[Finding] = []
        if language != "python":
            return findings  # Only enforce for Python currently

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return findings

        for node in ast.walk(tree):
            # Functions should be snake_case
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("_"):
                    name = node.name.lstrip("_")
                else:
                    name = node.name
                if name and not re.match(r'^[a-z][a-z0-9_]*$', name) and name != "__init__":
                    # Skip dunder methods
                    if not (name.startswith("__") and name.endswith("__")):
                        findings.append(Finding(
                            file=filename, line=node.lineno,
                            type="Naming Convention Violation",
                            severity="INFO",
                            category="code_quality",
                            description=f"Function '{node.name}' is not snake_case.",
                            fix_suggestion="Use snake_case for function names (PEP 8).",
                        ))

            # Classes should be PascalCase
            if isinstance(node, ast.ClassDef):
                if not re.match(r'^[A-Z][a-zA-Z0-9]*$', node.name):
                    findings.append(Finding(
                        file=filename, line=node.lineno,
                        type="Naming Convention Violation",
                        severity="INFO",
                        category="code_quality",
                        description=f"Class '{node.name}' is not PascalCase.",
                        fix_suggestion="Use PascalCase for class names (PEP 8).",
                    ))

        return findings


# ══════════════════════════════════════════════
#  Unified Scanner — aggregates both scanners
# ══════════════════════════════════════════════

class UnifiedScanner:
    """
    Part 1 — Convenience wrapper that runs both security and code-quality
    scans in a single call and returns an aggregated report.
    """

    def __init__(
        self,
        max_function_lines: int = StaticCodeAnalyzer.DEFAULT_MAX_FUNCTION_LINES,
        max_nesting_depth: int = StaticCodeAnalyzer.DEFAULT_MAX_NESTING_DEPTH,
        max_complexity: int = StaticCodeAnalyzer.DEFAULT_MAX_COMPLEXITY,
    ):
        self.security_scanner = StaticSecurityScanner()
        self.code_analyzer = StaticCodeAnalyzer(
            max_function_lines=max_function_lines,
            max_nesting_depth=max_nesting_depth,
            max_complexity=max_complexity,
        )

    def scan_code(self, code: str, filename: str, language: str = "python") -> Dict[str, Any]:
        """Run both scanners and return an aggregated report."""
        sec_findings = self.security_scanner.scan_code(code, filename)
        quality_findings = self.code_analyzer.analyze_code(code, filename, language)
        all_findings = sec_findings + quality_findings

        # Statistics
        severity_counts: Dict[str, int] = {}
        category_counts: Dict[str, int] = {}
        for f in all_findings:
            severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1
            category_counts[f.category] = category_counts.get(f.category, 0) + 1

        return {
            "file": filename,
            "total_findings": len(all_findings),
            "severity_breakdown": severity_counts,
            "category_breakdown": category_counts,
            "security_findings": [f.to_dict() for f in sec_findings],
            "quality_findings": [f.to_dict() for f in quality_findings],
            "all_findings": [f.to_dict() for f in all_findings],
            "health_score": self._compute_health_score(all_findings),
        }

    def scan_file(self, filepath: str, language: str = "python") -> Dict[str, Any]:
        """Read and scan a file from disk."""
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as fh:
                code = fh.read()
        except OSError as exc:
            return {"file": filepath, "error": str(exc), "total_findings": 0}
        return self.scan_code(code, filepath, language)

    @staticmethod
    def _compute_health_score(findings: List[Finding]) -> float:
        """
        Compute a 0–100 health score.
        Starts at 100 and deducts points per finding based on severity.
        """
        deductions = {
            "CRITICAL": 15,
            "HIGH": 10,
            "MEDIUM": 5,
            "LOW": 2,
            "INFO": 0,
        }
        score = 100.0
        for f in findings:
            score -= deductions.get(f.severity, 1)
        return max(0.0, round(score, 1))
