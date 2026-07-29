# Database Connection Timeout

## Symptom
Service logs output `OperationalError: (pymysql.err.OperationalError) (2003, "Can't connect to MySQL server")` or `sqlite3.OperationalError: database is locked`.

## Root Cause
Database connection pool exhaustion occurs when opened database connections are not properly closed or returned to the pool after HTTP request completion under heavy query load.

## Recommended Fix
Ensure all database interactions use context managers (`with connection:`) or explicit try/finally blocks to guarantee connection closure. Increase maximum pool size and configure pool pre-ping connection health validation.
