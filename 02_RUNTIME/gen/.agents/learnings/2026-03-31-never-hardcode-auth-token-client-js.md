---
type: learning
source: retro-quick
date: 2026-03-31
---

# Learning: Never hardcode auth tokens in client-side JS — use localStorage + URL param bootstrap

**Category**: security
**Confidence**: high

## What We Learned

Even for internal dev tools, hardcoding auth tokens like `const TOKEN = 'test-token-dev-only'` in HTML/JS is bad practice. The token is visible in source view, git history, and any HTTP response. It also leaks to CDN/proxy caches.

**Safe pattern for local dev tools:**
```javascript
// 1. Check URL param (one-time bootstrap: ?token=xxx)
const urlToken = new URLSearchParams(window.location.search).get('token');
if (urlToken) {
  localStorage.setItem('gen_api_token', urlToken);
  // Optionally strip from URL: history.replaceState({}, '', window.location.pathname)
}

// 2. Read from localStorage at runtime
const TOKEN = localStorage.getItem('gen_api_token') || '';

// 3. Use as function (not const) so TOKEN updates are reflected immediately
const HEADERS = () => ({
  'Content-Type': 'application/json',
  'Authorization': 'Bearer ' + TOKEN
});
```

This keeps the token out of source code, allows easy rotation (clear localStorage), and supports one-click setup via URL param.

## Source

gen dispatch.html vibe review — CRITICAL-1 finding
