import json
import re
import sys

# Keys whose names suggest a raw secret — but skip _PATH indirections
SECRET_KEY_RE = re.compile(
    r"(TOKEN|SECRET|PASSWORD|CREDENTIALS)(?!.*_PATH)", re.IGNORECASE
)
# Also catch bare _KEY keys (not _KEY_PATH)
SECRET_KEY_RE2 = re.compile(r"_KEY(?!_PATH)", re.IGNORECASE)

# Values that look like raw tokens/secrets (not file paths)
RAW_VALUE_RE = re.compile(r"^(ghp_|ghs_|sk-|xox[baprs]-|eyJ)", re.IGNORECASE)


def is_raw_secret(key: str, value: str) -> bool:
    if not isinstance(value, str):
        return False
    # Path indirections are safe regardless of key name
    if value.startswith(("C:\\", "/", "~")):
        return False
    # Key name signals a secret and value isn't a path
    if SECRET_KEY_RE.search(key) or SECRET_KEY_RE2.search(key):
        return True
    # Value looks like a known raw token format
    if RAW_VALUE_RE.match(value):
        return True
    return False


data = sys.stdin.read()
obj = json.loads(data)

env = obj.get("env", {})
scrubbed = {k: v for k, v in env.items() if not is_raw_secret(k, v)}
removed = set(env) - set(scrubbed)
if removed:
    import sys as _sys

    print(f"[scrub] removed keys: {sorted(removed)}", file=_sys.stderr)
    obj["env"] = scrubbed
    if not obj["env"]:
        del obj["env"]

print(json.dumps(obj, indent=2))
