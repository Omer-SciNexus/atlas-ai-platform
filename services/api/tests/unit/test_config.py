from pathlib import Path

from app.core.config import API_ROOT, REPO_ROOT, Settings


def test_env_files_are_anchored_to_the_project_not_the_working_directory() -> None:
    env_files = Settings.model_config["env_file"]
    assert env_files == (API_ROOT / ".env", REPO_ROOT / ".env")
    assert (API_ROOT / "pyproject.toml").exists()
    assert (REPO_ROOT / ".env.example").exists()
    assert all(Path(f).is_absolute() for f in env_files)
