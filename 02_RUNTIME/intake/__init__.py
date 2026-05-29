"""Intake queue — unified goal/bead bus for close-loop consolidation."""

from intake.queue import (
    IntakeEntry,
    append_entry,
    default_queue_path,
    list_entries,
    list_queued,
    record_status,
    validate_entry,
)
from intake.auto_intake import drain_queue, process_entry
from intake.inbox_adapter import poll_inbox_to_intake, resolve_inbox_db

__all__ = [
    "IntakeEntry",
    "append_entry",
    "default_queue_path",
    "drain_queue",
    "list_entries",
    "list_queued",
    "poll_inbox_to_intake",
    "process_entry",
    "record_status",
    "resolve_inbox_db",
    "validate_entry",
]
