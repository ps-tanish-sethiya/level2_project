# Test Ordering Dependency Pollution

## Symptom
Test suite succeeds when executed sequentially in order, but fails when run in random order using `pytest -n auto` or `pytest-randomly` with errors like `KeyError` or `AlreadyExistsError`.

## Root Cause
A test function mutates global state, singleton objects, or shared database tables without resetting state in teardown fixtures, causing state leakage into subsequent tests.

## Recommended Fix
Refactor tests to use explicit cleanup fixtures with `autouse=True` or `yield` statements that clean modified global state or database records upon completion. Avoid reliance on state created by preceding test cases.
