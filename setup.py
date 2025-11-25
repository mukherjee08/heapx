#!/usr/bin/env python3
"""
Ultra-optimized heap operations Python extension build configuration.

This setup script builds the heapx C extension with maximum optimizations
for different platforms and compilers.
"""

import os
import sys
import platform
from setuptools import setup, Extension, find_packages
from setuptools.command.build_ext import build_ext

class UltraOptimizedBuildExt(build_ext):
  """Custom build extension with ultra optimizations for different platforms."""
  
  def build_extensions(self):
    """Apply platform-specific optimizations."""
    compiler_type = self.get_compiler_type()
    
    for ext in self.extensions:
      self.apply_ultra_optimizations(ext, compiler_type)
      
    super().build_extensions()
  
  def get_compiler_type(self):
    """Determine compiler type for optimization flags."""
    compiler = self.compiler.compiler_type
    
    if (compiler == 'msvc'): return 'msvc'
    elif (compiler in ['unix', 'mingw32']):
      
      # Detect specific Unix compilers
      # Use a safer check for compiler version
      cc_env = os.environ.get('CC', 'cc')
      try:
        version_output = os.popen(f"'{cc_env}' --version 2>/dev/null").read().lower()
        if ('clang' in version_output): return 'clang'
        else: return 'gcc' # Default to gcc if clang not detected
      except: return 'gcc' # Fallback on error
    else: return 'generic'

  def apply_ultra_optimizations(self, ext, compiler_type):
    """Apply maximum optimizations based on compiler and platform."""
    # Common optimizations for all platforms
    common_opts = ['-DNDEBUG', '-DPY_SSIZE_T_CLEAN']
    
    # Architecture-specific optimizations
    arch = platform.machine().lower()
    is_64bit = sys.maxsize > 2**32
    
    if (compiler_type == 'clang'):
      opts = [
        '-O3', '-march=native', '-mtune=native', '-flto', '-ffast-math',
        '-funroll-loops', '-fvectorize', '-fslp-vectorize',
        '-Wno-unused-function', '-Wno-gcc-compat',
      ]
      
      # ARM64 specific optimizations
      if (('arm' in arch) or ('aarch' in arch)): opts.extend(['-mcpu=native', '-mtune=native'])
      
      # x86-64 specific optimizations
      elif (('x86' in arch) and is_64bit): opts.extend(['-mavx2', '-mbmi2', '-mpopcnt'])

    elif (compiler_type == 'gcc'):
      opts = [
        '-O3', '-march=native', '-mtune=native', '-flto', '-ffast-math',
        '-funroll-loops', '-ftree-vectorize', '-Wno-unused-function',
      ]
      
      # ARM64 specific optimizations
      if (('arm' in arch) or ('aarch' in arch)): opts.extend(['-mcpu=native', '-mtune=native'])
      
      # x86-64 specific optimizations  
      elif (('x86' in arch) and is_64bit): opts.extend(['-mavx2', '-mbmi2', '-mpopcnt'])
        
    elif (compiler_type == 'msvc'):
      opts = [
        '/O2', '/Ot', '/GL', '/arch:AVX2', '/fp:fast'
      ]
    else:
      # Generic optimizations for unknown compilers
      opts = ['-O3', '-DNDEBUG']
    
    # Add common options
    opts.extend(common_opts)
    
    # Apply to extension
    ext.extra_compile_args = opts
    
    # Linker optimizations
    if (compiler_type in ['clang', 'gcc']): ext.extra_link_args = ['-flto', '-s']
    elif (compiler_type == 'msvc'): ext.extra_link_args = ['/LTCG']
    
    # Platform-specific definitions
    if (sys.platform == 'win32'): ext.define_macros.append(('OS_WINDOWS', '1'))
    elif (sys.platform == 'darwin'): ext.define_macros.append(('OS_MACOS', '1'))
    elif (sys.platform.startswith('linux')): ext.define_macros.append(('OS_LINUX', '1'))
    
    # Architecture definitions
    if (('x86' in arch) and (is_64bit)): ext.define_macros.append(('ARCH_X64', '1'))
    elif (('arm' in arch) or ('aarch' in arch)): ext.define_macros.append(('ARCH_ARM64', '1'))

def read_long_description():
  """Read long description from README.md."""
  try: 
    with open('README.md', 'r', encoding='utf-8') as f: return f.read()
  except FileNotFoundError: return "Ultra-optimized heap operations with comprehensive functionality"

# Main heapx extension configuration
heapx_extension = Extension(
  name='heapx._heapx',
  sources=["src/heapx/heapx.c"],
  language='c',
  define_macros=[
    # Enable all optimizations
    ('PY_SSIZE_T_CLEAN', None),
  ],
  include_dirs=[],
  library_dirs=[],
  libraries=[],
  runtime_library_dirs=[],
)

setup(
  name='heapx',
  author='Aniruddha Mukherjee',
  author_email='mukher66@purdue.edu',
  description='Ultra-optimized heap operations with comprehensive functionality and superior performance',
  long_description=read_long_description(),
  long_description_content_type='text/markdown',
  url='https://github.com/ivan121500/heapx',
  project_urls={
    'Documentation': 'https://github.com/ivan121500/heapx',
    'Source': 'https://github.com/ivan121500/heapx',
    'Tracker': 'https://github.com/ivan121500/heapx',
    'Changelog': 'https://github.com/ivan121500/heapx',
  },
  classifiers=[
    'Development Status :: 5 - Production/Stable',
    'Intended Audience :: Developers',
    'Intended Audience :: Science/Research',
    'License :: OSI Approved :: MIT License',
    'Operating System :: OS Independent',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.8',
    'Programming Language :: Python :: 3.9',
    'Programming Language :: Python :: 3.10',
    'Programming Language :: Python :: 3.11',
    'Programming Language :: Python :: 3.12',
    'Programming Language :: Python :: 3.13',
    'Programming Language :: Python :: 3.14',
    'Programming Language :: Python :: Implementation :: CPython',
    'Topic :: Software Development :: Libraries :: Python Modules',
    'Topic :: Scientific/Engineering',
    'Topic :: System :: Hardware',
    'Topic :: Utilities',
    'Typing :: Typed',
  ],
  python_requires='>=3.8',
  install_requires=[],
  extras_require={
    'dev': [
      'pytest>=6.0',
      'pytest-benchmark>=3.4',
      'black>=22.0',
      'isort>=5.0',
      'mypy>=0.900',
      'flake8>=4.0',
    ],
    'test': [
      'pytest>=6.0',
      'pytest-benchmark>=3.4',
    ],
    'docs': [
      'sphinx>=4.0',
      'sphinx-rtd-theme>=1.0',
    ],
  },
  ext_modules=[heapx_extension],
  cmdclass={
    'build_ext': UltraOptimizedBuildExt,
  },
  zip_safe=False,
  include_package_data=True,
  package_dir={'': 'src'},
  packages=find_packages(where="src"),
  package_data={
    'heapx': ['*.pyi', 'py.typed'],
  },
  keywords=[
    'heap',
    'priority-queue',
    'optimized',
    'algorithm',
    'data-structures',
    'performance',
    'n-ary-heap',
    'max-heap',
    'min-heap',
  ],
  license='MIT',
  platforms=['any'],
)
