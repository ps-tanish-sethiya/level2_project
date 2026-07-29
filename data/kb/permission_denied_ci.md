# CI Runner Permission Denied

## Symptom
CI workflow fails during script execution step with `PermissionDeniedError: [Errno 13] Permission denied: './scripts/deploy.sh'` or `ResourceNotAccessibleException: Resource not accessible by integration`.

## Root Cause
The executable shell script lacks POSIX execution permissions (`+x`), or the GitHub Actions GITHUB_TOKEN permissions in the workflow file lack `write` access for the requested workflow action scope.

## Recommended Fix
Run `git update-index --chmod=+x scripts/deploy.sh` locally and commit the file mode change. For GitHub Actions API permissions, grant explicit `permissions: contents: read` or required permissions blocks in `.github/workflows/ci.yml`.
