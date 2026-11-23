from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import API_ROOT, REPO_ROOT, Settings


def test_env_files_are_anchored_to_the_project_not_the_working_directory() -> None:
    env_files = Settings.model_config["env_file"]
    assert env_files == (API_ROOT / ".env", REPO_ROOT / ".env")
    assert (API_ROOT / "pyproject.toml").exists()
    assert (REPO_ROOT / ".env.example").exists()
    assert all(Path(f).is_absolute() for f in env_files)


_SAFE_PROD = {
    "env": "production",
    "log_json": True,
    "database_url": "postgresql+asyncpg://app:s3cret@db/atlas",
    "migration_database_url": "postgresql+asyncpg://owner:s3cret@db/atlas",
}


def test_safe_production_settings_are_accepted() -> None:
    assert Settings(_env_file=None, **_SAFE_PROD).is_production


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"database_url": "postgresql+asyncpg://atlas_app:atlas_app@db/atlas"}, "Default database"),
        (
            {"migration_database_url": "postgresql+asyncpg://atlas:atlas@db/atlas"},
            "Default migration database",
        ),
        ({"log_json": False}, "ATLAS_LOG_JSON"),
        ({"oidc_algorithms": ["HS256"]}, "asymmetric"),
    ],
)
def test_unsafe_production_settings_are_rejected(override: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        Settings(_env_file=None, **{**_SAFE_PROD, **override})
