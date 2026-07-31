#!/usr/bin/env python3
"""Setup configuration for HUSTLER."""

from setuptools import setup

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="hustler",
    version="0.37.1",
    author="Iain Hoggan",
    description="UK Pool Physics Sandbox — WEPF-compliant real-world pool physics with utility AI",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ihoggan/hustler",
    py_modules=["hustler", "cushion_path"],
    python_requires=">=3.12",
    # Two dependencies, deliberately. No numpy, no asset libraries -- the
    # game synthesises everything it draws and plays. See CONTRIBUTING.md.
    install_requires=[
        "pygame>=2.6.1",
        "pymunk>=7.3.0",
    ],
    # r31: this listed pytest and pylint, neither of which the project uses
    # (the assertion suite is built into hustler.py behind --selftest, and CI
    # installed pylint without ever running it) and omitted isort, which CI
    # does gate on. These are now the tools actually used.
    extras_require={
        "dev": ["isort", "pyflakes"],
    },
    entry_points={
        "console_scripts": [
            "hustler=hustler:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Games/Entertainment",
        "Topic :: Scientific/Engineering :: Physics",
    ],
    keywords="pool billiards physics simulation pygame pymunk ai",
)
