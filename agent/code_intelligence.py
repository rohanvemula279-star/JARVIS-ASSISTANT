# agent/code_intelligence.py
"""
Code Intelligence Agent - Self-evolving system for code analysis and modification.

This module provides autonomous code scanning, dependency analysis, and safe modification
capabilities for the Jarvis assistant system.

Architecture:
    ┌─────────────────────────────────────────────────────────────┐
    │                   CodeIntelligenceAgent                    │
    ├─────────────────────────────────────────────────────────────┤
    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │
    │  │CodeScanner  │→ │DepAnalyzer  │→ │FeatureMapper    │   │
    │  └─────────────┘  └─────────────┘  └─────────────────┘   │
    │         ↓                ↓                ↓              │
    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │
    │  │BugDetector  │  │ChangePlanner│→ │SafeEditor       │   │
    │  └─────────────┘  └─────────────┘  └─────────────────┘   │
    │                                                    ↓      │
    │                   ┌─────────────────────────────┐       │
    │                   │     TestRunner + Rollback   │       │
    │                   └─────────────────────────────┘       │
    └─────────────────────────────────────────────────────────────┘
"""

import os
import ast
import json
import shutil
import subprocess
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
from collections import defaultdict


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKUP_DIR = PROJECT_ROOT / ".backups"


class CodeScanner:
    """
    Code Reader Agent - Scans project and builds structural map.

    Responsibilities:
    - List all Python files in project
    - Parse file structure (imports, classes, functions)
    - Build project map
    - Track file metadata
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self.file_map: Dict[str, Dict] = {}
        self._scan_project()

    def _scan_project(self):
        """Scan all Python files and build map."""
        for py_file in self.root.rglob("*.py"):
            if self._should_skip(py_file):
                continue

            rel_path = py_file.relative_to(self.root)
            key = str(rel_path).replace("\\", "/")

            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.read()

                self.file_map[key] = {
                    "path": str(py_file),
                    "rel_path": key,
                    "size": py_file.stat().st_size,
                    "modified": py_file.stat().st_mtime,
                    "classes": self._extract_classes(content),
                    "functions": self._extract_functions(content),
                    "imports": self._extract_imports(content),
                    "docstring": self._extract_docstring(content),
                }
            except Exception as e:
                print(f"[CodeScanner] Failed to parse {key}: {e}")

    def _should_skip(self, path: Path) -> bool:
        """Skip test files, __pycache__, and hidden dirs."""
        skip_patterns = ["__pycache__", ".git", "node_modules", ".venv", "venv", "env"]
        return any(p in str(path) for p in skip_patterns)

    def _extract_classes(self, content: str) -> List[str]:
        """Extract class definitions."""
        try:
            tree = ast.parse(content)
            return [
                node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
            ]
        except:
            return []

    def _extract_functions(self, content: str) -> List[str]:
        """Extract function definitions."""
        try:
            tree = ast.parse(content)
            return [
                node.name
                for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
            ]
        except:
            return []

    def _extract_imports(self, content: str) -> List[str]:
        """Extract import statements."""
        try:
            tree = ast.parse(content)
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)
            return imports
        except:
            return []

    def _extract_docstring(self, content: str) -> str:
        """Extract module docstring."""
        try:
            tree = ast.parse(content)
            docstring = ast.get_docstring(tree)
            return docstring[:200] if docstring else ""
        except:
            return ""

    def get_structure(self) -> Dict:
        """Return project structure as dict."""
        return {
            "total_files": len(self.file_map),
            "files": self.file_map,
            "directories": list(set(str(Path(f).parent) for f in self.file_map.keys())),
        }

    def find_file(self, name: str) -> Optional[str]:
        """Find file by class or function name."""
        name_lower = name.lower()
        for key, data in self.file_map.items():
            if name_lower in data.get("functions", []) or name_lower in data.get(
                "classes", []
            ):
                return key
        return None

    def get_file_content(self, rel_path: str) -> Optional[str]:
        """Read file content."""
        abs_path = self.root / rel_path
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                return f.read()
        except:
            return None


class DependencyAnalyzer:
    """
    Dependency Analyzer - Maps file relationships and dependencies.

    Responsibilities:
    - Map which files call which
    - Track function/class relationships
    - Build call graph
    """

    def __init__(self, scanner: CodeScanner):
        self.scanner = scanner
        self.dependency_graph: Dict[str, Set[str]] = defaultdict(set)
        self.reverse_graph: Dict[str, Set[str]] = defaultdict(set)
        self._build_graph()

    def _build_graph(self):
        """Build dependency graph from imports."""
        for file_key, data in self.scanner.file_map.items():
            imports = data.get("imports", [])

            for imp in imports:
                if imp.startswith("."):
                    continue

                for other_key in self.scanner.file_map.keys():
                    if imp in other_key or other_key.startswith(imp.split(".")[0]):
                        self.dependency_graph[file_key].add(other_key)
                        self.reverse_graph[other_key].add(file_key)

    def get_dependents(self, file_key: str) -> Set[str]:
        """Get files that depend on this file."""
        return self.reverse_graph.get(file_key, set())

    def get_dependencies(self, file_key: str) -> Set[str]:
        """Get files this file depends on."""
        return self.dependency_graph.get(file_key, set())

    def find_circular_deps(self) -> List[List[str]]:
        """Find circular dependencies."""
        circular = []
        visited = set()

        def dfs(path: str, stack: List[str]):
            if path in stack:
                idx = stack.index(path)
                circular.append(stack[idx:] + [path])
                return

            if path in visited:
                return

            visited.add(path)
            stack.append(path)

            for dep in self.dependency_graph.get(path, set()):
                dfs(dep, stack.copy())

        for file_key in self.dependency_graph:
            dfs(file_key, [])

        return circular


class FeatureMapper:
    """
    Feature Mapper - Maps functionality to files.

    Responsibilities:
    - Know which file handles which feature
    - Track feature domains (voice, browser, automation, etc.)
    """

    def __init__(self, scanner: CodeScanner):
        self.scanner = scanner
        self.feature_map: Dict[str, List[str]] = {
            "voice": [],
            "browser": [],
            "automation": [],
            "memory": [],
            "face_auth": [],
            "api": [],
            "actions": [],
            "core": [],
        }
        self._map_features()

    def _map_features(self):
        """Map files to feature domains."""
        for key in self.scanner.file_map:
            key_lower = key.lower()

            if "voice" in key_lower or "speech" in key_lower:
                self.feature_map["voice"].append(key)
            elif "browser" in key_lower:
                self.feature_map["browser"].append(key)
            elif "automation" in key_lower or "action" in key_lower:
                self.feature_map["actions"].append(key)
            elif "memory" in key_lower or "knowledge" in key_lower:
                self.feature_map["memory"].append(key)
            elif "face" in key_lower or "auth" in key_lower:
                self.feature_map["face_auth"].append(key)
            elif "api" in key_lower:
                self.feature_map["api"].append(key)
            elif "core" in key_lower:
                self.feature_map["core"].append(key)

    def find_handler(self, feature: str) -> List[str]:
        """Find files that handle a specific feature."""
        feature_lower = feature.lower()
        results = []

        for domain, files in self.feature_map.items():
            if feature_lower in domain:
                results.extend(files)

        if not results:
            results = self.feature_map.get(feature_lower, [])

        return results

    def get_domain_summary(self) -> Dict[str, int]:
        """Get count of files per domain."""
        return {k: len(v) for k, v in self.feature_map.items()}


class BugDetector:
    """
    Bug Detector - Finds errors, slow code, bad logic.

    Responsibilities:
    - Syntax error detection
    - Unused imports/variables
    - Slow patterns detection
    - Missing error handling
    """

    def __init__(self, scanner: CodeScanner):
        self.scanner = scanner
        self.issues: List[Dict] = []
        self._scan_issues()

    def _scan_issues(self):
        """Scan all files for issues."""
        for key, data in self.scanner.file_map.items():
            content = self.scanner.get_file_content(key)
            if not content:
                continue

            self._check_syntax_errors(key, content)
            self._check_bad_patterns(key, content)
            self._check_security_issues(key, content)

    def _check_syntax_errors(self, key: str, content: str):
        """Check for syntax issues."""
        try:
            ast.parse(content)
        except SyntaxError as e:
            self.issues.append(
                {
                    "file": key,
                    "type": "syntax_error",
                    "line": e.lineno,
                    "message": str(e),
                    "severity": "high",
                }
            )

    def _check_bad_patterns(self, key: str, content: str):
        """Check for bad code patterns."""
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            if "except:" in line and "pass" in lines[i : i + 3]:
                self.issues.append(
                    {
                        "file": key,
                        "type": "empty_except",
                        "line": i,
                        "message": "Empty except block - error silently ignored",
                        "severity": "medium",
                    }
                )

            if "time.sleep" in line and "while" in "".join(lines[max(0, i - 5) : i]):
                self.issues.append(
                    {
                        "file": key,
                        "type": "blocking_sleep",
                        "line": i,
                        "message": "Blocking sleep in potential loop",
                        "severity": "medium",
                    }
                )

    def _check_security_issues(self, key: str, content: str):
        """Check for security issues with safety context awareness."""
        dangerous_patterns = ["eval(", "exec(", "os.system(", "subprocess.call("]

        # Patterns that indicate safe, controlled usage
        safety_markers = [
            "# safe_exec",
            "# controlled_exec",
            "# sandboxed",
            "# SECURITY",
            "BLOCKED_KEYWORDS",
            "_is_safe_code",
            "_execute_with_timeout",
        ]

        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            # Skip lines with safety markers
            if any(marker in line for marker in safety_markers):
                continue

            for pattern in dangerous_patterns:
                if pattern in line:
                    # Check if this is in a function that has safety measures
                    context_start = max(0, i - 50)
                    context = "\n".join(lines[context_start:i])

                    # If there's safety checking in context, reduce severity or skip
                    if any(s in context for s in safety_markers):
                        continue

                    self.issues.append(
                        {
                            "file": key,
                            "type": "security",
                            "line": i,
                            "message": f"Dangerous function: {pattern} - ensure proper safety measures",
                            "severity": "high",
                        }
                    )

    def get_report(self) -> Dict:
        """Get bug report."""
        by_severity = {"high": [], "medium": [], "low": []}

        for issue in self.issues:
            by_severity[issue["severity"]].append(issue)

        return {
            "total_issues": len(self.issues),
            "by_severity": by_severity,
            "issues": self.issues,
        }

    def get_issues_for_file(self, file_key: str) -> List[Dict]:
        """Get issues for specific file."""
        return [i for i in self.issues if i["file"] == file_key]


class ChangePlanner:
    """
    Modification Planner - Plans safe changes.

    Responsibilities:
    - Decide WHAT to change
    - Decide WHERE to change
    - Decide HOW to change
    - Check impact before making changes
    """

    def __init__(self, scanner: CodeScanner, dep_analyzer: DependencyAnalyzer):
        self.scanner = scanner
        self.dep_analyzer = dep_analyzer

    def plan_change(self, target: str, change_type: str, description: str) -> Dict:
        """Plan a modification to a target."""
        file_key = (
            target
            if target in self.scanner.file_map
            else self.scanner.find_file(target)
        )

        if not file_key:
            return {"error": "Target not found", "success": False}

        content = self.scanner.get_file_content(file_key)
        if not content:
            return {"error": "Cannot read file", "success": False}

        dependents = self.dep_analyzer.get_dependents(file_key)
        dependencies = self.dep_analyzer.get_dependencies(file_key)

        return {
            "success": True,
            "target": file_key,
            "change_type": change_type,
            "description": description,
            "risk_level": self._calculate_risk(len(dependents)),
            "dependents": list(dependents),
            "dependencies": list(dependencies),
            "backup_needed": True,
            "test_required": True,
        }

    def _calculate_risk(self, num_dependents: int) -> str:
        """Calculate risk level based on dependents."""
        if num_dependents == 0:
            return "low"
        elif num_dependents < 3:
            return "medium"
        else:
            return "high"


class SafeEditor:
    """
    Safe Editor - Patch-based editing with rollback.

    Responsibilities:
    - Backup before changes
    - Patch-based editing (not full overwrite)
    - Rollback on error
    """

    def __init__(self, scanner: CodeScanner):
        self.scanner = scanner
        self.edit_history: List[Dict] = []

    def create_backup(self) -> Optional[str]:
        """Create timestamped backup of project."""
        BACKUP_DIR.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / f"backup_{timestamp}"

        try:
            shutil.copytree(
                self.scanner.root, backup_path, ignore=self._ignore_patterns
            )
            return str(backup_path)
        except Exception as e:
            print(f"[SafeEditor] Warning: Backup failed: {e}")
            return None

    def _ignore_patterns(self, src, names):
        """Patterns to ignore during backup."""
        return {"__pycache__", ".git", "node_modules", "*.pyc", ".venv", "venv"}

    def apply_patch(
        self,
        file_key: str,
        old_string: str,
        new_string: str,
        create_backup: bool = True,
    ) -> bool:
        """Apply patch to file."""
        if create_backup and not self.edit_history:
            self.create_backup()

        content = self.scanner.get_file_content(file_key)
        if not content:
            return False

        if old_string not in content:
            print(f"[SafeEditor] Warning: Old string not found in {file_key}")
            return False

        new_content = content.replace(old_string, new_string, 1)

        abs_path = self.scanner.root / file_key

        try:
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            self.edit_history.append(
                {
                    "file": file_key,
                    "timestamp": datetime.now().isoformat(),
                    "old_hash": hashlib.md5(content.encode()).hexdigest(),
                }
            )

            print(f"[SafeEditor] Applied patch to {file_key}")
            return True
        except Exception as e:
            print(f"[SafeEditor] ❌ Patch failed: {e}")
            return False

    def rollback(self, steps: int = 1) -> bool:
        """Rollback last N edits."""
        if not BACKUP_DIR.exists():
            print("[SafeEditor] ⚠️ No backups found")
            return False

        backups = sorted(BACKUP_DIR.glob("backup_*"), reverse=True)

        if steps > len(backups):
            steps = len(backups)

        latest = backups[steps - 1]

        try:
            for key in self.scanner.file_map:
                abs_path = self.scanner.root / key
                backup_file = latest / key

                if backup_file.exists():
                    shutil.copy2(backup_file, abs_path)

            print(f"[SafeEditor] ✅ Rolled back {steps} edit(s)")
            return True
        except Exception as e:
            print(f"[SafeEditor] ❌ Rollback failed: {e}")
            return False

    def verify_syntax(self, file_key: str) -> bool:
        """Verify file has no syntax errors."""
        content = self.scanner.get_file_content(file_key)
        if not content:
            return False

        try:
            ast.parse(content)
            return True
        except SyntaxError:
            return False


class TestRunner:
    """
    Test Runner - Runs tests and detects errors.

    Responsibilities:
    - Run modified code
    - Detect errors
    - Report results
    """

    def __init__(self, scanner: CodeScanner):
        self.scanner = scanner

    def check_syntax(self, file_key: str) -> Tuple[bool, Optional[str]]:
        """Check file syntax."""
        content = self.scanner.get_file_content(file_key)
        if not content:
            return False, "Cannot read file"

        try:
            ast.parse(content)
            return True, None
        except SyntaxError as e:
            return False, str(e)

    def run_import_test(self, file_key: str) -> Tuple[bool, Optional[str]]:
        """Test if file can be imported."""
        abs_path = self.scanner.root / file_key

        try:
            result = subprocess.run(
                [
                    "python",
                    "-c",
                    f"import sys; sys.path.insert(0, '{self.scanner.root}'); import {abs_path.stem}",
                ],
                capture_output=True,
                timeout=10,
                cwd=str(self.scanner.root),
            )

            if result.returncode == 0:
                return True, None
            else:
                return False, result.stderr.decode()[:200]
        except Exception as e:
            return False, str(e)

    def get_test_summary(self, file_keys: List[str]) -> Dict:
        """Run tests on multiple files."""
        results = {"passed": [], "failed": [], "errors": []}

        for key in file_keys:
            ok, err = self.check_syntax(key)
            if ok:
                results["passed"].append(key)
            else:
                results["failed"].append({"file": key, "error": err})

        return results


class CodeIntelligenceAgent:
    """
    Main Code Intelligence Agent - Coordinates all sub-agents.

    This is the brain that enables self-evolving capabilities.

    Usage:
        agent = CodeIntelligenceAgent()
        report = agent.scan()
        issues = agent.get_bugs()
        plan = agent.plan_change("open_app", "fix", "Add better error handling")
    """

    def __init__(self, root: Path = PROJECT_ROOT):
        self.root = Path(root)

        print("[CodeIntelligence] Initializing...")
        self.scanner = CodeScanner(self.root)
        print(f"[CodeIntelligence] Scanned {len(self.scanner.file_map)} files")

        self.dep_analyzer = DependencyAnalyzer(self.scanner)
        print("[CodeIntelligence] Built dependency graph")

        self.feature_mapper = FeatureMapper(self.scanner)
        print("[CodeIntelligence] Mapped features")

        self.bug_detector = BugDetector(self.scanner)
        print(f"[CodeIntelligence] Found {len(self.bug_detector.issues)} issues")

        self.change_planner = ChangePlanner(self.scanner, self.dep_analyzer)
        self.safe_editor = SafeEditor(self.scanner)
        self.test_runner = TestRunner(self.scanner)

        print("[CodeIntelligence] Ready")

    def scan(self) -> Dict:
        """Run full scan and return report."""
        return {
            "structure": self.scanner.get_structure(),
            "features": self.feature_mapper.get_domain_summary(),
            "bugs": self.bug_detector.get_report(),
        }

    def get_bugs(self, severity: Optional[str] = None) -> List[Dict]:
        """Get bug report."""
        if severity:
            return [i for i in self.bug_detector.issues if i["severity"] == severity]
        return self.bug_detector.issues

    def find_handler(self, feature: str) -> List[str]:
        """Find files that handle a feature."""
        return self.feature_mapper.find_handler(feature)

    def plan_change(self, target: str, change_type: str, description: str) -> Dict:
        """Plan a modification."""
        return self.change_planner.plan_change(target, change_type, description)

    def apply_fix(self, file_key: str, old: str, new: str) -> bool:
        """Apply a safe fix."""
        return self.safe_editor.apply_patch(file_key, old, new)

    def verify(self, file_key: str) -> Tuple[bool, Optional[str]]:
        """Verify a file."""
        return self.test_runner.check_syntax(file_key)

    def get_dependencies(self, file_key: str) -> List[str]:
        """Get file dependencies."""
        return list(self.dep_analyzer.get_dependencies(file_key))

    def get_dependents(self, file_key: str) -> List[str]:
        """Get file dependents."""
        return list(self.dep_analyzer.get_dependents(file_key))


def create_agent() -> CodeIntelligenceAgent:
    """Factory function to create agent."""
    return CodeIntelligenceAgent()
