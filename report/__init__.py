# Makes report/ importable as a package -- only needed so
# report/preprocess/build_cache.py can be invoked as
# `python -m report.preprocess.build_cache` and import the sibling
# _validation_scripts.py as `report._validation_scripts`. Quarto itself
# ignores this file; the report/*.qmd files' own `sys.path.insert(0, ".")`
# + `import _validation_scripts` (bare) is unaffected by its presence.
