# n8n Dashboard Placeholder

Use n8n as the workflow surface, not the governance brain.

Suggested workflows:

1. GitHub PR opened -> validate visual registry -> comment result.
2. Manual GO webhook -> read queue -> dispatch agent -> update status.
3. Nightly audit -> regenerate diagrams -> open issue if drift found.
4. Failure webhook -> create incident handoff.

Keep shell/code execution isolated and avoid broad host permissions.
