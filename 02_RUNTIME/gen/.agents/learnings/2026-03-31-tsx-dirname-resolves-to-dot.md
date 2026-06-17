---
type: learning
source: retro-quick
date: 2026-03-31
---

# Learning: __dirname resolves to "." under tsx

**Category**: debugging
**Confidence**: high

## What We Learned

When running TypeScript files with `tsx` (the ts-node replacement), `__dirname` resolves to `.` (the process cwd) rather than the source file's directory. This silently breaks any `path.join(__dirname, "relative-file")` pattern.

**Symptom:** Module loads (no import error), but `fs.readFileSync(path.join(__dirname, "roles.json"))` throws ENOENT because it looks in `./roles.json` instead of `./src/routes/roles.json`. The router exports successfully but its initialization is skipped, so all routes return 404.

**Fix:** Use a candidate path search:
```typescript
const candidates = [
  path.join(__dirname, "roles.json"),               // dist/ (compiled)
  path.resolve(process.cwd(), "src/routes/roles.json"), // tsx dev
  path.resolve(process.cwd(), "dist/routes/roles.json"),
];
for (const p of candidates) {
  if (fs.existsSync(p)) return p;
}
throw new Error(`Not found. Tried: ${candidates.join(", ")}`);
```

**Alternative:** Use `import.meta.url` with `fileURLToPath` if the project can switch to ESM module output.

## Source

gen delegate router debug — routes all returned 404 despite module loading cleanly
