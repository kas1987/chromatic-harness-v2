from intake.bd_runner import resolve_bd_argv


def test_resolve_bd_argv_returns_list():
    argv = resolve_bd_argv()
    assert isinstance(argv, list)
    assert len(argv) >= 1
    assert argv[0]
