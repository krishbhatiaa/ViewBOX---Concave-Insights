from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_stray_root_diagrams_are_gone():
    assert not (ROOT / "db_diagram.png").exists()
    assert not (ROOT / "user_flow.png").exists()
    assert (ROOT / "design" / "db_diagram.png").exists()
    assert (ROOT / "design" / "user_flow.png").exists()


def test_gitignore_covers_pytest_cache():
    assert ".pytest_cache/" in (ROOT / ".gitignore").read_text(encoding="utf-8")
