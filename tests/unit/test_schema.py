from __future__ import annotations

import pathlib
from collections import defaultdict

import pytest


def test_get_schema(app):
    assert app.schema_manager.get_schema().startswith("-- Procrastinate Schema")


def test_get_migrations_path(app):
    assert app.schema_manager.get_migrations_path().endswith("sql/migrations")


def test_get_alembic_versions_path(app):
    path = pathlib.Path(app.schema_manager.get_alembic_versions_path())

    assert path.name == "versions"
    assert path.parent.name == "alembic"


def test_get_alembic_config_snippet(app):
    snippet = app.schema_manager.get_alembic_config_snippet()

    assert "version_locations = %(here)s/versions" in snippet
    assert app.schema_manager.get_alembic_versions_path() in snippet


def test_get_alembic_migration_plan(app):
    plan = app.schema_manager.get_alembic_migration_plan()

    assert len(plan) == 38
    assert plan[0].as_dict() == {
        "version": "00.00.00",
        "index": 1,
        "phase": "post",
        "migration_file": "00.00.00_01_initial.sql",
        "revision": "procrastinate_0000",
        "down_revision": None,
    }
    assert plan[-2].version == "03.04.00"
    assert plan[-2].phase == "pre"
    assert plan[-2].revision == "procrastinate_0036"
    assert plan[-1].version == "03.04.00"
    assert plan[-1].phase == "post"
    assert plan[-1].revision == "procrastinate_0037"


@pytest.mark.parametrize(
    "version, phase, revision",
    [
        ("03.04.00", "pre", "procrastinate_0036"),
        ("3.4.0", "pre", "procrastinate_0036"),
        ("v3.4.0", "pre", "procrastinate_0036"),
        ("03.04.00", "post", "procrastinate_0037"),
        ("03.03.00", "pre", "procrastinate_0035"),
    ],
)
def test_get_alembic_revision(app, version, phase, revision):
    assert app.schema_manager.get_alembic_revision(version, phase) == revision


def test_get_alembic_revision__missing_phase(app):
    with pytest.raises(ValueError, match="No Procrastinate Alembic 'post'"):
        app.schema_manager.get_alembic_revision("03.03.00", "post")


def test_apply_schema(app, connector):
    connector.reverse_queries = defaultdict(lambda: "apply_schema")
    connector.set_schema_version_run = lambda *a, **kw: None
    app.schema_manager.apply_schema()

    assert connector.queries == [("apply_schema", {})]


async def test_apply_schema_async(app, connector):
    connector.reverse_queries = defaultdict(lambda: "apply_schema")
    connector.set_schema_version_run = lambda *a, **kw: None
    await app.schema_manager.apply_schema_async()

    assert connector.queries == [("apply_schema", {})]
