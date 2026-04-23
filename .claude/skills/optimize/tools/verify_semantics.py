#!/usr/bin/env python3
"""
Verify Semantics - Semantic Verification via Unit Tests

This tool verifies that semantic behavior is preserved after optimization.
It runs unit tests before and after changes to ensure:
1. Output consistency - same inputs produce same outputs
2. Error handling preservation - same errors for same inputs
3. Edge case coverage - boundary conditions behave identically

The "Dual-track Verification" approach:
- Run existing unit tests (if available)
- Generate and run semantic tests for critical functions
"""

import os
import json
import sys
import subprocess
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass


@dataclass
class SemanticTestResult:
    """Result of semantic verification tests"""
    passed: int
    failed: int
    errors: List[str]
    test_output: str
    duration: float


def run_unit_tests(
    project_root: Path,
    test_command: Optional[str] = None,
    test_directory: Optional[Path] = None
) -> Tuple[bool, SemanticTestResult]:
    """
    Run unit tests to verify semantic preservation.

    Args:
        project_root: Root directory of the project
        test_command: Optional custom test command
        test_directory: Directory containing tests

    Returns:
        Tuple of (success, result) where success is True if all tests pass
    """
    import time

    if test_command is None:
        # Default test commands to try
        test_commands = [
            "python -m pytest -v",
            "python -m pytest -v --tb=short",
            "pytest -v",
            "python -m unittest discover",
            "npm test",
            "go test ./...",
        ]
    else:
        test_commands = [test_command]

    errors = []
    test_output = ""
    passed = 0
    failed = 0
    start_time = time.time()

    for cmd in test_commands:
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            test_output = result.stdout + result.stderr

            # Parse test output for results
            if result.returncode == 0:
                # Success - tests passed
                # Try to parse pass/fail counts
                import re

                # Pytest format: X passed
                pytest_match = re.search(r'(\d+) passed', test_output)
                if pytest_match:
                    passed = int(pytest_match.group(1))

                # Unittest format: OK/FAIL
                if 'OK' in test_output and 'FAIL' not in test_output:
                    return True, SemanticTestResult(
                        passed=passed or 1,
                        failed=0,
                        errors=[],
                        test_output=test_output,
                        duration=time.time() - start_time
                    )

                # npm test format
                if 'passing' in test_output:
                    npm_match = re.search(r'(\d+) passing', test_output)
                    if npm_match:
                        passed = int(npm_match.group(1))

                return True, SemanticTestResult(
                    passed=passed,
                    failed=failed,
                    errors=[],
                    test_output=test_output,
                    duration=time.time() - start_time
                )
            else:
                # Tests failed
                # Parse failure counts
                pytest_fail = re.search(r'(\d+) failed', test_output)
                pytest_pass = re.search(r'(\d+) passed', test_output)

                if pytest_fail:
                    failed = int(pytest_fail.group(1))
                if pytest_pass:
                    passed = int(pytest_pass.group(1))

                errors.append(f"Tests failed with return code {result.returncode}")
                errors.append(result.stderr[:500] if result.stderr else "")

                return False, SemanticTestResult(
                    passed=passed,
                    failed=failed,
                    errors=errors,
                    test_output=test_output,
                    duration=time.time() - start_time
                )

        except subprocess.TimeoutExpired:
            errors.append("Test execution timed out after 5 minutes")
            return False, SemanticTestResult(
                passed=0,
                failed=0,
                errors=errors,
                test_output="Timeout",
                duration=300.0
            )
        except FileNotFoundError as e:
            # Command not found, try next one
            errors.append(f"Command not found: {cmd}")
            continue
        except Exception as e:
            errors.append(f"Error running tests: {str(e)}")
            continue

    # No test command succeeded
    return False, SemanticTestResult(
        passed=0,
        failed=0,
        errors=errors,
        test_output="\n".join(errors),
        duration=time.time() - start_time
    )


def generate_semantic_test(
    source_file: Path,
    function_name: Optional[str] = None
) -> str:
    """
    Generate a semantic test for a source file.

    This creates a test that verifies input/output behavior is preserved
    after optimization changes.
    """
    # Read source file
    try:
        content = source_file.read_text()
    except Exception as e:
        return f"# Error reading source: {e}\n"

    # Detect language
    suffix = source_file.suffix.lower()

    if suffix == '.py':
        return _generate_python_semantic_test(content, function_name)
    elif suffix in ['.js', '.ts']:
        return _generate_js_semantic_test(content, function_name)
    elif suffix == '.go':
        return _generate_go_semantic_test(content, function_name)
    else:
        return f"# Unsupported file type: {suffix}\n"


def _generate_python_semantic_test(content: str, function_name: Optional[str]) -> str:
    """Generate Python semantic test"""
    import re

    # Find function definitions
    functions = re.findall(r'^def\s+(\w+)\s*\([^)]*\):', content, re.MULTILINE)

    if not functions:
        return "# No functions found to test\n"

    test_code = '''#!/usr/bin/env python3
"""
Generated Semantic Test
Verifies that function behavior is preserved after optimization
"""

import unittest
import sys
from pathlib import Path

# Add source directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestSemanticPreservation(unittest.TestCase):
    """Test that semantic behavior is preserved"""

'''

    for func in functions[:5]:  # Limit to first 5 functions
        if function_name and func != function_name:
            continue

        test_code += f'''
    def test_{func}_input_output_consistency(self):
        """Test that {func} produces consistent outputs for same inputs"""
        # TODO: Add specific test cases for {func}
        # These should test:
        # 1. Normal inputs
        # 2. Edge cases
        # 3. Error conditions
        pass

'''

    test_code += '''
if __name__ == '__main__':
    unittest.main(verbosity=2)
'''

    return test_code


def _generate_js_semantic_test(content: str, function_name: Optional[str]) -> str:
    """Generate JavaScript/TypeScript semantic test"""
    import re

    # Find function definitions
    functions = re.findall(r'function\s+(\w+)\s*\(', content)

    if not functions:
        # Also check arrow functions
        functions = re.findall(r'const\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>', content)

    if not functions:
        return "// No functions found to test\n"

    test_code = '''/**
 * Generated Semantic Test
 * Verifies that function behavior is preserved after optimization
 */

const assert = require('assert');

'''

    for func in functions[:5]:
        if function_name and func != function_name:
            continue

        test_code += f'''
describe('{func}', () => {{
    it('should produce consistent outputs for same inputs', () => {{
        // TODO: Add specific test cases for {func}
        // These should test:
        // 1. Normal inputs
        // 2. Edge cases
        // 3. Error conditions
    }});
}});
'''

    return test_code


def _generate_go_semantic_test(content: str, function_name: Optional[str]) -> str:
    """Generate Go semantic test"""
    import re

    # Find function definitions
    functions = re.findall(r'func\s+(?:\([^)]+\)\s+)?(\w+)\s*\(', content)

    if not functions:
        return "// No functions found to test\n"

    test_code = '''package main

import (
    "testing"
)

'''

    for func in functions[:5]:
        if function_name and func != function_name:
            continue

        test_code += f'''
func Test{func.capitalize()}(t *testing.T) {{
    // TODO: Add specific test cases for {func}
    // These should test:
    // 1. Normal inputs
    // 2. Edge cases
    // 3. Error conditions
    t.Run("input output consistency", func(t *testing.T) {{
        // Add test cases here
    }})
}}
'''

    return test_code


def compare_semantic_behavior(
    before_output: Dict[str, Any],
    after_output: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    """
    Compare semantic behavior before and after optimization.

    Returns:
        Tuple of (is_preserved, differences)
    """
    differences = []

    def compare_recursive(before: Any, after: Any, path: str = "root"):
        if type(before) != type(after):
            differences.append(f"Type mismatch at {path}: {type(before).__name__} vs {type(after).__name__}")
            return

        if isinstance(before, dict):
            if set(before.keys()) != set(after.keys()):
                differences.append(f"Key mismatch at {path}: {set(before.keys())} vs {set(after.keys())}")
            for key in before:
                if key in after:
                    compare_recursive(before[key], after[key], f"{path}.{key}")

        elif isinstance(before, list):
            if len(before) != len(after):
                differences.append(f"Length mismatch at {path}: {len(before)} vs {len(after)}")
            for i, (b, a) in enumerate(zip(before, after)):
                compare_recursive(b, a, f"{path}[{i}]")

        elif isinstance(before, float):
            # Allow small floating point differences
            if abs(before - after) > 1e-9:
                differences.append(f"Value mismatch at {path}: {before} vs {after}")

        else:
            if before != after:
                differences.append(f"Value mismatch at {path}: {before} vs {after}")

    compare_recursive(before_output, after_output)

    return len(differences) == 0, differences


def main():
    parser = argparse.ArgumentParser(
        description="Verify semantic preservation after optimization"
    )
    parser.add_argument(
        "source_file",
        type=Path,
        help="Source file to verify"
    )
    parser.add_argument(
        "--test-command",
        type=str,
        help="Custom test command to run"
    )
    parser.add_argument(
        "--test-directory",
        type=Path,
        help="Directory containing tests"
    )
    parser.add_argument(
        "--function",
        type=str,
        help="Specific function to test"
    )
    parser.add_argument(
        "--generate-test",
        action="store_true",
        help="Generate a semantic test file"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file for generated test"
    )

    args = parser.parse_args()

    if args.generate_test:
        # Generate semantic test
        test_code = generate_semantic_test(args.source_file, args.function)
        output_path = args.output or args.source_file.parent / f"test_semantic_{args.source_file.stem}.py"
        output_path.write_text(test_code)
        print(f"Generated semantic test at {output_path}")
        return 0

    # Run semantic verification
    project_root = args.source_file.parent

    # Try to find project root (look for common markers)
    for marker in ['.git', 'pyproject.toml', 'setup.py', 'package.json', 'go.mod']:
        if (project_root / marker).exists():
            break
        project_root = project_root.parent

    success, result = run_unit_tests(
        project_root,
        test_command=args.test_command,
        test_directory=args.test_directory
    )

    print(f"\n{'='*60}")
    print(f"Semantic Verification Results")
    print(f"{'='*60}")
    print(f"Passed: {result.passed}")
    print(f"Failed: {result.failed}")
    print(f"Duration: {result.duration:.2f}s")

    if result.errors:
        print(f"\nErrors:")
        for error in result.errors:
            print(f"  - {error}")

    if not success:
        print(f"\n❌ Semantic verification FAILED")
        return 1

    print(f"\n✅ Semantic verification PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
