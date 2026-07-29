# SSL Certificate Verification Failure

## Symptom
Outbound API requests fail with `SSLError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: certificate has expired` or `httpx.ConnectError`.

## Root Cause
The destination API domain's TLS/SSL certificate expired or the local system CA certificate bundle is outdated and missing updated root certificates.

## Recommended Fix
Verify destination domain certificate validity using `openssl s_client -connect host:443`. Update local CA root certificates package via `pip install --upgrade certifi` or renew the target service certificate.
