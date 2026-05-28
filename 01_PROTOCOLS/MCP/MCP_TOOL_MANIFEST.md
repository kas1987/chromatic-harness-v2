# MCP Tool Manifest

## Purpose

This file defines the MCP tool families Chromatic Harness expects to connect through provider-agnostic adapters.

## Initial Tool Families

| Tool Family | Purpose | Risk |
|---|---|---|
| filesystem.read | Inspect files | Low |
| filesystem.patch | Patch scoped files | Medium |
| github.read | Issues, PRs, repo content | Low |
| github.write | Issues, branches, PRs | Medium |
| shell.execute | Run tests/scripts | High |
| database.read | Inspect state | Low |
| database.write | Update state | Medium |
| browser.search | Current research | Low |
| secrets.read | Secret access | Critical |
| deploy.production | Production deploy | Critical |

## Rule

MCP exposes capability. CMP grants permission.
