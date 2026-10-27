import os

from agent.env import load_env


def test_load_env_reads_values_without_overriding(tmp_path, monkeypatch):
    f = tmp_path / ".env"
    f.write_text("# comment\nTT_A=one\nexport TT_B='two'\nTT_C=three   # note\nTT_EMPTY=\nTT_SET=file\n")
    monkeypatch.setenv("TT_SET", "shell")
    for k in ("TT_A", "TT_B", "TT_C", "TT_EMPTY"):
        monkeypatch.delenv(k, raising=False)
    load_env(f)
    assert (os.environ["TT_A"], os.environ["TT_B"], os.environ["TT_C"]) == ("one", "two", "three")
    assert "TT_EMPTY" not in os.environ
    assert os.environ["TT_SET"] == "shell"
    for k in ("TT_A", "TT_B", "TT_C"):
        monkeypatch.delenv(k)
