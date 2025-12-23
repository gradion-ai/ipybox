# Programmatic tool calling plugin for Claude Code

This plugin installs the [ipybox MCP server](https://gradion-ai.github.io/ipybox/mcpserver/index.md) in Claude Code along with a `codeact`[1](#fn:1) skill. It enables Claude Code to act by generating and executing code rather than JSON tool calls. The generated code calls MCP tools and previously saved code actions programmatically.

With this "code as tool" approach, saved code actions become tools themselves, available for use in future code actions. Over time, a library of code actions can be built, each composing other code actions and MCP tools.

The `codeact` skill provides guidance for Claude Code to discover MCP tools and code actions via agentic filesystem search, inspect the interfaces of relevant tools, generate code actions that use them, and save successful code actions for later reuse.

Tool search and inspection is performed on demand based on the current task. This progressive disclosure approach frees Claude Code from pre-loading tool sources into its context window, saving tokens and improving performance.

Code actions are stored with interface separated from implementation. This separation lets Claude Code inspect only the interface without being distracted by implementation details, further reducing token consumption during tool discovery.

Note

This plugin is a demonstration of the "code as tool" approach. It is a prototype that requires further optimization and refinement.

The `codeact` skill distributes responsibilities between ipybox and Claude Code:

ipybox:

- Generates typed Python tool APIs from MCP server tool schemas
- Executes Python code that uses the generated MCP tool APIs
- Uses a stateful and sandboxed IPython kernel for code execution

Claude Code:

- Discovers and selects MCP tools and stored code actions via agentic search
- Generates and executes code in ipybox that calls selected MCP tools and code actions
- Adds output parsers and structured result types to MCP tools that lack output schemas
- Saves successful code actions with a structure optimized for discovery and reuse

## Environment setup

The [example below](#usage-example) uses the [GitHub MCP server](https://github.com/github/github-mcp-server). Create a `.env` file with your GitHub personal access token (PAT) in the current working directory:

.env

```
GITHUB_API_KEY=your-github-personal-access-token
```

The plugin automatically loads environment variables from this file.

## Plugin installation

Add the ipybox repository as plugin marketplace to Claude Code:

```
claude plugin marketplace add https://github.com/gradion-ai/ipybox
```

Then install one of the available plugins:

| Plugin            | Description                                                                                         |
| ----------------- | --------------------------------------------------------------------------------------------------- |
| `codeact-default` | Runs ipybox without a sandbox                                                                       |
| `codeact-sandbox` | Runs ipybox with a [sandboxed](https://gradion-ai.github.io/ipybox/sandbox/index.md) IPython kernel |
| `codeact-docker`  | Runs ipybox as a Docker container                                                                   |

```
claude plugin install codeact-default@ipybox
```

Warning

Only **one** plugin from this marketplace should be active at a time. Having multiple plugins active simultaneously may cause conflicts.

### Sandbox configuration

When using `codeact-sandbox`, you can optionally provide a `sandbox-config.json` file in the workspace directory to customize the sandbox configuration. If not provided, ipybox runs with the [default sandbox](https://gradion-ai.github.io/ipybox/sandbox/#default-sandbox).

## Usage example

This example demonstrates a complete workflow:

- [Registering an MCP server](#register-the-github-mcp-server)
- [Using its tools programmatically](#use-the-github-mcp-server-programmatically)
- [Generating an output parser](#generate-an-output-parser)
- [Chaining tools in a single code action](#chaining-tools-in-a-single-code-action)
- [Saving the code action for reuse](#saving-code-actions-as-tools)

It uses two tools from the GitHub MCP server:

- `search_repositories`
- `list_commits`

### Register the GitHub MCP server

User prompt

```
Register this MCP server at ipybox under name github:
{
  "url": "https://api.githubcopilot.com/mcp/",
  "headers": {
    "Authorization": "Bearer ${GITHUB_API_KEY}"
  }
}
```

The `${GITHUB_API_KEY}` placeholder is automatically replaced with the value from your `.env` file.

This registers the GitHub MCP server and generates a typed Python API for its tools under `mcptools/github/`. Each tool becomes a module named after the tool (`search_repositories.py`, `list_commits.py`, etc.).

### Use the GitHub MCP server programmatically

The codeact skill can be activated in Claude Code with phrases like "use the codeact skill" or similar:

User prompt

```
Use the codeact skill to get the latest 5 commits of the 3 github repos 
of torvalds with the most stars. For each repo, output name, stars and 
the first line of commit messages, and the link to the commit
```

Claude Code first lists directories under `mcptools/` to see which tools are available. It then reads the tool files [search_repositories.py](https://github.com/gradion-ai/ipybox/blob/main/docs/generated/mcptools/github/search_repositories_orig.py) and [list_commits.py](https://github.com/gradion-ai/ipybox/blob/main/docs/generated/mcptools/github/list_commits.py) to understand their interfaces, as these appear relevant to the task.

Claude Code generates two code actions. The first searches for the top 3 repos of Linus Torvalds sorted by stars:

Code action

```
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

Here, Claude Code makes assumptions about the tool response structure. The GitHub MCP server tools do not provide output schemas, so Claude Code guesses the structure from its training data. These assumptions may or may not be correct depending on the MCP server's popularity, but in this example they work. MCP tools that provide output schemas get a generated `Result` class with typed fields, but the GitHub MCP server tools return unstructured strings.

The second code action uses the repository information stored in `top_repos` to get the latest 5 commits of each repo:

Code action

```
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

User prompt

```
Generate an output parser for search_repositories
```

This adds a `run_parsed()` function to [search_repositories.py](https://github.com/gradion-ai/ipybox/blob/main/docs/generated/mcptools/github/search_repositories.py), returning a structured `ParseResult`. Claude Code infers this type by interacting with the tool using example inputs. The codeact skill encourages Claude Code to prioritize `run_parsed()` over `run()` when selecting tools.

The parsing implementation details are stored in [mcpparse/github/search_repositories.py](https://github.com/gradion-ai/ipybox/blob/main/docs/generated/mcpparse/github/search_repositories.py). Keeping implementation separate from interface prevents polluting the interfaces that Claude Code inspects.

### Chaining tools in a single code action

Running the same task again (optionally after restarting Claude Code), Claude Code now chains the tools in a single code action because it knows the structure of the `search_repositories` result up-front. It uses the new `run_parsed()` function and navigates the structured output based on the `ParseResult` type:

User prompt

```
Use the codeact skill to get the latest 5 commits of the 3 github repos 
of torvalds with the most stars. For each repo, output name, stars and 
the first line of commit messages, and the link to the commit
```

Code action

```
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

Code actions can be saved and reused as tools in later code actions. To save the previous code action, use a prompt like:

User prompt

```
Save this as code action under github category with name commits_of_top_repos. 
Make username, top_n_repos and last_n_commits parameters
```

This creates a new package `gentools/github/commits_of_top_repos/` with an [api.py](https://github.com/gradion-ai/ipybox/blob/main/docs/generated/gentools/github/commits_of_top_repos/api.py) module that defines the typed interface and an [impl.py](https://github.com/gradion-ai/ipybox/blob/main/docs/generated/gentools/github/commits_of_top_repos/impl.py) module that contains the implementation.

The interface in `api.py` exposes the tool's parameters and return types and is relevant for understanding tool usage. The implementation in `impl.py` is not inspected by Claude Code during tool selection, saving token usage.

### Using saved code actions as tools

After restarting Claude Code or clearing its context window, to enforce re-discovery of tools, the same task now uses the saved code action:

User prompt

```
Use the codeact skill to get the latest 5 commits of the 3 github repos 
of torvalds with the most stars. For each repo, output name, stars and 
the first line of commit messages, and the link to the commit
```

Code action

```
from gentools.github.commits_of_top_repos import run

results = run(username="torvalds", top_n_repos=3, last_n_commits=5)

for repo in results:
    print(f"\n## {repo.name} ({repo.stars:,} ⭐)")
    print("-" * 60)
    for commit in repo.commits:
        print(f"• {commit.message}")
        print(f"  {commit.url}")
```

To conclude, the usage pattern in this example supports building a library of code actions. Each saved code action becomes a tool available for use in future code actions, enabling composition and reuse.

______________________________________________________________________

1. Executable Code Actions Elicit Better LLM Agents: <https://arxiv.org/abs/2402.01030> [↩](#fnref:1 "Jump back to footnote 1 in the text")
