# codemetrics-cli

A cli tool for exploring code metrics of a software project. Only dotnet & Windows for now.

## development workflow
- make changes
- test `cd src && py -m codemetrics_cli -p ...`
- bump version in pyproject.toml
- build distribution `py -m build`
- upload new version to PyPI `py -m twine upload .\dist\codemetrics_cli-{new_version}*`
- test new version `pip install codemetrics_cli --upgrade && codemetrics_cli -p ...`