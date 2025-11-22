## [DEV] Part $1$: Creating the `heapx` module.

1. *Create a new virtual environment* using the command:
  `python -m venv .<env-name>`

2. *Activate the created environment* using the command:
  `source .<env-name>/bin/activate`

3. *Ensure the necessary tooling is installed* using the command:
  `python -m pip install --upgrade pip build twine`

4. **Ensure the repository is clean**. The folder structure should match the below:
```bash
  (iheap) margiela@margiela heapx % tree
  .
  ├── LICENSE
  ├── MANIFEST.in
  ├── pyproject.toml
  ├── README.md
  ├── setup.py
  ├── src
  │   └── heapx
  │       ├── __init__.py
  │       └── heapx.c
  └── USAGE_GUIDE.md

  3 directories, 8 files
```

5. *Build the sdist and wheel distributions* using the command:
  `python -m build --sdist --wheel`

6. *Check the generated sdist and wheel distribution builds* using the below command:
  `python -m twine check dist/*`

7. *Ensure that the python version matches the wheel's dist/cpXXX version tag* using the below command:
  `tree && python --version`

8. *Confirm that the python and pip belongs to the created .<env-name>* using the below command:
  `which python && which pip`

---

## [DEV] Part $2$: Install `heapx` development build to venv.

1. *Install the wheel distribution directly* in MacOS using the command:
  `python -m pip install dist/heapx-V.V.V-cpXXX-cpXXX-macosx_12_0_arm64.whl`
  Please note that in the above command $V.V.V$ represents the heapx module version and $XXX$ represents the desired python version.

2. *Install the sdist distribution directly* using the command:
  `python -m pip install dist/heapx-V.V.V.tar.gz`
  Please note that in the above command $V.V.V$ represents the heapx module version.

3. *Install the dource distribution* in the project directory root using the command:
  `python -m pip install -e .`

---

## [DEV] Part $3$: Execute the test suite.

The `tests/` directory contains comprehensive installation verification tests that validate the heapx module works correctly across different installation methods. The test suite automatically builds distributions, runs tests, and cleans up artifacts.

### Understanding the Test Structure

The test suite is designed to verify three critical installation workflows:

1. **Wheel Installation Test**: Validates that the pre-compiled wheel (`.whl`) installs correctly and all functions work as expected.

2. **Source Distribution Test**: Validates that the source distribution (`.tar.gz`) compiles the C extension correctly and all functions work as expected.

3. **Editable Installation Test**: Validates that the development installation (`pip install -e .`) works correctly for local development.

Each test creates an isolated temporary virtual environment to avoid polluting your development environment, installs the package, and runs comprehensive smoke tests that verify all seven core heap operations: `heapify`, `push`, `pop`, `sort`, `remove`, `replace`, and `merge`.

### Prerequisites for Running Tests

1. *Ensure pytest is installed* in your virtual environment using the command:
  `python -m pip install pytest`

2. *Ensure the build tools are installed* using the command:
  `python -m pip install --upgrade pip build twine`

### Executing the Test Suite

1. *Run all tests with automatic build and cleanup* using the command:
  `pytest tests/ -v`

  The `-v` flag provides verbose output showing each test's status. The test suite will automatically:
  - Build the wheel and sdist distributions before running tests
  - Execute all test files in the `tests/` directory
  - Clean up all build artifacts (`dist/`, `build/`, `*.egg-info/`) after tests complete

2. *Run a specific test file* using the command:
  `pytest tests/build.py -v`

3. *Run tests with detailed output* including print statements using the command:
  `pytest tests/ -v -s`

4. *Run tests and stop at first failure* for faster debugging using the command:
  `pytest tests/ -v -x`

### Alternative: Run Tests Directly as Python Script

The `tests/build.py` file can also be executed directly as a standalone Python script without pytest:

1. *Build the distributions first* using the command:
  `python -m build --sdist --wheel`

2. *Execute the test script directly* using the command:
  `python tests/build.py`

  This will output a JSON summary of test results:
  ```json
  {
    "wheel": "ok",
    "sdist": "ok",
    "editable": "ok"
  }
  ```

### Understanding Test Output

**Successful Test Output:**
```bash
tests/build.py::test_install_wheel_and_smoke PASSED
tests/build.py::test_install_sdist_and_smoke PASSED
tests/build.py::test_install_editable_and_smoke PASSED
```

**Failed Test Output:**
If a test fails, you will see detailed error messages indicating:
- Which installation method failed (wheel, sdist, or editable)
- The specific operation that failed (import, heapify, push, pop, etc.)
- The expected vs. actual output
- Full stdout and stderr from the failed operation

### Cleaning Up Build Artifacts Manually

If you need to manually clean up build artifacts without running tests, use the below commands:

1. *Remove distribution artifacts* using the command:
  `rm -rf dist/`

2. *Remove build artifacts* using the command:
  `rm -rf build/`

3. *Remove egg-info directories* using the command:
  `rm -rf *.egg-info src/*.egg-info`

4. *Remove all build artifacts at once* using the command:
  `rm -rf dist/ build/ *.egg-info src/*.egg-info`

### Test Configuration

The test suite is configured via `tests/conftest.py`, which contains pytest fixtures that:
- Automatically build distributions before any tests run (session-scoped fixture)
- Automatically clean up all build artifacts after all tests complete
- Ensure tests run in isolated temporary virtual environments

This configuration ensures that running `pytest tests/` is a complete, self-contained operation that leaves your repository clean.

---

