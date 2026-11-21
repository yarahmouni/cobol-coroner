"""Case registry: the number and name of each trap, read from samples/traps/cases.json."""
import json
from pathlib import Path
from typing import Optional

TRAPS_ROOT = Path(__file__).resolve().parent.parent / "samples" / "traps"
REGISTRY_PATH = TRAPS_ROOT / "cases.json"


class CasesRegistryError(ValueError):
    """The registry file is missing or malformed."""


def load_cases_registry(path: Optional[Path] = None) -> dict[str, dict]:
    """Return {trap id: {"case": int, "name": str}}, read from disk on every call."""
    registry_path = Path(path) if path else REGISTRY_PATH
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise CasesRegistryError(f"Cannot read case registry {registry_path.name}: {e}") from e
    if not isinstance(registry, dict):
        raise CasesRegistryError(f"{registry_path.name} must hold an object")
    for trap_id, entry in registry.items():
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("case"), int)
            or not isinstance(entry.get("name"), str)
        ):
            raise CasesRegistryError(f"{registry_path.name}: entry {trap_id} needs an integer case and a string name")
    return registry


def case_label(trap_id: Optional[str], registry: Optional[dict] = None) -> Optional[str]:
    """Display form "Case N Name", or None when the trap is not in the registry."""
    registry = load_cases_registry() if registry is None else registry
    entry = registry.get(trap_id) if trap_id else None
    if entry is None:
        return None
    return f"Case {entry['case']} {entry['name']}"


def auditable_trap_ids(registry: Optional[dict] = None, traps_root: Optional[Path] = None) -> list[str]:
    """Registry ids that have a trap folder with a trap.json (T6 has none), in case order."""
    registry = load_cases_registry() if registry is None else registry
    root = Path(traps_root) if traps_root else TRAPS_ROOT
    ids = [
        trap_id for trap_id in registry
        if any(root.glob(f"{trap_id}-*/trap.json"))
    ]
    return sorted(ids, key=lambda trap_id: registry[trap_id]["case"])
