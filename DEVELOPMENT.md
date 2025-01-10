# Development Guide

This guide provides instructions for setting up a development environment for `ipybox`. Follow these steps to get started with development, testing, and contributing to the project.

Clone the repository:

```bash
git clone https://github.com/gradion-ai/ipybox.git
cd ipybox
```

Create a new Conda environment and activate it:

```bash
conda env create -f environment.yml
conda activate ipybox
```

Install dependencies with Poetry:

```bash
poetry install --with dev --with docs
```

Install pre-commit hooks:

```bash
invoke precommit-install
```

Enforce coding conventions (done automatically by pre-commit hooks):

```bash
invoke cc
```

Run tests:

```bash
pytest -s tests
```
