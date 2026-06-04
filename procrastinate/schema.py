from __future__ import annotations

import ast
import dataclasses
import pathlib
from importlib import resources
from typing import Literal, cast

from typing_extensions import LiteralString

from procrastinate import connector as connector_module

migrations_path = pathlib.Path(__file__).parent / "sql" / "migrations"
alembic_versions_path = pathlib.Path(__file__).parent / "alembic" / "versions"

MigrationPhase = Literal["pre", "post"]


@dataclasses.dataclass(frozen=True)
class AlembicMigration:
    version: str
    index: int
    phase: MigrationPhase
    migration_file: str
    revision: str
    down_revision: str | None

    def as_dict(self) -> dict[str, str | int | None]:
        return dataclasses.asdict(self)


class SchemaManager:
    def __init__(self, connector: connector_module.BaseConnector):
        self.connector = connector

    @staticmethod
    def get_schema() -> LiteralString:
        # procrastinate takes full responsibility for the queries, we
        # can safely vouch for them being as safe as if they were
        # defined in the code itself.
        schema_sql = (resources.files("procrastinate.sql") / "schema.sql").read_text(
            encoding="utf-8"
        )
        return cast(LiteralString, schema_sql)

    @staticmethod
    def get_migrations_path() -> str:
        return str(migrations_path)

    @staticmethod
    def get_alembic_versions_path() -> str:
        return str(alembic_versions_path)

    @classmethod
    def get_alembic_config_snippet(cls) -> str:
        return (
            "[alembic]\n"
            "version_locations = %(here)s/versions "
            f"{cls.get_alembic_versions_path()}\n"
        )

    @staticmethod
    def get_alembic_migration_plan() -> list[AlembicMigration]:
        return [
            _parse_alembic_migration(path)
            for path in sorted(alembic_versions_path.glob("procrastinate_*.py"))
        ]

    @classmethod
    def get_alembic_revision(cls, version: str, phase: MigrationPhase) -> str:
        normalized_version = _normalize_migration_version(version)
        matches = [
            migration
            for migration in cls.get_alembic_migration_plan()
            if migration.version == normalized_version and migration.phase == phase
        ]
        if not matches:
            raise ValueError(
                f"No Procrastinate Alembic {phase!r} migration found for {version!r}"
            )
        return matches[-1].revision

    def apply_schema(self) -> None:
        queries = self.get_schema()
        queries = queries.replace("%", "%%")
        self.connector.get_sync_connector().execute_query(query=queries)

    async def apply_schema_async(self) -> None:
        queries = self.get_schema()
        queries = queries.replace("%", "%%")
        await self.connector.execute_query_async(query=queries)


def _parse_alembic_migration(path: pathlib.Path) -> AlembicMigration:
    module = ast.parse(path.read_text(encoding="utf-8"))
    values: dict[str, str | None] = {}
    for node in module.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id in {"revision", "down_revision", "MIGRATION_FILE"}
        ):
            name = node.targets[0].id
            if isinstance(node.value, ast.Constant) and isinstance(
                node.value.value, (str, type(None))
            ):
                values[name] = node.value.value

    migration_file = values["MIGRATION_FILE"]
    assert migration_file is not None
    parts = migration_file.removesuffix(".sql").split("_")
    version = parts[0]
    index = int(parts[1])
    phase: MigrationPhase = "post"
    if len(parts) > 2 and parts[2] in {"pre", "post"}:
        phase = cast(MigrationPhase, parts[2])

    return AlembicMigration(
        version=version,
        index=index,
        phase=phase,
        migration_file=migration_file,
        revision=cast(str, values["revision"]),
        down_revision=values["down_revision"],
    )


def _normalize_migration_version(version: str) -> str:
    parts = version.removeprefix("v").split(".")
    if len(parts) != 3:
        return version
    try:
        major, minor, patch = (int(part) for part in parts)
    except ValueError:
        return version
    return f"{major:02d}.{minor:02d}.{patch:02d}"
