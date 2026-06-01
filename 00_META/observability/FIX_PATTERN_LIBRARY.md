# Fix Pattern Library

Known error signatures and reusable fixes.

## Pattern Template

```md
## Pattern: [Name]

### Error Signature

### Symptoms

### Likely Cause

### Fix

### Verification

### Prevention

### Related Events
```

---

## Pattern: Missing Dependency After Scaffold

### Error Signature

`Cannot find module` / `Module not found`

### Symptoms

Build, test, or dev server fails after new scaffold is created.

### Likely Cause

Files were created but package install did not complete or dependency was not added.

### Fix

Run the package manager install command for the project and retry validation.

### Verification

Build/test command succeeds.

### Prevention

After scaffold creation, run dependency verification before implementation work continues.
