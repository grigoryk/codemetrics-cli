# codemetrics-cli

A cli tool for exploring code metrics of a software project. Only dotnet & Windows for now.

## Features

- Analyze code metrics for .NET projects and solutions
- Compare metrics across commits or date ranges
- Plot metrics over time
- **Export results to CSV** for importing into Excel or other tools

## CSV Export

To export metrics data to CSV format, use the `-csv` flag:

```bash
codemetrics_cli -p MyProject.csproj -csv
```

This will generate a CSV file with an auto-generated name based on your command options, like:
- `project_MyProject_metrics_20240101_120000.csv`
- `project_MyProject_diff_dates_2024-01-01_to_2024-12-31_20240101_120000.csv`

You can also specify a custom filename:

```bash
codemetrics_cli -p MyProject.csproj -csv -csv_filename my_metrics.csv
```

The CSV export works with all commands:
- Single project/solution analysis
- Commit-based analysis (`-c`)
- Date range comparisons (`-dd`)
- Commit range comparisons (`-dc`)
- Step-based analysis over time (`-st`)

## development workflow
- make changes
- test `cd src && py -m codemetrics_cli -p ...`
- bump version in pyproject.toml
- build distribution `py -m build`
- upload new version to PyPI `py -m twine upload .\dist\codemetrics_cli-{new_version}*`
- test new version `pip install codemetrics_cli --upgrade && codemetrics_cli -p ...`