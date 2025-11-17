"""heapx: A Python wrapper for a C-based heap implementation."""

# Try to import the compiled extension module. Different build setups
# may create either "_heapx" (underscore) or "heapx" (no underscore).
_ext = None
for ext_name in ("_heapx", "heapx"):
  try:
    _ext = __import__(f"{__name__}.{ext_name}", fromlist=["*"])
    break
  except Exception: _ext = None

if (_ext is None):
  # If the compiled extension is not available, provide a clear ImportError
  raise ImportError(
    "The compiled heapx extension is not available. "
    "If you installed from source, ensure a build step compiled the C extension. "
    "If you are developing, run: python -m build or python setup.py build_ext --inplace."
  )

# Re-export public symbols from the compiled extension
# (only names that do not start with an underscore).
_public_names = [n for n in dir(_ext) if not n.startswith("_")]
globals().update({name: getattr(_ext, name) for name in _public_names})

# Version provided by setuptools_scm via generated file src/heapx/_version.py
try:
  from ._version import version as __version__
except Exception: __version__ = "0+unknown"

# Public API listing
__all__ = _public_names + ["__version__"]
