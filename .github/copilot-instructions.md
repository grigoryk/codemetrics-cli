# Copilot Instructions for codemetrics-cli

## Project Overview
codemetrics-cli is a Python CLI tool for analyzing code metrics of .NET software projects. It wraps the Roslyn Metrics.exe tool and provides an intuitive command-line interface for tracking code quality metrics over time.

## Key Technologies
- **Language**: Python 3.8+
- **Platform**: Windows only (uses .NET tools and Windows-specific paths)
- **Build System**: hatchling
- **Dependencies**: colorist, numpy, uniplot, tabulate
- **External Tool**: Roslyn Metrics.exe (built from dotnet/roslyn repository)

## Architecture Overview
- **Main module**: `src/codemetrics_cli/metrics.py` - Contains all CLI logic and metric processing
- **Entry point**: `src/codemetrics_cli/__main__.py` - Simple wrapper that calls cli()
- The tool operates by:
  1. Installing/using Roslyn Metrics.exe in `~/.metrics_scratch`
  2. Creating shadow repos for git operations
  3. Running metrics analysis on .NET projects/solutions
  4. Displaying results as tables or plots

## Development Workflow
1. Make code changes to `src/codemetrics_cli/metrics.py`
2. Test locally: `cd src && py -m codemetrics_cli -p <project_path>`
3. Bump version in `pyproject.toml`
4. Build distribution: `py -m build`
5. Upload to PyPI: `py -m twine upload .\dist\codemetrics_cli-{new_version}*`
6. Test installed version: `pip install codemetrics-cli --upgrade && codemetrics-cli -p <project_path>`

## Code Style Guidelines
- Follow existing Python conventions in the codebase
- Use global variables sparingly (already present for paths)
- Functions should be focused and single-purpose
- Minimal comments unless explaining complex logic
- Use Windows-style path separators where appropriate (this is Windows-only)

## Important Constraints
- **Windows-only**: This tool only works on Windows due to .NET framework dependencies
- **Git operations**: The tool creates shadow repositories and performs git operations, be careful with path handling
- **External dependencies**: Depends on external Metrics.exe tool from Roslyn project
- **No tests**: There is currently no test infrastructure in this project

## Common Operations
- **Running metrics on a project**: `codemetrics-cli -p path/to/project.csproj`
- **Running metrics on a solution**: `codemetrics-cli -s path/to/solution.sln`
- **Diff between commits**: `codemetrics-cli -p project.csproj -dc hash1..hash2`
- **Diff over time**: `codemetrics-cli -p project.csproj -dd 2024-01-01..2024-12-31 -st 30`
- **Plotting metrics**: `codemetrics-cli -p project.csproj -dd 2024-01-01..2024-12-31 -pl all`

## Key Functions to Understand
- `cli()`: Main entry point, parses arguments and orchestrates execution
- `figure_out_paths_get_target()`: Resolves project/solution paths and git repo structure
- `internal_setup()`: Installs Metrics.exe and sets up shadow repositories
- `gather_metrics()`: Runs Metrics.exe and caches results
- `process_metrics()`: Parses XML output from Metrics.exe
- `compute_metrics_for_commits_and_plot()`: Handles diff operations and plotting

## Building and Testing
- **Build**: `py -m build` (creates distribution in `dist/` directory)
- **Local testing**: `cd src && py -m codemetrics_cli -p <test_project>`
- **No automated tests**: Manual testing is required

## Distribution
- Package is published to PyPI as `codemetrics-cli`
- Use `twine` for uploading new versions
- Always bump version in `pyproject.toml` before building

## When Making Changes
1. Preserve Windows-specific functionality (paths, .NET tools)
2. Test with actual .NET projects if modifying core functionality
3. Ensure git operations work correctly with shadow repositories
4. Update version in `pyproject.toml` for any user-facing changes
5. Maintain backward compatibility with existing CLI arguments
