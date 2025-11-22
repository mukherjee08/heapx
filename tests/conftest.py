"""Pytest configuration with automatic build and cleanup."""
import shutil, subprocess, pytest # type: ignore
from   pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DIST_DIR     = PROJECT_ROOT / "dist"
BUILD_DIR    = PROJECT_ROOT / "build"

@pytest.fixture(scope="session", autouse=True)
def build_distributions():
  """Build wheel and sdist before tests, cleanup after."""

  subprocess.run(
    ["python", "-m", "build", "--sdist", "--wheel"],
    cwd=PROJECT_ROOT,
    check=True,
    capture_output=True
  )
  
  yield # Run all tests

  # Cleanup
  if DIST_DIR.exists() : shutil.rmtree(DIST_DIR)
  if BUILD_DIR.exists(): shutil.rmtree(BUILD_DIR)
  for egg_dir in PROJECT_ROOT.glob("*.egg-info"): shutil.rmtree(egg_dir)
  for egg_dir in (PROJECT_ROOT / "src").glob("*.egg-info"): shutil.rmtree(egg_dir)
