"""Validate YAML content: ``python -m se_pov_builder.validate_content [CONTENT_DIR]``."""

from __future__ import annotations

import sys
from pathlib import Path

from .config import TOOL_ROOT
from .knowledge import ContentError, KnowledgeBase


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    content_dir = Path(args[0]) if args else TOOL_ROOT
    try:
        kb = KnowledgeBase.load(content_dir)
    except ContentError as exc:
        print(f"Content in {content_dir} is INVALID:")
        for problem in exc.problems:
            print(f"  - {problem}")
        return 1
    print(f"Content in {content_dir} is valid: {len(kb.personas)} personas, {len(kb.capabilities)} capabilities, "
          f"{len(kb.questions)} questions, {len(kb.scenarios)} demo scenarios, {len(kb.workflows)} workflows, "
          f"{len(kb.pov_template.milestones)} POV milestones.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
