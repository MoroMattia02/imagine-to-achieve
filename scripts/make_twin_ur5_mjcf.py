"""Write src/twin/assets/ur5.xml from the DH constants in twin.robot.

    python scripts/make_twin_ur5_mjcf.py

The file is generated, never hand-edited; tests/test_twin_mujoco_fk.py checks that the
committed file equals the generator output and that its tcp site matches the repo FK.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from twin.robot import UR5_ASSET_PATH, ur5_mjcf_xml  # noqa: E402


def main() -> None:
    UR5_ASSET_PATH.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n": identical bytes on Windows and Linux, so the sync test is platform-free.
    with UR5_ASSET_PATH.open("w", encoding="utf-8", newline="\n") as f:
        f.write(ur5_mjcf_xml())
    print(f"wrote {UR5_ASSET_PATH.relative_to(REPO_ROOT).as_posix()}")


if __name__ == "__main__":
    main()
