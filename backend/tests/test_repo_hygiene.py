import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_stray_root_diagrams_are_gone():
    assert not (ROOT / "db_diagram.png").exists()
    assert not (ROOT / "user_flow.png").exists()
    assert (ROOT / "design" / "db_diagram.png").exists()
    assert (ROOT / "design" / "user_flow.png").exists()


def test_gitignore_covers_pytest_cache():
    assert ".pytest_cache/" in (ROOT / ".gitignore").read_text(encoding="utf-8")


def test_dotenv_loader_reads_values_without_overriding_environment(tmp_path, monkeypatch):
    from app import load_env

    monkeypatch.setenv("VB_ENV_TEST", "from-shell")
    monkeypatch.delenv("VB_ENV_NEW", raising=False)
    path = tmp_path / ".env"
    path.write_text('VB_ENV_TEST=from-file\nVB_ENV_NEW="hello world"\n# ignored\n', encoding="utf-8")
    load_env(path)
    assert os.environ["VB_ENV_TEST"] == "from-shell"
    assert os.environ["VB_ENV_NEW"] == "hello world"
