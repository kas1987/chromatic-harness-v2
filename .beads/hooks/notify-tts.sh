#!/usr/bin/env bash
# Notification hook: speak the message via Windows System.Speech.
# Reads JSON {"message": "..."} on stdin. Silent on empty/missing message.
msg=$(jq -r '.message // empty' 2>/dev/null)
[ -z "$msg" ] && exit 0
MSG="$msg" powershell.exe -NoProfile -Command "Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak(\$env:MSG)" >/dev/null 2>&1 &
exit 0
