"""读取并校验 semantic-audit.json。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .defaults import (
    DEFAULT_ANSWER_MEDIA_ENVIRONMENTS,
    DEFAULT_ANSWER_OWNER_ENVIRONMENTS,
    DEFAULT_CROSS_PAGE_OWNER_ENVIRONMENTS,
    DEFAULT_FORBIDDEN_COMMANDS,
    DEFAULT_MEDIA_ENVIRONMENTS,
    DEFAULT_OWNER_ENVIRONMENTS,
    DEFAULT_QUESTION_OWNER_ENVIRONMENTS,
    DEFAULT_STANDALONE_COMMANDS,
    DEFAULT_STRUCTURE_COMMANDS,
    ENVIRONMENT_NAME,
    IDENTIFIER_NAME,
)
from .models import AuditConfig, ConfigurationError
from .paths import CONFIG_FILENAME, CONTROL_DIR, ROOT_OWNER


def _configured_set(
    payload: dict[str, Any], key: str, default: frozenset[str], pattern: re.Pattern[str]
) -> frozenset[str]:
    if key not in payload:
        return default
    value = payload[key]
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ConfigurationError(f"{key} 必须是字符串数组")
    normalized: list[str] = []
    for item in value:
        name = item[1:] if key == "structure_commands" and item.startswith("\\") else item
        if pattern.fullmatch(name) is None:
            raise ConfigurationError(f"{key} 中的名称无效: {item!r}")
        normalized.append(name)
    if len(normalized) != len(set(normalized)):
        raise ConfigurationError(f"{key} 包含重复名称")
    return frozenset(normalized)


def _configured_owner_parents(
    payload: dict[str, Any], owner_environments: frozenset[str]
) -> dict[str, frozenset[str]]:
    """Read an optional direct-parent allowlist for semantic owners.

    Keys are child owner environments. Values contain owner environments or the
    ``$root`` sentinel for a root owner. Omitted children stay unconstrained so
    a project can introduce this check incrementally while its class API grows.
    """
    key = "owner_parent_environments"
    if key not in payload:
        return {}
    value = payload[key]
    if not isinstance(value, dict):
        raise ConfigurationError(f"{key} 必须是对象")

    normalized: dict[str, frozenset[str]] = {}
    for child, parents in value.items():
        if not isinstance(child, str) or child not in owner_environments:
            raise ConfigurationError(
                f"{key} 中的子所有者必须属于 owner_environments: {child!r}"
            )
        if not isinstance(parents, list) or not parents:
            raise ConfigurationError(f"{key}.{child} 必须是非空字符串数组")

        parent_names: list[str] = []
        for parent in parents:
            if not isinstance(parent, str):
                raise ConfigurationError(f"{key}.{child} 包含非字符串父所有者")
            if parent == ROOT_OWNER:
                parent_names.append(parent)
                continue
            if parent not in owner_environments:
                raise ConfigurationError(
                    f"{key}.{child} 中的父所有者未登记: {parent!r}"
                )
            parent_names.append(parent)
        if len(parent_names) != len(set(parent_names)):
            raise ConfigurationError(f"{key}.{child} 包含重复父所有者")
        normalized[child] = frozenset(parent_names)
    return normalized

def load_config(project: Path) -> tuple[AuditConfig, Path | None]:
    config_path = project / CONTROL_DIR / CONFIG_FILENAME
    payload: dict[str, Any] = {}
    loaded_path: Path | None = None
    if config_path.exists():
        if not config_path.is_file():
            raise ConfigurationError(f"配置路径不是文件: {config_path}")
        try:
            value = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ConfigurationError(f"无法读取配置 {config_path}: {exc}") from exc
        if not isinstance(value, dict):
            raise ConfigurationError("配置顶层必须是 JSON 对象")
        allowed = {
            "owner_environments",
            "owner_parent_environments",
            "cross_page_owner_environments",
            "structure_commands",
            "media_environments",
            "answer_owner_environments",
            "question_owner_environments",
            "answer_media_environments",
            "forbidden_commands",
            "standalone_commands",
        }
        unknown = set(value) - allowed
        if unknown:
            raise ConfigurationError(f"配置包含未知键: {sorted(unknown)}")
        payload = value
        loaded_path = config_path

    owner_environments = _configured_set(
        payload, "owner_environments", DEFAULT_OWNER_ENVIRONMENTS, IDENTIFIER_NAME
    )
    config = AuditConfig(
        owner_environments=owner_environments,
        owner_parent_environments=_configured_owner_parents(payload, owner_environments),
        cross_page_owner_environments=_configured_set(
            payload,
            "cross_page_owner_environments",
            DEFAULT_CROSS_PAGE_OWNER_ENVIRONMENTS,
            IDENTIFIER_NAME,
        ),
        structure_commands=_configured_set(
            payload, "structure_commands", DEFAULT_STRUCTURE_COMMANDS, IDENTIFIER_NAME
        ),
        media_environments=_configured_set(
            payload, "media_environments", DEFAULT_MEDIA_ENVIRONMENTS, ENVIRONMENT_NAME
        ),
        answer_owner_environments=_configured_set(
            payload,
            "answer_owner_environments",
            DEFAULT_ANSWER_OWNER_ENVIRONMENTS,
            IDENTIFIER_NAME,
        ),
        question_owner_environments=_configured_set(
            payload,
            "question_owner_environments",
            DEFAULT_QUESTION_OWNER_ENVIRONMENTS,
            IDENTIFIER_NAME,
        ),
        answer_media_environments=_configured_set(
            payload,
            "answer_media_environments",
            DEFAULT_ANSWER_MEDIA_ENVIRONMENTS,
            ENVIRONMENT_NAME,
        ),
        forbidden_commands=_configured_set(
            payload,
            "forbidden_commands",
            DEFAULT_FORBIDDEN_COMMANDS,
            IDENTIFIER_NAME,
        ),
        standalone_commands=_configured_set(
            payload,
            "standalone_commands",
            DEFAULT_STANDALONE_COMMANDS,
            IDENTIFIER_NAME,
        ),
    )
    missing_answers = config.answer_owner_environments - config.owner_environments
    missing_questions = config.question_owner_environments - config.owner_environments
    missing_cross_page_owners = (
        config.cross_page_owner_environments - config.owner_environments
    )
    missing_answer_media = config.answer_media_environments - config.media_environments
    if missing_answers:
        raise ConfigurationError(
            "answer_owner_environments 也必须属于 owner_environments: "
            f"{sorted(missing_answers)}"
        )
    if missing_questions:
        raise ConfigurationError(
            "question_owner_environments 也必须属于 owner_environments: "
            f"{sorted(missing_questions)}"
        )
    if missing_cross_page_owners:
        raise ConfigurationError(
            "cross_page_owner_environments 也必须属于 owner_environments: "
            f"{sorted(missing_cross_page_owners)}"
        )
    if missing_answer_media:
        raise ConfigurationError(
            "answer_media_environments 也必须属于 media_environments: "
            f"{sorted(missing_answer_media)}"
        )
    return config, loaded_path
