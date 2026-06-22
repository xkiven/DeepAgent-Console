from pathlib import Path

from app.skills import discover_skills


def test_discover_skills() -> None:
    skills = discover_skills(Path("skills"))
    names = {skill.name for skill in skills}
    assert {"code-review", "test-generator", "data-analysis"} <= names

