import pytest

from app.config import env_bool, read_int_env

# --- env_bool ---


@pytest.mark.parametrize(
    "value,expected",
    [
        ("true", True),
        ("True", True),
        ("1", True),
        ("yes", True),
        ("on", True),
        ("false", False),
        ("0", False),
        ("no", False),
        ("", False),
        ("nonsense", False),
    ],
)
def test_env_bool_parses_truthy_values(
    monkeypatch: pytest.MonkeyPatch, value: str, expected: bool
) -> None:
    monkeypatch.setenv("FLAG_X", value)
    assert env_bool("FLAG_X", default=False) is expected


def test_env_bool_unset_returns_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLAG_X", raising=False)
    assert env_bool("FLAG_X", default=False) is False
    assert env_bool("FLAG_X", default=True) is True


# --- read_int_env ---


def test_read_int_env_required_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NEEDED", raising=False)
    with pytest.raises(ValueError, match="NEEDED"):
        read_int_env("NEEDED", required=True)


def test_read_int_env_optional_missing_returns_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MAYBE", raising=False)
    assert read_int_env("MAYBE", required=False, default=42) == 42


def test_read_int_env_invalid_int_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BAD", "abc")
    with pytest.raises(ValueError, match="BAD"):
        read_int_env("BAD", required=True)
