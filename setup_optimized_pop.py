"""Setup script for compiling optimized_pop.pyx"""
from setuptools import setup, Extension
from Cython.Build import cythonize
import sys

ext = Extension(
    "optimized_pop",
    sources=["optimized_pop.pyx"],
    extra_compile_args=['-O3', '-ffast-math', '-funroll-loops', '-march=native', '-mtune=native'],
)

setup(
    name="optimized_pop",
    ext_modules=cythonize([ext], language_level=3),
    script_args=['build_ext', '--inplace'],
)
