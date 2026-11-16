# Twin progress log

Last updated: 16 Nov 2026. Branch `twin`. Milestones refer to `docs/thesis/twin_implementation_plan.md`.

## Done

**T1: UR5 kinematics. Done, all acceptance criteria met.**

| Item | Where | Result |
|---|---|---|
| numpy standard-DH forward kinematics | `src/twin/robot.py` (`fk`) | equals the repo FK |
| Rotation helpers (axis-angle to matrix, geodesic angle, `make_T`) | `src/twin/transforms.py` | unit-tested |
| Load the repo's `eef_pose_adapter.py` by file path | `src/twin/repo_import.py` | used by the generator, reused in T2 |
| Reference table: 1000 random joint vectors in ±2π, seed 0, repo FK in float64 | `scripts/make_twin_fk_reference.py` writes `tests/fixtures/twin_fk_reference_ur5.json` | 261 KiB, metadata records source hash and commit |
| MuJoCo UR5 model generated from the DH constants | `ur5_mjcf_xml()` in `robot.py`; `scripts/make_twin_ur5_mjcf.py` writes `src/twin/assets/ur5.xml` | compiles in mujoco 4.0.1 |
| Tests | `tests/test_twin_fk.py` (11), `tests/test_twin_mujoco_fk.py` (7) | 18 passed |

Measured parity over the 1000 reference vectors (acceptance: < 1e-5 m and < 1e-5 rad):

| Comparison | Position max | Rotation max |
|---|---|---|
| numpy FK vs repo FK | 3.4e-16 m | 8.2e-14 rad |
| MuJoCo `tcp` site vs repo FK | 7.2e-16 m | 8.2e-14 rad |

The tests were checked for sensitivity: a flipped wrist-3 twist (0.53 m error) and a TCP 1 mm short (1.0e-3 m) fail parity; a missing `angle="radian"` fails the joint-range test.

Other: mujoco 4.0.1 installed in the local `.venv`; added to `pyproject.toml` as the optional extra `twin`. Branch `twin` pushed to the fork (`origin`), not to `upstream`.

## Decisions and why

- **The DH constants are read from the repo function, not from a UR datasheet.** That function produced Ctrl-World's conditioning states, so the twin must reproduce it. Reading it also confirms the twist angles (π/2, 0, 0, π/2, −π/2, 0), which the guide had left as "(check)".
- **Reference table in float64.** In float32 the repo function is off by up to 5.9e-5 rad (4 of 1000 samples above 1e-5), which is over the T1 tolerance.
- **Fixture is JSON.** `.npz` is gitignored and `scripts/verify_no_weights.py` rejects it. JSON float repr round-trips float64 exactly.
- **Guard on small quaternion components (5e-5).** The repo's matrix-to-quaternion step clamps at eps = 1e-8. This alters a component only when it is below 5e-5, and then costs up to about 1e-4 rad. The generator refuses a table that hits this case; the seed-0 minimum is 9.25e-5.
- **Geodesic angle via `atan2(sin, cos)`, not `arccos`.** `arccos` has a floor around 1e-8 near 0 and loses accuracy near π.
- **A staleness test regenerates the table from the live repo function** (needs torch, skipped without it). It fails if `eef_pose_adapter.py` changes.
- **MJCF body frames sit on their own joint axes.** Each hinge is +z at its body origin, and `qpos = q` with no offsets. This avoids the DH-vs-MuJoCo joint-axis pitfall from the guide.
- **MJCF is generated, never hand-edited.** A test checks that the committed `ur5.xml` equals the generator output.
- **`compiler angle="radian"` is explicit.** MJCF defaults to degrees, which would silently make the ±2π ranges ±0.11 rad.
- **Geoms are visual-only capsules with nominal UR5 masses.** They have no contact; contact is decided in T3, and the masses and radii are placeholders (check).
- **mujoco is an optional extra, pinned at 4.0.1.** This keeps the cluster environment unchanged until the aarch64 wheel is checked.

## In progress

Nothing half-done. T1 is closed, and T0 (headless render) has not started.

## Open problems

- **Lab requests (critical path), not sent yet.** These are:
  - UR5 vs UR5e, the 0.18 m TCP and the real joint limits (±2π assumed).
  - Camera intrinsics and extrinsics.
  - Laptop dimensions.
  - Gripper geometry.
  - Which episodes Ctrl-World was fine-tuned on.
- **`T_WB` is unknown.** The robot base currently sits at the world origin; it is estimated from demos (T2/section 8) or given by the lab.
- **float32 in production (check).** If the env calls the repo FK or conversion in float32, the error is about 6e-5 rad. That is small for the referee, but worth knowing when comparing.
- **mujoco aarch64 wheel on the GH200 nodes (check).**
- **The full test suite does not run on Windows.** There are 10 failures and 5 collection errors, all already present before T1: Linux-only calls (`os.getuid`, `fcntl`, `resource`) and missing `rlinf`/`omegaconf`/`scipy`. They are not related to the twin.
- **Link masses, radii and meshes are placeholders.** UR5 meshes (ROS-Industrial `universal_robot`, check) are needed later for silhouette-based camera fitting (T4).

## Exact next step

**T0: headless render.**

1. Write `tests/test_twin_render.py` first: load `load_ur5_model()`, add a fixed camera, render one 192x320 RGB frame off-screen with `mujoco.Renderer`, and assert the shape is (192, 320, 3) and the frame is not all one colour.
2. Time 100 frames and record ms/frame here (needed for the compute budget in the plan).
3. Use the default GL backend on Windows; `MUJOCO_GL=egl` only on Linux with a GPU.

After T0: T2 synthetic (IK by damped least squares with warm start, `FK(IK(x))` within 1 mm / 0.1°), then T8.
