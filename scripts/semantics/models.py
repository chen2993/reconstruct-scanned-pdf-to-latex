"""审计用的数据结构。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuditConfig:
    owner_environments: frozenset[str]
    owner_parent_environments: dict[str, frozenset[str]]
    cross_page_owner_environments: frozenset[str]
    structure_commands: frozenset[str]
    media_environments: frozenset[str]
    answer_owner_environments: frozenset[str]
    question_owner_environments: frozenset[str]
    answer_media_environments: frozenset[str]
    forbidden_commands: frozenset[str]
    standalone_commands: frozenset[str]


@dataclass(frozen=True)
class Issue:
    path: str
    line: int
    column: int
    code: str
    message: str

    def as_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "line": self.line,
            "column": self.column,
            "code": self.code,
            "message": self.message,
        }


@dataclass(frozen=True)
class EnvironmentFrame:
    name: str
    path: str
    line: int
    column: int
    is_owner: bool


class ConfigurationError(RuntimeError):
    pass
