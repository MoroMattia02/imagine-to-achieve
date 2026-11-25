"""T1 (MuJoCo part): the generated UR5 MJCF reproduces the repo FK.

Acceptance (twin_implementation_plan.md, T1): for the 1000 in-limit joint vectors of the
reference table generated with the repo function, the MuJoCo `tcp` site pose equals the repo
FK within 1e-5 m and 1e-5 rad.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np
import pytest

mujoco = pytest.importorskip("mujoco")

from twin.robot import (  # noqa: E402
    JOINT_LIMITS,
    JOINT_NAMES,
    UR5_ASSET_PATH,
    fk,
    load_ur5_model,
    ur5_mjcf_xml,
)
from twin.transforms import geodesic_angle, rotvec_to_matrix  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "twin_fk_reference_ur5.json"
POS_TOL = 1e-5
ROT_TOL = 1e-5


@pytest.fixture(scope="module")
def table():
    with FIXTURE.open() as f:
        data = json.load(f)
    return {k: np.asarray(data[k], dtype=np.float64) for k in ("q", "pos", "rotvec")}


@pytest.fixture(scope="module")
def model():
    return load_ur5_model()


def site_poses(model, qs: np.ndarray, site: str) -> tuple[np.ndarray, np.ndarray]:
    data = mujoco.MjData(model)
    sid = model.site(site).id
    pos = np.empty((len(qs), 3))
    rot = np.empty((len(qs), 3, 3))
    for i, q in enumerate(qs):
        data.qpos[:] = q
        mujoco.mj_kinematics(model, data)
        pos[i] = data.site_xpos[sid]
        rot[i] = data.site_xmat[sid].reshape(3, 3)
    return pos, rot


def test_model_structure(model):
    assert model.nq == 6 and model.nv == 6 and model.njnt == 6
    assert [model.joint(j).name for j in range(model.njnt)] == list(JOINT_NAMES)
    assert np.all(model.jnt_type == mujoco.mjtJoint.mjJNT_HINGE)
    np.testing.assert_array_equal(model.jnt_axis, np.tile([0.0, 0.0, 1.0], (6, 1)))
    np.testing.assert_array_equal(model.jnt_pos, np.zeros((6, 3)))
    # Ranges in radians: guards against MJCF's default angle unit (degrees).
    assert np.all(model.jnt_limited == 1)
    np.testing.assert_allclose(model.jnt_range, JOINT_LIMITS, rtol=0, atol=1e-12)
    for name in ("tcp", "flange"):
        model.site(name)  # raises KeyError if missing
    # Visual-only geoms for now: contact is decided in T3.
    assert np.all(model.geom_contype == 0) and np.all(model.geom_conaffinity == 0)
    assert np.all(model.body_mass[1:] > 0)


def test_mujoco_tcp_matches_repo_reference_table(model, table):
    pos, rot = site_poses(model, table["q"], "tcp")
    pos_err = np.linalg.norm(pos - table["pos"], axis=-1)
    rot_err = geodesic_angle(rot, rotvec_to_matrix(table["rotvec"]))
    print(
        f"\nMuJoCo tcp vs repo FK over {len(pos_err)} joint vectors: "
        f"pos max {pos_err.max():.3e} m, rot max {rot_err.max():.3e} rad"
    )
    assert pos_err.max() < POS_TOL, f"pos max {pos_err.max():.3e} at row {pos_err.argmax()}"
    assert rot_err.max() < ROT_TOL, f"rot max {rot_err.max():.3e} at row {rot_err.argmax()}"


@pytest.mark.parametrize("site, tcp", [("tcp", True), ("flange", False)])
def test_mujoco_sites_match_numpy_fk(model, table, site, tcp):
    q = table["q"][:200]
    pos, rot = site_poses(model, q, site)
    T = fk(q, tcp=tcp)
    assert np.abs(pos - T[:, :3, 3]).max() < 1e-12
    assert geodesic_angle(rot, T[:, :3, :3]).max() < 1e-12


def test_mujoco_zero_configuration(model):
    pos, rot = site_poses(model, np.zeros((1, 6)), "tcp")
    np.testing.assert_allclose(pos[0], [-0.81725, -0.37145, 0.089159 - 0.09465], atol=1e-12)
    R_expected = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]])
    np.testing.assert_allclose(rot[0], R_expected, atol=1e-12)


def test_committed_asset_is_generator_output():
    # src/twin/assets/ur5.xml is written by scripts/make_twin_ur5_mjcf.py; never hand-edit it.
    assert UR5_ASSET_PATH.read_text(encoding="utf-8") == ur5_mjcf_xml()


@pytest.mark.parametrize("direction", [2.0, -2.0])
def test_generator_output_does_not_depend_on_libm(monkeypatch, direction):
    # WP 1.1: libm sin/cos may differ by 1 ulp between platforms (sin(pi/4) does between the
    # Windows and Linux libm). Simulate such a libm; the generated MJCF must not change.
    reference = ur5_mjcf_xml()

    def off_by_one_ulp(f):
        return lambda x: float(np.nextafter(f(x), direction)) if x else f(x)

    monkeypatch.setattr(math, "sin", off_by_one_ulp(math.sin))
    monkeypatch.setattr(math, "cos", off_by_one_ulp(math.cos))
    assert ur5_mjcf_xml() == reference


def test_generator_writes_exact_quarter_turn_quaternions():
    # Rx(0) and Rx(+-pi/2) exactly: (1, 0, 0, 0) and (sqrt(0.5), +-sqrt(0.5), 0, 0).
    s = "0.7071067811865476"  # repr(math.sqrt(0.5)); sqrt is correctly rounded on every platform
    quats = set(re.findall(r'quat="([^"]+)"', ur5_mjcf_xml()))
    assert quats == {"1.0 0.0 0.0 0.0", f"{s} {s} 0.0 0.0", f"{s} -{s} 0.0 0.0"}


def test_asset_file_loads_to_same_kinematics(model):
    from_file = mujoco.MjModel.from_xml_path(str(UR5_ASSET_PATH))
    q = np.random.default_rng(3).uniform(-math.pi, math.pi, size=(20, 6))
    p_a, r_a = site_poses(model, q, "tcp")
    p_b, r_b = site_poses(from_file, q, "tcp")
    np.testing.assert_array_equal(p_a, p_b)
    np.testing.assert_array_equal(r_a, r_b)
