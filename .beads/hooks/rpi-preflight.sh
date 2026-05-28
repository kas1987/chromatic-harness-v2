#!/usr/bin/env bash
# rpi-preflight.sh — validate cwd is a real codebase before launching /rpi orchestrators
# Usage: rpi-preflight.sh [--help]
# Exit 0 = codebase found; exit 1 = no codebase markers
set -u

usage() {
  printf 'Usage: rpi-preflight.sh [--help]\n'
  printf '\n'
  printf 'Validates that the current working directory contains a known codebase marker.\n'
  printf 'Exit 0 = codebase found. Exit 1 = no markers found.\n'
  printf 'Output: JSON on stdout.\n'
}

case "${1:-}" in
  --help|-h)
    usage
    exit 0
    ;;
esac

cwd=$(pwd)
markers=(go.mod package.json pyproject.toml Cargo.toml .git pom.xml build.gradle Makefile CMakeLists.txt)

for marker in "${markers[@]}"; do
  if [ -e "${cwd}/${marker}" ]; then
    jq -cn --arg m "${marker}" --arg c "${cwd}" \
      '{status: "ok", marker: $m, cwd: $c}'
    exit 0
  fi
done

jq -cn --arg c "${cwd}" \
  '{status: "fail", reason: "cwd does not appear to be a codebase — no known project markers found", cwd: $c}'
exit 1
