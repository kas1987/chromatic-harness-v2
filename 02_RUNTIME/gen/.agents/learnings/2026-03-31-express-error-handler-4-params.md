---
type: learning
source: retro-quick
date: 2026-03-31
---

# Learning: Express error middleware requires exactly 4 params

**Category**: debugging
**Confidence**: high

## What We Learned

Express distinguishes error-handling middleware from regular middleware **solely by function arity** (number of declared params). If you write a handler with 3 params `(err, req, res)` instead of 4 `(err, req, res, next)`, Express treats it as normal middleware — `err` receives `req`, `req` receives `res`, `res` receives `next`. Calling `res.status(500)` fails with `TypeError: res.status is not a function`.

**Wrong:**
```typescript
app.use((err: any, req: Request, res: Response) => {
  res.status(500).json({ error: "..." }); // TypeError at runtime
});
```

**Correct:**
```typescript
app.use((err: any, req: Request, res: Response, _next: NextFunction) => {
  res.status(500).json({ error: "..." });
});
```

The `_next` param is never called but must be declared for Express's arity check.

## Source

gen server — all delegate routes throwing 500 "res.status is not a function"
