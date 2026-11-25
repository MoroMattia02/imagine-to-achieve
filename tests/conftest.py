"""Test-session setup shared by all test files.

MuJoCo picks its OpenGL backend from ``MUJOCO_GL`` when ``mujoco`` is first imported, so this must
run before any test module imports it. On Linux the twin renders off-screen (workstation over SSH,
cluster nodes), so the default there is EGL; an explicit ``MUJOCO_GL`` always wins. Windows and
macOS keep MuJoCo's default backend.
"""

from __future__ import annotations

import os
import sys

if sys.platform.startswith("linux"):
    os.environ.setdefault("MUJOCO_GL", "egl")
