# Missing Required Environment Variable

## Symptom
Application startup crashes immediately with `KeyError: 'DATABASE_URL'` or `ConfigurationError: Missing required environment variable GITHUB_TOKEN`. The error occurs right after container launch or when executing automated integration tests.

## Root Cause
The codebase attempts to dereference an environment variable directly via `os.environ['KEY']` without fallback defaults or configuration validation, and the variable is missing from the environment or `.env` secrets store.

## Recommended Fix
Add mandatory environment variable validation at application initialization using `pydantic-settings` or `os.getenv('KEY', default)`. Ensure all required keys are documented in `.env.example` and configured in CI repository secrets.
