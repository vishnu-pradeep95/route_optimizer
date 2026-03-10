---
created: 2026-03-10T10:59:17.412Z
title: Add SRI integrity attributes to CDN resources
area: ui
files:
  - apps/kerala_delivery/driver_app/index.html:20
  - apps/kerala_delivery/driver_app/index.html:885
---

## Problem

Semgrep scan (v1.154.0, `--config auto`) flagged two external CDN resources in the Driver PWA `index.html` that are missing `integrity` subresource integrity (SRI) attributes (CWE-353, OWASP A08:2021).

- Line 20: `<link>` tag loading external CSS from CDN
- Line 885: `<script>` tag loading external JS from CDN

Without SRI, if the CDN is compromised, modified resources could introduce XSS or other attacks into the Driver PWA.

## Solution

1. Download each CDN resource and generate SHA-384 hashes (`openssl dgst -sha384 -binary | openssl base64 -A`)
2. Add `integrity="sha384-..."` and `crossorigin="anonymous"` attributes to both tags
3. Re-run semgrep to confirm findings are resolved
