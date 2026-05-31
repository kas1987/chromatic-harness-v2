import json, sys

msg = {
    "systemMessage": (
        "[P1-P4 GATE] Before taking any action this session, classify your work:\n"
        "  P1 = must do now (breakage, blocker, critical path)\n"
        "  P2 = should do this session (planned work, open beads)\n"
        "  P3 = nice to have (improvements, cleanup)\n"
        "  P4 = idea only — ADD TO 01_STATE/P4_PARKING_LOT.md, do NOT execute\n"
        "Run: bd ready — then claim a bead before starting."
    )
}
print(json.dumps(msg))
