# External API Rate Limit Exceeded (HTTP 429)

## Symptom
Outbound HTTP requests fail with `HTTP status 429 Too Many Requests` or `API rate limit exceeded for client IP`. The service fails to retrieve external status or data.

## Root Cause
The application executes unthrottled concurrent requests to an external web API without exponential backoff or caching headers, breaching the API provider's rate limit quota.

## Recommended Fix
Implement exponential backoff with retry jitter (e.g. using `tenacity` or `httpx` retry middleware) and cache GET responses locally using in-memory or Redis caches to reduce redundant API calls.
