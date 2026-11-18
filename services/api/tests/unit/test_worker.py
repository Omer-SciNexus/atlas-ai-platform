import subprocess
import sys


def test_worker_process_loads_every_table_its_foreign_keys_point_to() -> None:
    """The worker must load all models on its own, without the API routers.

    Run in a fresh interpreter: inside the test process other tests have already
    imported every model, which hides a missing import.
    """
    code = (
        "import app.worker\n"
        "from app.db.base import Base\n"
        "for table in Base.metadata.tables.values():\n"
        "    for fk in table.foreign_keys:\n"
        "        fk.column\n"
    )
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=60, check=False
    )
    assert result.returncode == 0, result.stderr
