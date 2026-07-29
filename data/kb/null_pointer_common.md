# Common Null / None Type Error

## Symptom
Runtime crash with `AttributeError: 'NoneType' object has no attribute 'get'` or `TypeError: Cannot read properties of undefined (reading 'status')`.

## Root Cause
An API call or database query returned `None` or `null` due to missing records, and the calling function dereferenced properties directly without verifying object existence.

## Recommended Fix
Add defensive checking or optional chaining before accessing properties on objects returned from external sources (e.g. `val.get('prop') if val is not None else default`). Validate schema payloads using Pydantic models with default fields.
