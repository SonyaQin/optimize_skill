#!/usr/bin/env python3
"""
Propose Patch - Generate Code Diff for Optimization

This tool generates optimization proposals as unified diffs.
It's designed to be called by an external orchestrator that manages
the LLM interaction.

Key features:
- Generates clean, minimal diffs
- Focuses on performance optimizations only
- Can receive graveyard warnings to avoid failed strategies
"""

import os
import json
import argparse
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass


@dataclass
class OptimizationProposal:
    """A proposed optimization with metadata"""
    diff_content: str
    optimization_type: str
    description: str
    expected_benefit: str
    risk_level: str  # "low", "medium", "high"
    affected_functions: List[str]


def analyze_file_for_optimizations(file_path: Path) -> List[Dict[str, Any]]:
    """
    Analyze source file and identify optimization opportunities.

    This is a static analysis - actual optimization proposal
    should come from an LLM with full context.
    """
    content = file_path.read_text()
    opportunities = []

    # Check for common patterns
    lines = content.split('\n')

    for i, line in enumerate(lines):
        # Nested loops - O(n²) or worse
        if 'for' in line and any('for' in l for l in lines[max(0,i-5):i]):
            opportunities.append({
                'line': i + 1,
                'type': 'algorithm',
                'description': 'Nested loops detected - potential algorithmic optimization',
                'severity': 'high'
            })

        # String concatenation in loop
        if '+=' in line and ('for' in line or any('for' in l for l in lines[max(0,i-3):i])):
            opportunities.append({
                'line': i + 1,
                'type': 'memory',
                'description': 'String concatenation in loop - consider using join()',
                'severity': 'medium'
            })

        # Repeated function calls with same arguments
        # (simplified check - real implementation would need AST)

    return opportunities


def generate_prompt_for_llm(
    file_path: Path,
    file_content: str,
    unit_test_content: Optional[str] = None,
    graveyard_warnings: Optional[str] = None,
    optimization_focus: Optional[str] = None,
    previous_attempts: Optional[List[str]] = None
) -> str:
    """
    Generate the prompt that will be sent to an LLM for optimization proposal.

    This prompt is designed to be:
    1. Stateless - all context is provided
    2. Constrained - clear rules about what's allowed
    3. Warned - graveyard failures are injected
    """
    prompt = f"""You are a performance optimization expert. Your task is to propose a SINGLE, SPECIFIC optimization for the code below.

## CRITICAL RULES

1. **DO NOT change behavior** - The code must produce identical outputs for identical inputs
2. **DO NOT remove error handling** - Keep all try/except blocks and validation
3. **DO NOT hardcode values** - Dynamic computations must remain dynamic
4. **OUTPUT ONLY A UNIFIED DIFF** - No explanations outside the diff
5. **ONE OPTIMIZATION AT A TIME** - Focus on a single improvement

## TARGET FILE

File: `{file_path.name}`

```{file_path.suffix[1:]}
{file_content}
```

"""

    if unit_test_content:
        prompt += f"""
## UNIT TESTS (Must Pass)

These tests verify correct behavior. Your optimization MUST NOT break these:

```python
{unit_test_content[:2000]}  # Truncated for prompt length
```

"""

    if graveyard_warnings:
        prompt += graveyard_warnings

    if optimization_focus:
        focus_hints = {
            'algorithm': 'Focus on algorithmic complexity improvements (e.g., O(n²) → O(n log n))',
            'memory': 'Focus on memory allocation and data structure optimizations',
            'io': 'Focus on I/O operations and caching',
            'caching': 'Focus on adding caching or memoization',
            'loop': 'Focus on loop optimizations and vectorization'
        }
        prompt += f"""
## OPTIMIZATION FOCUS

{focus_hints.get(optimization_focus, f'Focus on: {optimization_focus}')}

"""

    if previous_attempts:
        prompt += """
## PREVIOUS ATTEMPTS (Already Tried)

The following optimization types have already been attempted for this file:
- """ + "\n- ".join(previous_attempts) + """

Please try a DIFFERENT type of optimization.

"""

    prompt += """
## OUTPUT FORMAT

Output ONLY a unified diff in this format:

```diff
--- a/path/to/file.py
+++ b/path/to/file.py
@@ -line,count +line,count @@
 context line
-removed line
+added line
 context line
```

If you cannot find a safe optimization, output:
```
NO_OPTIMIZATION_FOUND
```

Now propose your optimization:
"""

    return prompt


def parse_llm_response(response: str) -> Optional[OptimizationProposal]:
    """
    Parse LLM response to extract diff and metadata.
    """
    if "NO_OPTIMIZATION_FOUND" in response:
        return None

    # Extract diff from response
    diff_content = ""
    in_diff = False

    for line in response.split('\n'):
        if line.startswith('```diff'):
            in_diff = True
            continue
        elif line.startswith('```') and in_diff:
            break
        elif in_diff:
            diff_content += line + '\n'

    if not diff_content:
        # Try to find diff without code block
        if '---' in response and '+++' in response:
            lines = response.split('\n')
            start = next((i for i, l in enumerate(lines) if l.startswith('---')), 0)
            diff_content = '\n'.join(lines[start:])

    if not diff_content.strip():
        return None

    # Try to extract optimization type from response
    optimization_type = "unknown"
    type_hints = {
        'algorithm': ['complexity', 'O(n', 'algorithm', 'quadratic', 'linear'],
        'memory': ['memory', 'allocation', 'cache', 'memoi'],
        'io': ['I/O', 'file', 'network', 'buffer'],
        'caching': ['cache', 'memoiz', 'store', 'remember'],
        'loop': ['loop', 'vectoriz', 'unroll', 'iteration']
    }

    response_lower = response.lower()
    for opt_type, hints in type_hints.items():
        if any(hint in response_lower for hint in hints):
            optimization_type = opt_type
            break

    # Extract description (usually first paragraph)
    description = ""
    for line in response.split('\n'):
        if line.strip() and not line.startswith('```') and not line.startswith('---') and not line.startswith('+++') and not line.startswith('@@'):
            description = line.strip()
            break

    return OptimizationProposal(
        diff_content=diff_content.strip(),
        optimization_type=optimization_type,
        description=description or "Performance optimization",
        expected_benefit="Unknown - benchmark required",
        risk_level="medium",
        affected_functions=[]  # Would need AST analysis
    )


def validate_diff_syntax(diff_content: str) -> tuple[bool, str]:
    """Validate that a diff is syntactically correct"""
    lines = diff_content.split('\n')

    has_source = False
    has_target = False
    has_hunk = False

    for line in lines:
        if line.startswith('--- '):
            has_source = True
        elif line.startswith('+++ '):
            has_target = True
        elif line.startswith('@@ '):
            has_hunk = True

    if not has_source:
        return False, "Missing source file line (---)"
    if not has_target:
        return False, "Missing target file line (+++)"
    if not has_hunk:
        return False, "Missing hunk header (@@)"

    return True, "Valid diff format"


def create_placeholder_proposal(
    file_path: Path,
    optimization_type: str = "placeholder"
) -> OptimizationProposal:
    """Create a placeholder proposal for testing"""
    return OptimizationProposal(
        diff_content=f"""--- a/{file_path}
+++ b/{file_path}
@@ -1,1 +1,1 @@
-pass
+# Placeholder optimization
""",
        optimization_type=optimization_type,
        description="Placeholder for testing",
        expected_benefit="N/A",
        risk_level="low",
        affected_functions=[]
    )


def main():
    parser = argparse.ArgumentParser(
        description="Generate optimization proposals for source files"
    )
    parser.add_argument(
        "target",
        type=Path,
        help="Source file to optimize"
    )
    parser.add_argument(
        "--unit-test",
        type=Path,
        help="Path to unit test file (included in prompt)"
    )
    parser.add_argument(
        "--graveyard",
        type=Path,
        help="Path to graveyard JSON file"
    )
    parser.add_argument(
        "--focus",
        choices=['algorithm', 'memory', 'io', 'caching', 'loop'],
        help="Focus area for optimization"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output file for the prompt (default: stdout)"
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Just analyze the file, don't generate prompt"
    )

    args = parser.parse_args()

    target = args.target.resolve()

    if not target.exists():
        print(f"Error: {target} does not exist")
        return 1

    if args.analyze:
        opportunities = analyze_file_for_optimizations(target)
        print(json.dumps(opportunities, indent=2))
        return 0

    # Read source file
    file_content = target.read_text()

    # Read unit test if provided
    unit_test_content = None
    if args.unit_test and args.unit_test.exists():
        unit_test_content = args.unit_test.read_text()

    # Read graveyard warnings
    graveyard_warnings = None
    if args.graveyard and args.graveyard.exists():
        try:
            with open(args.graveyard) as f:
                graveyard_data = json.load(f)
            # Generate warning text from graveyard
            if graveyard_data.get("entries"):
                graveyard_warnings = "\n## ⚠️ FAILED OPTIMIZATIONS TO AVOID\n\n"
                for entry in graveyard_data["entries"][-5:]:
                    graveyard_warnings += f"- {entry.get('failure_reason', 'Unknown failure')}\n"
        except:
            pass

    # Generate prompt
    prompt = generate_prompt_for_llm(
        file_path=target,
        file_content=file_content,
        unit_test_content=unit_test_content,
        graveyard_warnings=graveyard_warnings,
        optimization_focus=args.focus
    )

    # Output
    if args.output:
        args.output.write_text(prompt)
        print(f"Prompt written to {args.output}")
    else:
        print(prompt)

    return 0


if __name__ == "__main__":
    exit(main())
