# Twin progress log

Last updated: 25 Nov 2026. Branch `twin`. Milestones refer to `docs/thesis/twin_implementation_plan.md`; work packages (WP) to `docs/thesis/data_free_roadmap.md`.

## Done

**WP 1.1: housekeeping, T0 render, viewer script. Done on Linux (25 Nov); the Windows items are (check).**

| Item | Where | Result |
|---|---|---|
| 1-ulp MJCF mismatch fixed: `Rx(0)`, `Rx(+-pi/2)` written exactly as `(1,0,0,0)`, `(sqrt(0.5), +-sqrt(0.5), 0, 0)` | `_rx_quat` in `src/twin/robot.py` | regenerated `ur5.xml` is **byte-identical** to the committed (Windows) file, so both asset tests now pass on Linux |
| T0: off-screen render from a named MJCF camera, 192x320 | `TwinRenderer.render` / `close` / context manager in `src/twin/render.py` | shape, uint8, not one colour, arm in view (3.9 % of pixels), identical for two renders, changes with `q`, unknown camera = `KeyError` |
| Render time (EGL, RTX 4070, i7-14700) | `MUJOCO_GL=egl python tests/test_twin_render.py` | **0.09-0.10 ms/frame** (3 runs, 100 frames, after one warm-up; `update_scene` + render + read-back). Lower bound: 7 untextured geoms (base + 6 capsules), one view |
| EGL default for pytest on Linux | `tests/conftest.py` | `MUJOCO_GL=egl` unless already set; Windows/macOS untouched |
| Viewer | `scripts/twin_view.py` (`--model ur5`, `--replay q.json/.npz`, `--demo-chunk [--chunks N]`, `--loop`) | headless parts tested; the window itself is (check) on the Windows laptop |
| Tests | `test_twin_render.py` (4), `test_twin_view_script.py` (9), `test_twin_mujoco_fk.py` (+3) | twin subset: **69 passed** (Linux, 25 Nov), was 51 passed + 2 failed |

Sensitivity check (each break reverted afterwards): a libm `sin/cos` for the -pi/2 twist (5 asset tests fail), swapped height/width (shape test), a reused output buffer (identity and state tests), a scene built only once (state test), no camera-name check (unknown-camera test), no finite check on replay files, a demo chunk that does not close (closed-loop test), `fps` of `.npz` files ignored (option wiring test). Not caught, by design: a top-level `import mujoco.viewer` (importing it needs no display, so `--help` still works headless). With `conftest.py` disabled and neither `DISPLAY` nor `MUJOCO_GL` set, the render tests skip with "no OpenGL context" (listed by `-ra`), they do not fail.

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

- **Camera naming resolved by reading (17 Nov): main = `d405_0_rgb`, wrist = `d435_rgb`, side/extra = `d405_1_rgb`.** Source: `CLOSE_DESKTOP_DROID_LAYOUT` / `CLOSE_DESKTOP_VERTICAL_LAYOUT` in `third_party/cosmos_framework/data/vfm/action/camera_layout.py:136`, consistent with the production config comment (main = D405_0, wrist = D435, extra = D405_1). The plan (`twin_implementation_plan.md`, item 9) and guide (section 1) say main = `d435_rgb`; that is wrong and should be corrected there. The terminal-goal reward remaps names again (`ctrl_world_source_mapping`), so the twin still keys views by physical camera name.

- **WP 1.1: exact `sqrt(0.5)` for the quarter-turn twists, not a tolerance in the test.** The intended rotation is exactly pi/2. glibc's `sin(float(pi)/4)` is correctly rounded (`...475`); the Windows libm returned `...476`, which happens to equal `sqrt(0.5)`. IEEE `sqrt` is correctly rounded everywhere, so the generator output is now the same on every platform. A test fakes a libm that is off by 1 ulp in either direction and checks that the MJCF is unchanged, so the property is tested on any single machine.
- **WP 1.1: the render tests add their camera with `MjSpec`**, so the committed `ur5.xml` (pure kinematics) stays unchanged. The real cameras come with T4 (WP 3.1).
- **WP 1.1: `TwinRenderer.render` does not call `mj_forward`.** The caller keeps `data` up to date, and rendering never changes the simulation state. It returns a new array each call.
- **WP 1.1: `tests/conftest.py` sets `MUJOCO_GL=egl` on every Linux run, not only when `DISPLAY` is unset.** This machine has `DISPLAY=:1` even over SSH, so a "headless only" rule would not have triggered here. An explicit `MUJOCO_GL` still wins.
- **WP 1.1: the render tests skip, rather than fail, when no OpenGL context can be created.** The check is a bare `mujoco.Renderer`, separate from `TwinRenderer`, so a bug in the twin code still fails. The skip reason is printed by `-ra`; on this machine the tests run (no skip).
- **WP 1.1: the timing is a `__main__` block in the test file**, so the recorded number comes from the same scene as the tests, without a separate script.

## In progress

Nothing half-done. WP 1.1 is closed on Linux; its Windows checks are listed under open problems.

## Open problems

- **Which representation is `observation.state` in `close_desktop_lerobot_joint_3cam`? (check, important; the repo cannot settle it, 17 Nov).** Two close-desktop dataset formats exist in the code with the same 7-D layout: EEF `[x, y, z, rotvec(3), gripper]` (`UR5EEFLeRobotDataset`) and joints `[q0..q5, gripper]` (`UR5JointLeRobotDataset`, both in `third_party/cosmos_framework/data/vfm/action/datasets/`). Evidence read:
  - For EEF: the resolved production config has `joint_action_adapter: none`, so `initial_image_state_representation: auto` resolves to `eef` and the first-frame `observation.state` seeds Ctrl-World raw as an EEF pose. The production policy (`ur5_eef_rel10d`, close_desktop) was trained by `UR5EEFLeRobotDataset`, which says the source `observation.state` is an absolute EEF pose and anchors the 10-D actions on it; the Ctrl-World stats are `..._eef_state_3cam`. The Push-T demo-chain script treats `observation.state` as EEF too (a different dataset).
  - For joints: the dataset name; the comment at `world_model_ctrl_world_env.py:2214` ("This dataset's observation.state is raw joint angles"); the older pi05 config reads the same path as joints through FK; production still sets `initial_joint_state_path` to the same path.
  - Which dataset root the policy was trained on is not recorded in the repo, and the dataset is not on this machine.
  - If it holds joints, production seeds Ctrl-World with joint angles as an EEF pose (the saturation bug described in the 2214 comment). It also decides how the twin gets `q0` and `T_WB`: from joints, `T_WB` follows from FK; from EEF only, `q0` comes from `initial_configuration`.
  - One-minute check where the data lives: `python -c "import json;f=json.load(open('<dataset>/meta/info.json'))['features'];print(f['observation.state'],f['action'])"` (LeRobot usually stores per-channel `names`). Without names: joints look like `-1.57, -1.9, ...`; an EEF pose has xyz within about +-1 m and a 3-value rotvec of norm <= pi.
- **WP 1.1 on Windows (check).** Run `python -m pytest tests/test_twin_*.py -q` (expect 69 passed; the asset tests should pass since the file is unchanged) and the viewer by hand: `python scripts/twin_view.py`, `--demo-chunk`, `--replay <file>`. MuJoCo's own viewer also works: `python -m mujoco.viewer --mjcf=src/twin/assets/ur5.xml` (flag read from `--help` in 4.0.1; the window was not opened here).
- **Roadmap references checked on 25 Nov (Phase 1 Step 0), not fixed:**
  - the proposal PDF (`thesis_proposal_final.pdf`) is not in the repo, so equation, lemma, proposition and assumption numbers in docstrings are taken from the roadmap (check);
  - `grpo_action_suffix_advantages` takes `(rewards, loss_mask, dones, *, group_size, gamma)`, with contiguous groups, ε = 1e-6 hard-coded, and a float32 cast before the mask. The cross-rank `validate_and_compute_group_suffix_advantages` (`cross_rank_grpo.py:801`) keeps the input dtype and gathers groups with `index_select`; whether the two agree bit for bit is (check, WP 1.2);
  - a third suffix-advantage function, `compute_grpo_action_suffix_advantages` (`third_party/rlinf_runtime/rlinf/algorithms/advantages.py:139`, success anchoring and dynamic gammas), is not mentioned in the roadmap; which one production uses for the close config matters for WP 5.1 (check).
- **Pre-existing ruff findings in `src/twin/robot.py`** (two lines over 100 characters, `zip` without `strict=`) and a missing blank line after two module docstrings; present at `f4f669e`, not touched in WP 1.1.
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

**WP 1.2: trust-weighted advantages** (`data_free_roadmap.md` §2, Step 8, T8, D1). Tests first in `tests/test_trust_weighting.py` (the seven acceptance items), then `src/rlinf_modified/algorithms/trust.py` and the optional `weights=None, std_source="weighted"` arguments of `grpo_action_suffix_advantages` (the old path bit-identical, tested). No edit to `cross_rank_grpo.py`. Also `docs/thesis/notes/d1_scale_policy.md`. Run `tests/test_algorithms_contracts_rewards.py` as well.

Still pending once the dataset is available: the **T2 demo check** (convert the recorded actions of the 8 held-out episodes with `actions_to_eef_targets`, run `ActionsToJoints`, compare with the recorded `observation.state` of the following frames, report the error distribution). Settle the `observation.state` question first.
