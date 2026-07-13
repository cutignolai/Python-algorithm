import json
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def load_templates() -> list[dict]:
    templates = []
    if not TEMPLATES_DIR.exists():
        return templates
    for folder in sorted(TEMPLATES_DIR.iterdir()):
        if not folder.is_dir():
            continue
        cfg_path = folder / "config.json"
        if cfg_path.exists():
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            cfg["_path"] = folder
            templates.append(cfg)
    return templates
