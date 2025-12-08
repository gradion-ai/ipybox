import json
import os
import urllib.request
from sys import platform

import jsonschema
from invoke import task


@task
def precommit_install(c):
    """Install pre-commit hooks."""
    c.run("pre-commit install")


@task(aliases=["cc"])
def code_check(c):
    """Run coding conventions checks."""
    c.run("pre-commit run --all-files")


@task
def test(c, cov=False):
    _run_pytest(c, "tests", cov)


@task(aliases=["ut"])
def unit_test(c, cov=False):
    _run_pytest(c, "tests/unit", cov)


@task(aliases=["it"])
def integration_test(c, cov=False):
    _run_pytest(c, "tests/integration", cov)


def _run_pytest(c, test_dir, cov=False):
    c.run(f"pytest -xsv {test_dir} {_pytest_cov_options(cov)}", pty=_use_pty())


def _use_pty():
    return platform != "win32"


def _pytest_cov_options(use_cov: bool):
    if not use_cov:
        return ""
    return "--cov=ipybox --cov-report=term"


@task
def build_docs(c):
    """Build documentation with MkDocs."""
    c.run("mkdocs build")


@task
def serve_docs(c):
    """Serve documentation locally with MkDocs."""
    c.run("mkdocs serve -a 0.0.0.0:8000")


@task
def deploy_docs(c):
    """Deploy documentation to GitHub Pages."""
    c.run("mkdocs gh-deploy --force")


@task
def latest_tag(c):
    """Get the latest git tag."""
    result = c.run("git describe --tags --abbrev=0", hide=True, warn=True)
    if result.ok:
        return result.stdout.strip()
    return "0.0.0-dev"


@task()
def mcp_sync(c):
    """Update server.json with version from environment or git tag."""
    version = os.environ.get("VERSION") or latest_tag(c)

    with open("server.json", "r") as f:
        data = json.load(f)

    data["version"] = version
    if "packages" in data:
        for package in data["packages"]:
            package["version"] = version

    with open("server.json", "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


@task(aliases=["mcp-val"])
def mcp_validate(c, schema_path=".mcpregistry_schema.json"):
    """Validate server.json against MCP schema."""
    schema_url = "https://static.modelcontextprotocol.io/schemas/2025-10-17/server.schema.json"

    if not os.path.exists(schema_path):
        with urllib.request.urlopen(schema_url) as response:
            schema_content = response.read().decode("utf-8")
        with open(schema_path, "w") as f:
            f.write(schema_content)

    with open("server.json", "r") as f:
        server_data = json.load(f)

    with open(schema_path, "r") as f:
        schema = json.load(f)

    jsonschema.validate(server_data, schema)
