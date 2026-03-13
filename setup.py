#!/usr/bin/env python3
"""
Build configuration for the heapx C extension.

All package metadata lives in pyproject.toml. This file exists solely to
define the C extension module and apply platform-specific compiler optimizations.
"""

import os
import sys
import platform
from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext


class OptimizedBuildExt(build_ext):
  """Custom build_ext that applies platform-specific C compiler optimizations."""

  def build_extensions(self):
    compiler_type = self._detect_compiler()
    for ext in self.extensions:
      self._apply_optimizations(ext, compiler_type)
    super().build_extensions()

  def _detect_compiler(self):
    compiler = self.compiler.compiler_type
    if compiler == 'msvc':
      return 'msvc'
    if compiler in ('unix', 'mingw32'):
      cc = os.environ.get('CC', 'cc')
      try:
        out = os.popen(f"'{cc}' --version 2>/dev/null").read().lower()
        return 'clang' if 'clang' in out else 'gcc'
      except Exception:
        return 'gcc'
    return 'generic'

  def _apply_optimizations(self, ext, compiler_type):
    arch = platform.machine().lower()
    is_64bit = sys.maxsize > 2**32
    is_conda = os.environ.get('CONDA_BUILD', '') == '1'
    is_cibuildwheel = os.environ.get('CIBUILDWHEEL', '') == '1'

    common = ['-DNDEBUG', '-DPY_SSIZE_T_CLEAN']

    if compiler_type in ('clang', 'gcc'):
      # Safe floating-point flags that preserve IEEE 754 NaN semantics
      safe_fp = ['-fno-math-errno', '-fno-signed-zeros']

      if is_conda:
        # Conda builds: portable baseline — no -march=native
        if ('x86' in arch) and is_64bit:
          arch_flags = ['-march=x86-64-v2']
        elif ('arm' in arch) or ('aarch' in arch):
          arch_flags = []  # conda-forge sets its own ARM baseline
        else:
          arch_flags = []
      elif is_cibuildwheel:
        # cibuildwheel builds: portable baselines for wheel compatibility
        # aarch64 wheels run under QEMU emulation where -march=native fails
        if ('x86' in arch) and is_64bit:
          arch_flags = ['-march=x86-64-v2', '-mtune=generic']
        elif ('arm' in arch) or ('aarch' in arch):
          arch_flags = ['-march=armv8-a', '-mtune=generic']
        else:
          arch_flags = []
      else:
        # Local / pip builds: use native tuning for maximum performance
        arch_flags = ['-march=native', '-mtune=native']

      opts = ['-O3'] + arch_flags + ['-flto'] + safe_fp + ['-funroll-loops']

      if compiler_type == 'clang':
        opts += ['-fvectorize', '-fslp-vectorize',
                 '-Wno-unused-function', '-Wno-gcc-compat']
      else:
        opts += ['-ftree-vectorize', '-Wno-unused-function']

      ext.extra_compile_args = opts + common
      ext.extra_link_args = ['-flto']

    elif compiler_type == 'msvc':
      # /fp:precise preserves NaN semantics (unlike /fp:fast)
      ext.extra_compile_args = ['/O2', '/Ot', '/GL', '/fp:precise'] + common
      ext.extra_link_args = ['/LTCG']

    else:
      ext.extra_compile_args = ['-O3'] + common
      ext.extra_link_args = []

    # Platform definitions
    if sys.platform == 'win32':
      ext.define_macros.append(('OS_WINDOWS', '1'))
    elif sys.platform == 'darwin':
      ext.define_macros.append(('OS_MACOS', '1'))
    elif sys.platform.startswith('linux'):
      ext.define_macros.append(('OS_LINUX', '1'))

    # Architecture definitions
    if ('x86' in arch) and is_64bit:
      ext.define_macros.append(('ARCH_X64', '1'))
    elif ('arm' in arch) or ('aarch' in arch):
      ext.define_macros.append(('ARCH_ARM64', '1'))


heapx_extension = Extension(
  name='heapx._heapx',
  sources=['src/heapx/heapx.c'],
  language='c',
  define_macros=[('PY_SSIZE_T_CLEAN', None)],
)

setup(
  ext_modules=[heapx_extension],
  cmdclass={'build_ext': OptimizedBuildExt},
)
