from setuptools import setup, Extension
import sys
import platform

# Compiler flags
extra_compile_args = ['-O3', '-DNDEBUG']
if platform.system() == 'Darwin':
    extra_compile_args.extend(['-Wno-unreachable-code', '-Wno-unused-function'])
elif platform.system() == 'Linux':
    extra_compile_args.extend(['-Wno-unused-function'])

heapx_module = Extension(
    '_heapx',
    sources=['heapx_modified.c'],
    extra_compile_args=extra_compile_args,
)

setup(
    name='heapx_fast',
    version='1.0.0',
    ext_modules=[heapx_module],
)
