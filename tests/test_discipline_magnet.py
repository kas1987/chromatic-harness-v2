"""Tests for Karpathy discipline_magnet."""

from magnets.discipline_magnet import DisciplineMagnet


class TestDisciplineMagnet:
    def test_clean_discipline_post_impl(self) -> None:
        m = DisciplineMagnet()
        ev = m.observe(
            "CHR-1",
            "post_implementation",
            {
                "read_paths": ["src/a.py"],
                "modified_paths": ["src/a.py"],
                "expected_paths": ["src/a.py"],
                "has_success_criteria": True,
                "assumptions_stated": True,
                "verification_ran": True,
            },
        )
        assert ev.risk_delta == 0.0
        assert ev.confidence_delta > 0
        assert ev.recommended_action == "proceed"

    def test_write_without_read(self) -> None:
        m = DisciplineMagnet()
        ev = m.observe(
            "CHR-1",
            "discipline_check",
            {
                "read_paths": [],
                "modified_paths": ["src/a.py"],
                "has_success_criteria": True,
                "assumptions_stated": True,
            },
        )
        assert ev.risk_delta >= 0.2
        assert any("WRITE without READ" in e for e in ev.evidence)

    def test_missing_assumptions_and_criteria(self) -> None:
        m = DisciplineMagnet()
        ev = m.observe(
            "CHR-1",
            "pre_implementation",
            {"read_paths": [], "modified_paths": [], "has_success_criteria": False},
        )
        assert ev.risk_delta >= 0.18
        assert ev.recommended_action in ("narrow_scope", "halt_and_review")
