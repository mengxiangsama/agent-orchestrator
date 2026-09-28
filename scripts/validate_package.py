#!/usr/bin/env python3
"""Validate this package's simple metadata and relative links; not model behavior."""
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "SKILL.md", "README.md", "LICENSE", "agents/openai.yaml",
    "references/runtime.md", "references/dispatch.md", "references/ledger.md",
    "references/acceptance.md", "examples/scenarios.md", "examples/coupon-order-payment.md",
    "examples/accepted-run.json", "scripts/check_ledger.py", "evals/README.md",
    "evals/reports/validation.md",
)


def validate(root):
    root = Path(root).resolve()
    errors = ["Missing required file: " + name for name in REQUIRED if not (root / name).is_file()]
    if not (root / "SKILL.md").is_file():
        return errors
    skill = (root / "SKILL.md").read_text(encoding="utf-8")
    header = re.match(r"\A---\n(.*?)\n---(?:\n|$)", skill, re.S)
    if not header:
        errors.append("SKILL.md must start with YAML frontmatter")
    else:
        # Deliberately supports only this repository's two single-line scalar fields.
        fields = {}
        for line in header.group(1).splitlines():
            key, separator, value = line.partition(":")
            if not separator or key in fields or key not in {"name", "description"}:
                errors.append("Unsupported or duplicate frontmatter field: " + key)
            fields[key] = value.strip().strip('"')
        if fields.get("name") != "agent-orchestrator":
            errors.append("Unexpected skill name")
        if not fields.get("description") or len(fields.get("description", "")) > 1024:
            errors.append("Missing or oversized description")

    for path in root.rglob("*"):
        if any(part.startswith(".") or part == "__pycache__" for part in path.relative_to(root).parts):
            continue
        if not path.is_file() or path.suffix not in {".md", ".json", ".yaml"}:
            continue
        content = path.read_text(encoding="utf-8")
        if "[TODO:" in content:
            errors.append(f"Unfinished scaffold: {path.relative_to(root)}")
        if re.search(r"/Users/[^/\s]+/|[A-Za-z]:\\Users\\[^\\\s]+\\|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", content):
            errors.append(f"Private path or key marker: {path.relative_to(root)}")
        if path.suffix == ".json":
            try:
                json.loads(content)
            except ValueError as error:
                errors.append(f"Invalid JSON {path.relative_to(root)}: {error}")
        if path.suffix != ".md":
            continue
        for match in re.finditer(r"\[[^\]\n]+\]\(([^)\n]+)\)", content):
            link = match.group(1).strip().strip("<>")
            parsed = urlparse(link)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            target = (path.parent / unquote(parsed.path)).resolve()
            if not target.is_relative_to(root) or not target.exists():
                errors.append(f"Broken/escaping local link: {path.relative_to(root)} -> {link}")
    return errors


if __name__ == "__main__":
    failures = validate(ROOT)
    if failures:
        print("\n".join(failures), file=sys.stderr)
        sys.exit(1)
    print("Package metadata, required files and local links checked; no behavioral claim.")
