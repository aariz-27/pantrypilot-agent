"""Direct unit coverage for app.db.connection (audit finding, 2026-09-07:
this module had no dedicated test file -- only indirect exercise via
PriceRepository/ingestion tests)."""

import sqlite3

import pytest

from app.db.connection import check_database_health, connect, connection_scope
from app.db.schema import create_schema


def test_connect_read_write_creates_parent_directory(tmp_path):
    db_path = tmp_path / "nested" / "dir" / "test.db"
    connection = connect(db_path, read_only=False)
    try:
        assert db_path.parent.is_dir()
        assert db_path.exists()
    finally:
        connection.close()


def test_connect_read_only_missing_file_raises_file_not_found(tmp_path):
    missing_path = tmp_path / "does_not_exist.db"
    with pytest.raises(FileNotFoundError):
        connect(missing_path, read_only=True)


def test_connect_read_only_cannot_write(tmp_path):
    db_path = tmp_path / "readonly_write_test.db"
    with connection_scope(db_path, read_only=False) as connection:
        create_schema(connection)

    with connection_scope(db_path, read_only=True) as connection:
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("INSERT INTO ingredient_aliases (alias, canonical_id, source) VALUES ('x', 'y', 'z')")


def test_connection_scope_closes_connection_on_success(tmp_path):
    db_path = tmp_path / "scope_test.db"
    with connection_scope(db_path, read_only=False) as connection:
        create_schema(connection)
    # A closed connection raises ProgrammingError on further use.
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")


def test_connection_scope_closes_connection_even_on_exception(tmp_path):
    db_path = tmp_path / "scope_exception_test.db"
    with pytest.raises(ValueError):
        with connection_scope(db_path, read_only=False) as connection:
            create_schema(connection)
            raise ValueError("boom")
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")


def test_check_database_health_true_for_valid_schema(tmp_path):
    db_path = tmp_path / "healthy.db"
    with connection_scope(db_path, read_only=False) as connection:
        create_schema(connection)
    assert check_database_health(db_path) is True


def test_check_database_health_false_for_missing_file(tmp_path):
    assert check_database_health(tmp_path / "missing.db") is False


def test_check_database_health_false_for_corrupt_file_never_raises(tmp_path):
    corrupt_path = tmp_path / "corrupt.db"
    corrupt_path.write_text("not a real sqlite database")
    assert check_database_health(corrupt_path) is False


def test_check_database_health_false_when_table_missing(tmp_path):
    # A file that is a valid SQLite database but was never given the
    # expected schema (e.g. an unrelated .db file) must report False,
    # not raise.
    db_path = tmp_path / "wrong_schema.db"
    connection = sqlite3.connect(str(db_path))
    connection.execute("CREATE TABLE unrelated_table (id INTEGER)")
    connection.commit()
    connection.close()
    assert check_database_health(db_path) is False
