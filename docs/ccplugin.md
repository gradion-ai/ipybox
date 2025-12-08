# Claude Code plugin

This plugin installs ipybox as an MCP server in Claude Code along with a *codeact* skill. The plugin demonstrates interactive code action development where an agent generates and executes Python code that calls MCP tools programmatically. This is not a production-ready plugin but a prototype showing how code action development and application might work in practice.

The codeact skill provides guidance for Claude Code to discover MCP tools via filesystem search, inspect their interfaces, generate code actions that use them, and save successful code actions as reusable tools. Saved code actions become tools themselves, available for use in future code actions. Over time, a library of code actions can be built, each composing other code actions and MCP tools.

This progressive disclosure approach frees Claude Code from pre-loading tool interfaces into its system prompt. Claude Code lists available tools, reads only the interfaces it needs, generates code, and executes it in ipybox. Only relevant sources are loaded into the context window.

Code actions are stored with interface separated from implementation. This separation lets Claude Code inspect only the interface without being distracted by implementation details, reducing token consumption during tool discovery.

**Responsibilities:**

ipybox provides:

- Generation of typed Python tool APIs from MCP server tool schemas
- Sandboxed execution of Python code that uses the generated APIs
- Fully local code execution without cloud dependencies

The codeact skill guides Claude Code to:

- Discover and inspect tools and code actions via agentic search on the filesystem
- Select tools and code actions appropriate for the task based on their Python interfaces
- Generate and execute code in ipybox that composes MCP tools and saved code actions
- Generate output parsers that add structured return types to MCP tools lacking output schemas
- Save successful code actions with a structure optimized for discovery and reuse

## Installation

...

## Environment setup

- empty project
- install ipybox (optional)
- .env file with API keys

## Usage example

This example demonstrates the complete workflow: registering an MCP server, using its tools programmatically, generating an output parser, chaining tools in a single code action, and saving the code action for reuse.

### Register the GitHub MCP server

``` title="User prompt"
Register this MCP server under name github: {"url": "https://api.githubcopilot.com/mcp/", "headers": {"Authorization": "Bearer ${GITHUB_API_KEY}"}}
```

This registers the GitHub MCP server and generates a typed Python API for its tools under `mcptools/github/`. Each tool becomes a module named after the tool (`search_repositories`, `list_commits`, etc.). Claude Code searches and inspects these modules to understand how to use them in code actions.

### Use the GitHub MCP server programmatically

The codeact skill activates with phrases like "use the codeact skill":

```
use codeact to get the latest 5 commits of the 3 github repos of torvalds with the most stars. for each repo, output name, stars and the first line of commit messages, and the link to the commit
```

Claude Code first lists directories under `mcptools/` to see which tools are available. It then reads the tool files [search_repositories.py](generated/mcptools/github/search_repositories_orig.py) and [list_commits.py](generated/mcptools/github/list_commits.py) to understand their interfaces, as these appear relevant to the task.

Claude Code generates two code actions. The first searches for the top 3 repos of Linus Torvalds sorted by stars:

```python
import json
from mcptools.github import search_repositories, list_commits

# Search for torvalds' repositories sorted by stars (descending)
repos_result = search_repositories.run(search_repositories.Params(
    query="user:torvalds",
    sort=search_repositories.Sort.stars,
    order=search_repositories.Order.desc,
    perPage=10,
    minimal_output=False
))

repos_data = json.loads(repos_result)
print(f"Found {repos_data['total_count']} repos")

# Get top 3 repos
top_repos = repos_data['items'][:3]
for repo in top_repos:
    print(f"- {repo['name']}: {repo['stargazers_count']} stars")
```

Claude Code makes assumptions about the response structure. The GitHub MCP server tools do not provide output schemas, so Claude Code infers the structure from its training data. These assumptions may or may not be correct depending on the MCP server's popularity, but in this example they work. MCP tools that provide output schemas get a generated `Result` class with typed fields, but the GitHub MCP server tools return unstructured strings.

The second code action uses the repository information stored in `top_repos` to get the latest 5 commits of each repo:

```python
# Get latest 5 commits for each of the top 3 repos
for repo in top_repos:
    repo_name = repo['name']
    stars = repo['stargazers_count']

    print(f"\n{'='*60}")
    print(f"📦 {repo_name} | ⭐ {stars:,} stars")
    print(f"{'='*60}")

    # Get commits
    commits_result = list_commits.run(list_commits.Params(
        owner="torvalds",
        repo=repo_name,
        perPage=5
    ))

    commits_data = json.loads(commits_result)

    for i, commit in enumerate(commits_data[:5], 1):
        sha = commit['sha']
        short_sha = sha[:7]
        message = commit['commit']['message'].split('\n')[0]  # First line only
        url = commit['html_url']

        print(f"\n{i}. {message}")
        print(f"   🔗 {url}")
```

This prints the requested information. However, intermediate results were added to the agent's context window. To encourage Claude Code to chain `search_repositories` and `list_commits` in a single code action, we generate an output parser for `search_repositories`.

### Generate an output parser

To compensate for the lack of output schemas, we generate an output parser for the `search_repositories` tool:

```
generate an output parser for search_repositories
```

This adds a `run_parsed()` function to [search_repositories.py](generated/mcptools/github/search_repositories.py), returning a structured `ParseResult`. Claude Code infers this type by interacting with the tool using example inputs. The codeact skill encourages Claude Code to prioritize `run_parsed()` over `run()` when generating code actions.

The implementation details of parsing are stored separately in [mcpparse/github/search_repositories.py](generated/mcpparse/github/search_repositories.py). Keeping implementation separate from interface prevents polluting the interfaces that Claude Code reads.

### Chaining tools in a single code action

Running the same task again (optionally after restarting Claude Code), Claude Code now chains the tools in a single code action. It uses the new `run_parsed()` function and navigates the structured output based on the `ParseResult` type:

```
use codeact to get the latest 5 commits of the 3 github repos of torvalds with the most stars. for each repo, output name, stars and the first line of commit messages, and the link to the commit
```

```python
import json
from mcptools.github import search_repositories, list_commits

# Get Torvalds' repos sorted by stars
repos_result = search_repositories.run_parsed(
    search_repositories.Params(
        query="user:torvalds",
        sort=search_repositories.Sort.stars,
        order=search_repositories.Order.desc,
        perPage=3
    )
)

# Get top 3 repos
top_repos = repos_result.repositories[:3]
print(f"Found {len(top_repos)} repos\n")

for repo in top_repos:
    print(f"📦 {repo.name} ⭐ {repo.stargazers_count:,} stars")
    print("-" * 60)

    # Get latest 5 commits
    commits_raw = list_commits.run(
        list_commits.Params(
            owner="torvalds",
            repo=repo.name,
            perPage=5
        )
    )

    # Parse the commits JSON
    commits = json.loads(commits_raw)

    for commit in commits[:5]:
        sha = commit["sha"][:7]
        message = commit["commit"]["message"].split("\n")[0]
        url = commit["html_url"]
        print(f"  {sha}: {message}")
        print(f"         {url}")

    print()
```

### Saving code actions as tools

Code actions can be saved and reused as tools in later code actions. To save the previous code action:

```
save this as code action under github category with name commits_of_top_repos. Make username, top_n_repos and last_n_commits parameters
```

This creates a new package under `gentools/github/commits_of_top_repos/` with an [api.py](generated/gentools/github/commits_of_top_repos/api.py) that defines the typed interface and an [impl.py](generated/gentools/github/commits_of_top_repos/impl.py) that contains the implementation. The interface in `api.py` exposes the tool's parameters and return types. The implementation in `impl.py` contains the code that Claude Code does not need to inspect when using the tool.

### Using saved code actions as tools

After restarting Claude Code (to force re-discovery of tools), the same task now uses the saved code action:

```
use codeact to get the latest 5 commits of the 3 github repos of torvalds with the most stars. for each repo, output name, stars and the first line of commit messages, and the link to the commit
```

```python
from gentools.github.commits_of_top_repos import run

results = run(username="torvalds", top_n_repos=3, last_n_commits=5)

for repo in results:
    print(f"\n## {repo.name} ({repo.stars:,} ⭐)")
    print("-" * 60)
    for commit in repo.commits:
        print(f"• {commit.message}")
        print(f"  {commit.url}")
```

This pattern supports building a library of code actions. Each saved code action becomes a tool available for use in future code actions, enabling composition and reuse.
