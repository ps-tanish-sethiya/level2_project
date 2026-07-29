# Import Error / Typo in Module Path

## Symptom
Application execution or pytest collection fails with `ModuleNotFoundError: No module named 'agent.util'` or `ImportError: cannot import name 'process_data' from 'services.pipeline'`.

## Root Cause
A recent refactoring renamed a module file or package folder without updating all corresponding import statements, or an import statement contains a typographical error.

## Recommended Fix
Inspect the traceback to locate the invalid import statement. Update the module path or symbol name to match the current project structure, or add missing `__init__.py` markers if referencing a newly added python package directory.
