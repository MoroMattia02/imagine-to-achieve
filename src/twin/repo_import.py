"""Load the repo's EEF conversion module by file path.

Importing ``rlinf...`` would run the vendored runtime's package init (ray, hydra, ...). Loading
the single file by path only needs torch. Used by the T1 reference-table generator and later by
twin/actions.py (T2), so twin and Ctrl-World share the exact same conversion functions.
"""
from __future__ import annotations

import functools
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[2]
EEF_POSE_ADAPTER_PATH = (
    REPO_ROOT / "third_party" / "rlinf_runtime" / "rlinf" / "envs" / "world_model" / "eef_pose_adapter.py"
)
_MODULE_NAME = "_twin_repo_eef_pose_adapter"


@functools.cache
def load_eef_pose_adapter() -> ModuleType:
    """Return the repo's ``eef_pose_adapter`` module (requires torch)."""
    if not EEF_POSE_ADAPTER_PATH.is_file():
        raise FileNotFoundError(f"repo adapter not found at {EEF_POSE_ADAPTER_PATH}")
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, EEF_POSE_ADAPTER_PATH)
    module = importlib.util.module_from_spec(spec)
    # Must be registered before exec: @dataclass with `from __future__ import annotations`
    # looks the module up in sys.modules.
    sys.modules[_MODULE_NAME] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(_MODULE_NAME, None)
        raise
    return module
