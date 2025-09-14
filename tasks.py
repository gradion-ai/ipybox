import json
import os
from sys import platform

from invoke import task


@task
def precommit_install(c):
    c.run("pre-commit install")


@task(aliases=["cc"])
def code_check(c):
    c.run("pre-commit run --all-files")


@task
def build_docs(c):
    c.run("mkdocs build")


@task
def serve_docs(c):
    c.run("mkdocs serve -a 0.0.0.0:8000")


@task
def deploy_docs(c):
    c.run("mkdocs gh-deploy --force")


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
def latest_tag(c):
    """Get the latest git tag"""
    result = c.run("git describe --tags --abbrev=0", hide=True, warn=True)
    if result.ok:
        return result.stdout.strip()
    return "0.0.0-dev"


@task()
def mcp_sync(c):
    """Update server.json with version from environment or git tag"""
    # Get version from environment variable (set by GitHub Actions) or fallback to latest tag
    version = os.environ.get("VERSION") or latest_tag(c)

    # Read server.json
    with open("server.json", "r") as f:
        data = json.load(f)

    # Update version fields
    data["version"] = version
    if "packages" in data:
        for package in data["packages"]:
            package["version"] = version

    # Write back to server.json
    with open("server.json", "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


@task(aliases=["mcp-val"])
def mcp_validate(c):
    """Validate server.json against MCP schema"""
    import tempfile
    import urllib.request

    import jsonschema

    # Download schema to temp file
    schema_url = "https://static.modelcontextprotocol.io/schemas/2025-07-09/server.schema.json"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as temp_schema:
        with urllib.request.urlopen(schema_url) as response:
            schema_content = response.read().decode("utf-8")
            temp_schema.write(schema_content)
            temp_schema_path = temp_schema.name

    try:
        # Read server.json
        with open("server.json", "r") as f:
            server_data = json.load(f)

        # Read schema
        with open(temp_schema_path, "r") as f:
            schema = json.load(f)

        # Validate - will raise exception if invalid
        jsonschema.validate(server_data, schema)
    finally:
        # Clean up temp file
        os.unlink(temp_schema_path)
