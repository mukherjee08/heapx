
'''
Pytest's configuration & testing (conftest) with automatic build and cleanup.
This file is automatically discovered by pytest.
*This is the 'configuration/infrastructure file', and not a test file*.

# Implementation Analysis

(HOOK) def pytest_configure(config):
  Runs once at 'pytest' startup, before the test collection.
  Installs heapx in editable mode so the C extension is compiled and importable.

(HOOK) def pytest_collection_finish(session):
  Runs after all tests are collected but before execution. 
  Prints a numbered list of all test cases for visibility.

(Session-scoped fixture) def build_distributions():
  Automatically runs for every test session. 
  Builds wheel/sdist before tests, cleans up all artifacts after tests complete.
'''

import shutil, subprocess, sys, pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent # Get the root dir
DIST_DIR     = PROJECT_ROOT / "dist"        # Get the dist distribution dir
BUILD_DIR    = PROJECT_ROOT / "build"       # Get the build distribution dir
SRC_DIR      = PROJECT_ROOT / "src"         # Get the src distribution dir

def pytest_configure(config):
  """Build and install package before test collection."""
  try:
    # First, clean up any existing installation
    for egg_dir in PROJECT_ROOT.glob("*.egg-info"):
      shutil.rmtree(egg_dir, ignore_errors=True)
    for egg_dir in SRC_DIR.glob("**/*.egg-info"):
      shutil.rmtree(egg_dir, ignore_errors=True)
    
    # Install in editable mode
    result = subprocess.run(
      [sys.executable, "-m", "pip", "install", "-e", ".", "--force-reinstall", "--no-deps"],
      cwd=PROJECT_ROOT,
      capture_output=True,
      text=True
    )
    if result.returncode != 0:
      print(f"Installation failed:\n{result.stderr}")
      raise RuntimeError("Package installation failed")
      
  except Exception as e:
    print(f"Error in pytest_configure: {e}")
    raise
  
  return None

def pytest_collection_finish(session):
  """Print test cases after collection, before execution."""
  window_size = shutil.get_terminal_size().columns
  print("\n" + "=" * window_size)
  print("COLLECTED TEST CASES:")
  print("=" * window_size)
  for i, item in enumerate(session.items, 1):
    print(f" {i}. {item.nodeid}")
  print("=" * window_size + "\n")

  return None

@pytest.fixture(scope="session", autouse=True)
def build_distributions():
  """Build wheel and sdist for distribution tests."""
  print("Building distributions...")
  
  # Clean up any existing build artifacts first
  if DIST_DIR.exists():
    shutil.rmtree(DIST_DIR, ignore_errors=True)
  if BUILD_DIR.exists():
    shutil.rmtree(BUILD_DIR, ignore_errors=True)
  
  # Build with verbose output
  result = subprocess.run(
    [sys.executable, "-m", "build", "--sdist", "--wheel"],
    cwd=PROJECT_ROOT,
    capture_output=True,
    text=True
  )
  
  if result.returncode != 0:
    print(f"Build failed:\n{result.stderr}")
    raise RuntimeError("Distribution build failed")
  else:
    print(f"Build output:\n{result.stdout}")
  
  yield # Run all tests
  
  # Always run cleanup, even if tests fail
  print("\nCleaning up build artifacts...")
  
  cleanup()

  return None

def cleanup():
  """Clean up all build artifacts."""
  # Cleanup build artifacts
  if DIST_DIR.exists():
    shutil.rmtree(DIST_DIR, ignore_errors=True)
    print(f"Removed: {DIST_DIR}")
  
  if BUILD_DIR.exists():
    shutil.rmtree(BUILD_DIR, ignore_errors=True)
    print(f"Removed: {BUILD_DIR}")
  
  # Cleanup egg-info directories
  for egg_dir in PROJECT_ROOT.glob("*.egg-info"):
    shutil.rmtree(egg_dir, ignore_errors=True)
    print(f"Removed: {egg_dir}")
  
  for egg_dir in SRC_DIR.glob("**/*.egg-info"):
    shutil.rmtree(egg_dir, ignore_errors=True)
    print(f"Removed: {egg_dir}")
  
  # Cleanup compiled extensions - check recursively
  for ext_pattern in ["**/*.so", "**/*.pyd", "**/*.dll", "**/*.cpython-*"]:
    for ext_file in SRC_DIR.glob(ext_pattern):
      try:
        ext_file.unlink()
        print(f"Removed: {ext_file}")
      except FileNotFoundError:
        pass
  
  # Cleanup __pycache__ directories
  for pycache in PROJECT_ROOT.glob("**/__pycache__"):
    shutil.rmtree(pycache, ignore_errors=True)
    print(f"Removed: {pycache}")

  return None

# Also register the cleanup as a pytest hook for final cleanup
def pytest_unconfigure(config):
  """Final cleanup after all tests are done."""
  print("\nPerforming final cleanup...")
  
  cleanup()

  return None
