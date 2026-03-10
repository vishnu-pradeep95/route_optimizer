"""Cython build configuration for licensing module compilation.

Used inside infra/Dockerfile.build to compile license_manager.py to a
platform-specific .so extension. Run with: python cython_build.py build_ext --inplace

Scope: core/licensing/license_manager.py ONLY.
__init__.py is kept as a plain .py stub (see 06-RESEARCH.md Pitfall 1).
"""
from setuptools import setup, Extension
from Cython.Build import cythonize

extensions = [
    Extension(
        "core.licensing.license_manager",
        ["core/licensing/license_manager.py"],
        extra_compile_args=["-O2"],
    ),
]

setup(
    ext_modules=cythonize(
        extensions,
        compiler_directives={
            "language_level": "3",
            "embedsignature": False,
        },
    ),
)
