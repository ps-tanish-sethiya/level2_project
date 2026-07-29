# Flaky Test Timeout in CI Pipeline

## Symptom
Test suite execution fails intermittently during integration test runs with `pytest.PytestUnhandledThreadExceptionWarning` or `TimeoutError: Connection timed out after 30000ms`. The test passes when re-run individually locally or when the CI pipeline is re-triggered without any code modifications.

## Root Cause
Asynchronous network requests or background database connection pools fail to resolve within default hardcoded test runner timeouts when running under high resource contention in shared CI runner environments.

## Recommended Fix
Increase the explicit wait timeout for async assertions from 5 seconds to 15 seconds using dynamic polling utilities (e.g. `wait_for_condition`). Alternatively, mark known network-dependent test cases with `@pytest.mark.flaky(reruns=2)` or isolate external service mocks using local fixtures.
