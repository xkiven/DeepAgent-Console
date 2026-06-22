from __future__ import annotations

from pathlib import Path

import yaml

from app.schemas import SkillSummary


def discover_skills(skills_dir: str | Path) -> list[SkillSummary]:
    root = Path(skills_dir)
    if not root.exists():
        return []

    skills: list[SkillSummary] = []
    for skill_md in sorted(root.glob("*/SKILL.md")):
        parsed = _parse_skill_file(skill_md)
        if parsed:
            skills.append(parsed)
    return skills


def _parse_skill_file(path: Path) -> SkillSummary | None:
    content = path.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return None

    try:
        _, frontmatter, _body = content.split("---", 2)
        data = yaml.safe_load(frontmatter) or {}
    except ValueError:
        return None

    name = data.get("name")
    description = data.get("description")
    if not name or not description:
        return None

    raw_allowed_tools = data.get("allowed-tools") or []
    if isinstance(raw_allowed_tools, str):
        allowed_tools = [item for item in raw_allowed_tools.split() if item]
    else:
        allowed_tools = list(raw_allowed_tools)
    return SkillSummary(
        name=str(name),
        description=str(description),
        path=str(path),
        allowed_tools=[str(item) for item in allowed_tools],
    )
