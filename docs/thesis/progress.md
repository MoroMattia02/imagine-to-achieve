# Twin progress log

Last updated: 17 Nov 2026. Branch `twin`. Milestones refer to `docs/thesis/twin_implementation_plan.md`.

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

**T2 synthetic part: done. Demo part (real `observation.state` check) still open, needs the dataset.**

| Item | Where | Result |
|---|---|---|
| Geometric Jacobian at the TCP, closed-form IK (8 branches), damped least squares with warm start, path tracking with feasibility flags | `src/twin/ik.py` | Jacobian equals finite differences and MuJoCo `mj_jacSite` (1e-12) |
| 10-D action checks (shape, non-finite, degenerate rot6d = hard errors; large steps, non-orthonormal rot6d, gripper range = warnings) | `src/twin/actions.py` (`check_actions`) | unit-tested |
| Action chunk to EEF targets, through the repo functions in float32 | `actions_to_eef_targets` | **bit-exact** with production `CtrlWorldEnv._convert_via_analytic_ur5_rot6d` (called on a stand-in `self`) |
| Chunk to 64 joint targets at 30 Hz, frame W to B via `T_WB` | `ActionsToJoints` | FK(IK) within 1e-6 m / 1e-6 rad over 5 chunks, also with an offset `T_WB` |
| `so3_log`, `invert_T` | `src/twin/transforms.py` | log map checked up to pi - 1e-9 |
| Skeleton for T3-T7 | `scene.py`, `cameras.py`, `render.py`, `init_fit.py`, `session.py` | interfaces + `NotImplementedError`; `TwinSession` runs in kinematics-only mode |
| Tests | `tests/test_twin_ik.py` (14), `test_twin_actions.py` (13), `test_twin_action_to_joints.py` (4), `test_twin_skeleton.py` (4) | 35 passed (Linux, 17 Nov) |

Acceptance (1 mm / 0.1 deg): met by a wide margin; the solver tolerance is 1e-6. The tests were checked for sensitivity: world-frame translation, world-frame rotation, a missing gripper clip, the wrong next state, `T_WB` instead of its inverse, a flipped Jacobian sign and constant damping each make at least one test fail.

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

- **IK in numpy, not `mj_jacSite`.** The guide suggested MuJoCo's Jacobian; the numpy geometric Jacobian is identical (tested) and keeps T2 runnable without mujoco.
- **Closed-form IK as well as DLS.** DLS tracks paths (stays on the seed branch); the closed form picks the initial branch when only an EEF pose is known, and defines the branch label used to flag branch flips.
- **Damping scaled by the pose error.** Fixed damping near the elbow singularity (sin q3 = 0.06) stalled above the 1e-6 tolerance; the damping now fades as the error goes to zero.
- **The twin carries the EEF state open loop like Ctrl-World** (`next_state` of the adapter), not FK of its own joints, so both follow the same commanded path and IK problems show as flags, not drift.
- **Production conversion runs in float32** (`_convert_via_analytic_ur5_rot6d` disables autocast and casts to float32). This settles the float32 open problem: the twin uses float32 too, so it matches bit for bit.
- **Resampling 15 to 30 Hz uses quaternion slerp for rotation**, not linear axis-angle as the guide said. The twin calls the repo function, so this needs no code, only a guide correction.
- **Joint speed limit 180 deg/s on all joints** (UR5 CB3 value, check). Action step plausibility limits (5 cm, 0.35 rad per 1/15 s step) are guesses until the demo action statistics are read (check).

## In progress

Nothing half-done. T1 and T2 (synthetic) are closed. T0 (headless render) has not started; a one-off EGL render of 192x320 worked on this Linux machine (RTX 4070), not yet a test.

## Open problems

- **Which representation is `observation.state` in `close_desktop_lerobot_joint_3cam`? (check, important).** The resolved production config has `joint_action_adapter: none`, so `initial_image_state_representation: auto` resolves to `eef` and the first-frame `observation.state` is used raw as `[x, y, z, rx, ry, rz, gripper]`. The same field is also read as joints (`initial_joint_state_path` points to the same dataset), and the dataset name and a code comment (`world_model_ctrl_world_env.py:2214`) say it holds raw joints. If it holds joints, Ctrl-World is seeded with joint angles as an EEF pose in production. Needs `meta/info.json` or one episode (lab request 1). It also decides how the twin gets `q0` and `T_WB`: from joints, `T_WB` follows from FK; from EEF only, `q0` comes from `initial_configuration`.
- **Camera naming conflict (check before T4).** The plan says main = `d435_rgb`; the production config comment says main = D405_0, wrist = D435, extra = D405_1, and the reward remaps them again. The twin keys views by physical camera name (`twin/cameras.py`).
- **MJCF asset tests fail on Linux.** `ur5.xml` was generated on Windows; `math.sin(pi/4)` differs in the last digit between the Windows and Linux libm, so `test_committed_asset_is_generator_output` and `test_asset_file_loads_to_same_kinematics` fail here (kinematics unaffected, 1 ulp). Fix proposal, not applied: write exact `sqrt(0.5)` for alpha = +-pi/2 in the generator, or compare with a tolerance.
- **Gripper clip range** = q01/q99 of the policy action statistics (`action_stats_path`, not in the repo). Needed for exact parity on the gripper channel.

- **Lab requests (critical path), not sent yet.** These are:
  - UR5 vs UR5e, the 0.18 m TCP and the real joint limits (±2π assumed).
  - Camera intrinsics and extrinsics.
  - Laptop dimensions.
  - Gripper geometry.
  - Which episodes Ctrl-World was fine-tuned on.
- **`T_WB` is unknown.** The robot base currently sits at the world origin; it is estimated from demos (T2/section 8) or given by the lab.
- **float32 in production: verified by reading** (see decisions). The repo FK reference stays float64; the action conversion is float32 on both sides.
- **mujoco aarch64 wheel on the GH200 nodes (check).**
- **The full test suite does not run on Windows.** There are 10 failures and 5 collection errors, all already present before T1: Linux-only calls (`os.getuid`, `fcntl`, `resource`) and missing `rlinf`/`omegaconf`/`scipy`. They are not related to the twin.
- **Link masses, radii and meshes are placeholders.** UR5 meshes (ROS-Industrial `universal_robot`, check) are needed later for silhouette-based camera fitting (T4).

## Exact next step

**T0: headless render** (unchanged, see below). Then the **T2 demo check** as soon as the dataset is available: convert the recorded actions of the 8 held-out episodes with `actions_to_eef_targets`, run `ActionsToJoints`, compare with the recorded `observation.state` of the following frames, and report the error distribution. Settle the `observation.state` question first.

T0 steps:

1. Write `tests/test_twin_render.py` first: load `load_ur5_model()`, add a fixed camera, render one 192x320 RGB frame off-screen with `mujoco.Renderer`, and assert the shape is (192, 320, 3) and the frame is not all one colour.
2. Time 100 frames and record ms/frame here (needed for the compute budget in the plan).
3. Use `MUJOCO_GL=egl` on Linux with a GPU (this machine), the default GL backend on Windows.

After T0 and the T2 demo check: T8, then T3 when the lab data arrives.
