# Claude Code plugin

This plugin installs ipybox as MCP server in Claude Code together with a code action skill. 
It enables Claude Code to call MCP tools programmatically in code actions executed in ipybox.
Code actions themselves can be saved and reused as tools in other code actions generated later.
Over time, a library of code actions can be built, composed of other code actions and MCP tools.

Code actions and MCP tools are discovered via agentic search
Their sources are inspected on demand to understand their interfaces so that they can be properly used.
This progressive disclosure approach frees Claude Code from pre-loading interfaces into its system prompt.
Only sources that are actually needed are loaded into the agent's context window.

Code actions are stored such that their interface is separated from implementation details.
This enables Claude Code to inspect only the relevant parts of a code action without being distracted by implementation details.
Separating interface from implementation also reduces token consumption when inspecting code actions.

Here's an overview how responsibilities are distributed between ipybox and Claude Code:

ipybox provides:
- generation of Python tool APIs from MCP server tool schemas
- sandboxed execution of Python code that uses the generated APIs
- fully local code execution without any cloud dependencies

Claude Code uses the code action skill to:
- augment generated Python tool APIs so that they can be better chained in code actions
- discover and inspect tools and code actions via agentic search on the filesystem
- select tools and code actions appropriate for the task, based on their Python interfaces
- generate and execute code in ipybox that composes MCP tools and saved code actions
- save successful code actions with a structure for efficient discovery and reuse

## Installation

...

## Environment setup

- empty project
- install ipybox (optional)
- .env file with API keys

## Usage example

TODO: give a brief overview of the steps covered in this example.

### Register the GitHub MCP server

> Register this MCP server under name github: {"url": "https://api.githubcopilot.com/mcp/", "headers": {"Authorization": "Bearer ${GITHUB_API_KEY}"}}

This registers the GitHub MCP servers and generates Python API for its tools under `mcptools/github/`, one module per tool, named after the tool (`search_repositories`, `list_commits`, ...). These tools are then searched and inspected by Claude Code to understand how to use them in code actions.

### Use the GitHub MCP server programmatically

Guidance for using registered MCP servers programmatically is given by the *codeact* skill bundled with this plugin. It is activated with phrases like "use the codeact skill" or similar:

> use codeact to get the latest 5 commits of the 3 github repos of torvalds with the most stars. for each repo, output name, stars and the first line of commit messages, and the link to the commit

Claude code first lists directories and subdirectories under `mcptools/` to understand which tools are available. It then decides to read the tool files [search_repositories.py](generated/mcptools/github/search_repositories_orig.py), [list_commits.py](generated/mcptools/github/list_commits.py) to understand their interfaces, as these tools seem to be relevant to the task.

Claude code generates two code actions using these tools,and executes them in ipybox. The first code action searches for the top 3 repos of Linus Torvalds with the most stars and stores the result in the `top_repos` variable:

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

Note how Claude Code makes assumptions about the response structure. It didn't get that information from the GitHub MCP server as its tools do not provide an output schema. Claude Code must have learned about this structure from its training data. These assumptions may or may not be correct, depending on the popularity of the MCP server, but in this example it works. For MCP servers whose tools provide an output schema, the generated tool API defines a `Result` class but this is not the case for the GitHub MCP server. Further below, we will see how to augment the `search_repositories` tool with an output parser that returns a structured type that can be inspected by Claude Code prior to generating a code action.

The second code action, uses the repository information stored in the `top_repos` variable to get the latest 5 commits of each repo and print the commit messages and links:

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

This finally prints what we asked for, but intermediate results were added to the agent's context windows which is not ideal and could be avoided in this particular example. In order to ecourage Claude Code to generate a code actions that chains `search_repositories` and `list_commits` in a single code action, we are going to generate an output parser for the `search_repositories` tool.

### Generate an output parser

To compensate for the lack of output schemas for tools of the GitHub MCP server, we are going to generate an output parser for the `search_repositories` tool using the *codeact* skill.

> generate an output parser for search_repositories

This adds a `run_parsed()` function to the [search_repositories](generated/mcptools/github/search_repositories.py) tool, returning a structured `ParseResult`. This type is inferred by Claude Code from interacting with the tool using example inputs. Whenever Claude Code reads this file in the future it is encouraged by the *codeact* skill to prioritize `run_parsed()` over `run()` when generating code actions.

### Chaining tools in a single code action

When running the same task again (optionally after restarting Claude Code), Claude Code is now able to confidently chain the tools `search_repositories` and `list_commits` in a single code action. It now uses the new `run_parsed()` function and navigates the structured output based on the `ParseResult` type:

> use codeact to get the latest 5 commits of the 3 github repos of torvalds with the most stars. for each repo, output name, stars and the first line of commit messages, and the link to the commit

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

The implementation details of parsing are stored separately in [mcpparse/github/search_repositories.py](generated/mcpparse/github/search_repositories.py). It is important not to pollute the interfaces read by Claude Code with implementation details, in order to keep the agent focused and the context window small.

### Saving code actions as tools

One big advantage of prgrammatic tool calling is that code actions generated by an agent can be saved and reused as custom tools in later code actions. To save the previous code action as custom tool, we prompt Claude Code with:

> save this as code action under github category with name commits_of_top_repos. Make username, top_n_repos and last_n_commits parameters

This creates a new package under `gentools/github/commits_of_top_repos/` with with an [api.py](generated/gentools/github/commits_of_top_repos/api.py) and an [impl.py](generated/gentools/github/commits_of_top_repos/impl.py) file. The `api.py` file defines the typed interfaces of the custom too, `impl.py` contains all the implementation details that are not relevant for usage.

### Using saved code actions as tools

After restarting Claude Code (to force a re-discovery of tools), and prompting Claude Code again with the same task, it now discovers and uses the new custom tool:

> use codeact to get the latest 5 commits of the 3 github repos of torvalds with the most stars. for each repo, output name, stars and the first line of commit messages, and the link to the commit

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

Following this schema repeatedly supports building a library of code actions that an agent can reuse for more efficient work. 
