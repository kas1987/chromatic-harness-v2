---
type: learning
source: retro-quick
date: 2026-03-31
---

# Learning: Never hardcode auth tokens in client-side JS — use localStorage + URL param bootstrap

**Category**: security
**Confidence**: high

## What We Learned

Even for internal dev tools, hardcoding auth tokens directly as a constant in HTML/JS is bad practice. The token is visible in source view, git history, and any HTTP response. It also leaks to CDN/proxy caches.

**Safe pattern for local dev tools:**
```javascript
// 1. Check URL param (one-time bootstrap: ?token=xxx) // pragma: allowlist secret
const urlParam = new URLSearchParams(window.location.search).get('token'); // pragma: allowlist secret
if (urlParam) {
  localStorage.setItem('gen_api_token', urlParam); // pragma: allowlist secret
  // Optionally strip from URL: history.replaceState({}, '', window.location.pathname)
}

// 2. Read from localStorage at runtime (never hardcode the value here)
const AUTH = localStorage.getItem('gen_api_token') || ''; // pragma: allowlist secret

// 3. Use as function (not const) so AUTH updates are reflected immediately
const HEADERS = () => ({
  'Content-Type': 'application/json',
  'Authorization': 'Bearer ' + AUTH
});
```

This keeps the token out of source code, allows easy rotation (clear localStorage), and supports one-click setup via URL param.

## Source

gen dispatch.html vibe review — CRITICAL-1 finding
