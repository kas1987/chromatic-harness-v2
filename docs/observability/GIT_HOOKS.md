# Git Hooks

Copy hooks into `.git/hooks/` and make them executable.

```bash
cp git_hooks/pre-commit .git/hooks/pre-commit
cp git_hooks/pre-push .git/hooks/pre-push
chmod +x .git/hooks/pre-commit .git/hooks/pre-push
```
