# Renaming `-Chromatic_Wiki` → `chromatic-wiki` (optional)

The leading hyphen in `-Chromatic_Wiki` is awkward for paths and tooling. Rename when you are ready.

## GitHub rename

```bash
gh repo rename chromatic-wiki --repo kas1987/-Chromatic_Wiki
```

Or: **Settings → General → Repository name** → `chromatic-wiki`

## Local clone

```powershell
cd C:\Users\kas41
git clone https://github.com/kas1987/chromatic-wiki.git chromatic-wiki
# retire: -Chromatic_Wiki folder after verifying remote
```

## Harness env

```powershell
$env:CHROMATIC_WIKI_ROOT = "C:\Users\kas41\chromatic-wiki"
```

Update defaults in:

- `scripts/promote_to_wiki.py`
- `scripts/sync_wiki_mirror.py`

Or rely on `CHROMATIC_WIKI_ROOT` only (recommended).

## Wiki manifest

In Wiki `manifest.yaml`, add after rename:

```yaml
github_repo: kas1987/chromatic-wiki
legacy_name: kas1987/-Chromatic_Wiki
```

## Docs to grep-update

- [WIKI_REPO_AND_PROMOTION.md](WIKI_REPO_AND_PROMOTION.md)
- [REPO_AND_RIG_INVENTORY.md](REPO_AND_RIG_INVENTORY.md)
- [docs/beads/WIKI_V01_BEADS.md](beads/WIKI_V01_BEADS.md)

Bead **WIKI-007** tracks human approval for rename.
