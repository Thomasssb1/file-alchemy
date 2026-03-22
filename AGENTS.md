### 1. Maintain a Clean Codebase

Eliminate noise to reduce mental overhead for both human developers and AI agents parsing the repository.

- **Remove commented-out code and unused imports:** Do not leave commented-out blocks of code in the codebase. If it is no longer needed, rely on version control (Git) and delete it entirely. Remove unused imports to keep the namespace clean and prevent linting/circular dependency issues.

```python
# Bad
import os
import sys  # sys is never used
from agent_core import Memory, Tools

# def legacy_memory_wipe():
#     Memory.clear_all()
#     print("Wiped")

def clear_agent_memory():
    Memory.clear_recent()

# Good
import os
from agent_core import Memory, Tools

def clear_agent_memory():
    Memory.clear_recent()
```

- **Follow standard Python idioms (PEP 8):** Use standard Python paradigms and type hinting. Avoid non-standard naming conventions or overriding built-in functions unless strictly necessary.

```python
# Bad - Non-standard naming, mutable default argument, missing type hints
def Add_Message(Msg, history=[]):
    history.append(Msg)
    return history

# Good - PEP 8 compliant, type hints, safe default arguments
def add_message(message: str, history: list[str] | None = None) -> list[str]:
    if history is None:
        history = []
    history.append(message)
    return history
```

- **Avoid dead code:** Remove helper functions, variables, and unreachable code blocks that are no longer utilized by your primary logic.

```python
# Bad - Unreachable code and unused variables
def process_llm_response(response: str) -> dict:
    parsed_data = json.loads(response)
    unused_token_count = len(response.split()) # Computed but never used
    return parsed_data
    print("Parsing complete") # Dead code
```

- **Don't disable lint rules inline:** Instead of bypassing `mypy` or `ruff` with inline comments (`# type: ignore`, `# noqa`), fix the underlying type mismatch or structural issue.

```python
# Bad
import json  # noqa: F401
result = agent.execute(tool_name) # type: ignore

# Good
# Remove the unused import entirely rather than suppressing the Ruff warning.
# Fix the underlying typing issue for Mypy by asserting or explicitly casting.
assert isinstance(tool_name, str)
result = agent.execute(tool_name)
```

### 2. Optimize for the Reader

Code is read far more often than it’s written. When faced with choices between concise but obscure code and more explicit but readable code, choose readability.

- **Avoid unnecessary operators or anti-patterns:** Do not use implicit boolean checks when an explicit check is required, but conversely, don't use redundant equality operators when Python's truthiness suffices.
- **Structure clear control flow:** Prefer early returns (guard clauses) and explicit `else` clauses when they improve the cognitive flow of the function.
- **Add explanatory comments:** Document _why_ you are doing something non-obvious.

**Example of applying this principle:**

```python
# Less clear - Redundant boolean checks and deeply nested logic
def parse_tool_call(tool_input: dict):
    if bool(tool_input.get("arguments")) == True:
        if len(tool_input["arguments"]) > 0:
            execute_tool(tool_input)
            return True
    return False

# More clear - Pythonic truthiness and early returns (Guard Clauses)
def parse_tool_call(tool_input: dict) -> bool:
    arguments = tool_input.get("arguments")

    # Guard clause for missing or empty arguments
    if not arguments:
        return False

    execute_tool(tool_input)
    return True
```

### 3. Ensure Comprehensive Test Coverage

Ensure thorough test coverage by systematically testing edge cases, boundary conditions, failure scenarios, and different data types.

**Key areas to cover:**

- **Boundary values:** Test minimum, maximum, and overflow conditions for numeric inputs.
- **Edge cases:** Empty strings, `None` values, malformed JSON structures, and unexpected unicode characters.
- **Failure conditions:** API timeouts and strict type mismatches.

### 4. Running Tests
When running tests locally with `pytest`, ensure you use an active virtual environment (e.g., using `.venv`) so dependencies are correctly found.

Use systematic approaches like `pytest.mark.parametrize` to ensure comprehensive coverage without duplicating test logic:

```python
import pytest
from agent_tools import parse_hex_string

# Use parameterization to thoroughly test boundary and edge cases
@pytest.mark.parametrize("input_val, expected", [
    ("0xFF", 255),               # Standard case
    ("0xff", 255),               # Case variation
    ("0x0", 0),                  # Minimum boundary
    ("0xFFFFFFFFFFFFFFFF", 18446744073709551615), # Max 64-bit integer
])
def test_parse_hex_string_success(input_val, expected):
    assert parse_hex_string(input_val) == expected

@pytest.mark.parametrize("invalid_input", [
    "0x",                        # Empty hex
    "FF",                        # Missing prefix
    None,                        # Null input
    "0xG1",                      # Invalid hex character
])
def test_parse_hex_string_failures(invalid_input):
    with pytest.raises((ValueError, TypeError)):
        parse_hex_string(invalid_input)
```

### 5. Code Formatting (Ruff)

The project utilizes `ruff` for strict code formatting to ensure consistency across the codebase.
When running the formatter locally, use the globally installed `ruff` command. Do not attempt to invoke Ruff as a module from within the project's virtual environment.

```shell
# Good
ruff format .

# Bad - attempting to call the module from the virtual environment, which may fail if not bundled locally
.\.venv\Scripts\python.exe -m ruff format .
```
