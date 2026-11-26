# Files

One section per module: its role, its public names and its status. Private helpers (leading
underscore) are named only where they matter for understanding. The full signatures and
docstrings are on each module's API page.

## Kinematics

### `twin.transforms`

`src/twin/transforms.py` · implemented · [API](reference/twin.transforms.md)

The rotation and pose maths every other module uses. numpy only, batched over leading axes.

| Name | What it does |
|---|---|
| `skew(v)` | 3×3 matrix [v]× with [v]× u = v × u |
| `rotvec_to_matrix(r)` | axis-angle vector to rotation matrix (Rodrigues' formula) |
| `so3_log(R)` | rotation matrix to axis-angle vector; accurate up to π − 1e-9 |
| `geodesic_angle(Ra, Rb)` | angle of Raᵀ Rb, via `atan2` (accurate near 0 and π) |
| `make_T(R, p)`, `invert_T(T)` | build a 4×4 pose; invert it using Rᵀ |

### `twin.robot`

`src/twin/robot.py` · implemented · [API](reference/twin.robot.md)

The UR5 model, numerically and for MuJoCo.

| Name | What it does |
|---|---|
| `UR5_DH`, `TCP_OFFSET` | the six (a, d, α) rows read from the repo; tool offset (0, 0, 0.18) m |
| `JOINT_LIMITS`, `JOINT_NAMES`, `LINK_NAMES` | ±2π per joint; names used in the MJCF |
| `dh_transform(a, d, alpha, theta)` | one link transform Rz(θ) Tz(d) Tx(a) Rx(α) |
| `fk(q, tcp=True)` | forward kinematics, (…, 6) → (…, 4, 4) |
| `ur5_mjcf_xml()` | builds the MJCF text from `UR5_DH`, without importing MuJoCo. Uses `_rx_quat` (exact quarter turns with `sqrt(0.5)`, WP 1.1), `_num` and `_vec` for formatting |
| `UR5_ASSET_PATH` | `src/twin/assets/ur5.xml` |
| `load_ur5_model()` | `mujoco.MjModel.from_xml_string(ur5_mjcf_xml())` (lazy import) |

The MJCF places every body frame on its own joint axis (hinge about +z, `qpos` = q), with sites
`flange` and `tcp`. Geoms are visual-only capsules (`contype="0"`), so the arm has no collisions yet.

### `twin.repo_import`

`src/twin/repo_import.py` · implemented · [API](reference/twin.repo_import.md)

Gives the twin the repo's own conversion functions, so it cannot drift from production.
`load_eef_pose_adapter()` loads `third_party/rlinf_runtime/rlinf/envs/world_model/eef_pose_adapter.py`
*by file path* with `importlib`, registers it in `sys.modules` under a private name, and caches
it (`functools.cache`). Loading by path avoids `import rlinf...`, which would run the runtime's
package `__init__` and pull in Ray and the whole training stack. `EEF_POSE_ADAPTER_PATH` is the
file's location.

### `twin.ik`

`src/twin/ik.py` · implemented · [API](reference/twin.ik.md)

Joint angles for end-effector poses. numpy only.

| Name | What it does |
|---|---|
| `joint_frames(q)` | the 7 frames T_{B,i} along the arm, (7, 4, 4) |
| `jacobian(q)` | geometric Jacobian (6, 6) at the TCP, from `joint_frames` |
| `branch_of(q)` | which of the 8 UR5 solution families (shoulder, elbow, wrist) q belongs to |
| `ik_analytic(T_BE)` | closed-form IK: all solutions, up to 8 |
| `nearest_equivalent`, `initial_configuration` | pick the solution closest to a reference (when only an EEF pose is known) |
| `IKConfig`, `DEFAULT_IK` | tolerances (1e-6), damping settings, maximum step, joint limits |
| `pose_error(T_target, T)` | 6-D error: position difference and `so3_log` of the rotation difference |
| `ik_dls(T_target, q_seed)` → `IKResult` | damped least squares from a warm start |
| `track_path(T_targets, q_start, dt)` → `PathIKResult` | `ik_dls` frame by frame, each seeded with the previous solution, plus feasibility flags |
| `UR5_MAX_JOINT_SPEED` | π rad/s per joint (180 deg/s) (check) |

### `twin.actions`

`src/twin/actions.py` · implemented · [API](reference/twin.actions.md)

One policy chunk to 64 joint targets, exactly as production converts it.

| Name | What it does |
|---|---|
| `ACTION_DIM`, `identity_actions(n)` | 10; a chunk that does not move |
| `ActionCheckConfig`, `check_actions(a)` → `ActionReport` | hard errors (shape, NaN, degenerate rot6d) and warnings (large steps, gripper range) |
| `AdapterConfig`, `PRODUCTION_ADAPTER` | the resolved production settings (gains, frame, 15/30 Hz, gripper clip) |
| `actions_to_eef_targets(state, a)` → `EEFTargets` | the repo conversion in float32: chain, clip, resample, Ctrl-World alignment |
| `eef_state_to_T(states)` | 7-D EEF states (axis-angle) to 4×4 poses |
| `ActionsToJoints(T_WB).step_chunk(state, a, q)` → `JointChunk` | checks + EEF targets + T_WB⁻¹ + `track_path` |

## Scene, cameras and the session

### `twin.scene`

`src/twin/scene.py` · skeleton · [API](reference/twin.scene.md)

The physical scene of T3. The data classes exist; `LaptopScene`'s methods raise
`NotImplementedError`.

| Name | What it is |
|---|---|
| `PHYSICS_TIMESTEP`, `SUBSTEPS_PER_FRAME` | 1/480 s; 16 physics steps per 30 Hz frame |
| `LaptopGeometry`, `DEFAULT_GEOMETRY` | box sizes, hinge offset, maximum opening (placeholders) |
| `PhysicsParams`, `DEFAULT_PARAMS` | one ψ: hinge friction, damping, masses, friction coefficients, contact softness, lag |
| `SceneState` | x = (p_x, p_y, yaw, ϑ) plus joints and gripper |
| `GripperModel.opening(g)` | absolute gripper value → finger opening (linear, clipped; implemented) |
| `ChunkRollout` | per-frame record of one chunk (lid angle, contacts, penetration) |
| `LaptopScene`: `mjcf_xml`, `reset`, `step_chunk`, `get_state` | the scene itself (skeleton, WP 2.3) |

### `twin.cameras`

`src/twin/cameras.py` · skeleton · [API](reference/twin.cameras.md)

Camera parameters. `PHYSICAL_CAMERAS` (`d405_0_rgb`, `d405_1_rgb`, `d435_rgb`; main, side,
wrist), `DATASET_IMAGE_SIZE` (480, 640), `LOOP_IMAGE_SIZE` (192, 320); `CameraIntrinsics` with
`K` and `resized(h, w)`; `Camera` (name, intrinsics, pose, wrist flag); `project(K, T_WC, p_W)`
(pinhole projection, implemented). Building MJCF cameras from these is WP 3.1.

### `twin.render`

`src/twin/render.py` · render implemented, masks skeleton · [API](reference/twin.render.md)

Images of the twin. `TwinRenderer(model, height=192, width=320)` keeps one `mujoco.Renderer`
(the OpenGL context is expensive, so it is reused). `render(data, camera)` checks that the camera
exists (`mj_name2id`, else `KeyError`), then calls `update_scene` and `render`, and returns a new
`uint8` array (H, W, 3). It never calls `mj_forward` and never changes `data`: the caller keeps
the state up to date. `render_masks` is T4 (WP 3.1). Usable as a context manager
(`with TwinRenderer(...) as r:`).

### `twin.init_fit`

`src/twin/init_fit.py` · skeleton · [API](reference/twin.init_fit.md)

The per-episode scene fit of Step 2. `EpisodeFit` (episode id, best and near-optimal
`SceneState`s, IoU per view, q0); `SCENE_CACHE_DIR` = `scene_cache/`; `fit_episode` and
`load_cached_fit` raise `NotImplementedError` (WP 3.2).

### `twin.session`

`src/twin/session.py` · kinematics implemented, physics skeleton · [API](reference/twin.session.md)

The twin of one environment through an episode. `TwinSession(actions_to_joints, scene=None)` with
`reset(eef_state, q0, scene_state=None)`, `step_chunk(actions)` → `ChunkResult` (joints, rollout,
renders) and `reachability_summary()`. It carries two pieces of state between chunks: the
open-loop EEF state (`next_state`, as Ctrl-World does) and the last joint vector (the IK seed for
the next chunk).

## Referee maths (Phase 1)

Pure functions on arrays: they import nothing from the scene and run no model. Their inputs are
scores and features that later WPs produce (WP 2.2, 4.2); nothing calls them yet (WP 5.1).

### `twin.compare`

`src/twin/compare.py` · implemented (WP 1.3) · [API](reference/twin.compare.md)

Comparison of a rendered and a generated video through change features: Step 4 (eqs. (11)-(12),
P4) and Step 7.2 (eq. (16)). numpy; it does not know the encoder (V-JEPA 2 comes in WP 4.2).

| Name | What it does |
|---|---|
| `change_features(phi, phi_ref)` | eq. (11) for one camera: c [Tw, d] = φ − φ_ref; both inputs must be unit-normalised (`UNIT_NORM_TOL` = 1e-5) |
| `average_views(per_view)` | mean over cameras, keyed by `PHYSICAL_CAMERAS` names (role names are rejected), summed in a fixed order |
| `d_tilde(c_x, c_y, window_index)` | eq. (12): mean over the chunk's windows T_k of ‖c_x − c_y‖; a pseudometric, at most 4 (P4) |
| `grounded_scores(c_w, c_s, window_index)` → (S, κ) | eq. (16): S = min over the twin samples θ of D̃(c_w, c_s[θ]); κ = max D̃ between twin samples (0 for one sample) |

`window_index` holds distinct integer positions (masks are rejected); the caller maps chunk k to
its windows T_k (open: no module owns this mapping yet, G3 in `open_items_and_deviations.md`).
The scores Q = −D̃ of eq. (13) are not computed here.

### `twin.verdict`

`src/twin/verdict.py` · implemented (WP 1.4) · [API](reference/twin.verdict.md)

Chunk-0 verdicts and the probe weight: Step 6 (eqs. (14)-(15), Definition 1, the table of
Step 6.4, P6, P8, P9, P11) and eq. (19) at chunk 0. numpy and `math`.

| Name | What it does |
|---|---|
| `Label`, `FAILURE_LABELS` | the five labels of Step 6.4; the order in which failures are reported |
| `TwinDecision`, `TWIN_DECISIONS` | `"effect+"`, `"effect-"`, `"none"`, `"undecided"` |
| `twin_decision(tau_s, eta0, eta, phase_ok)` | Definition 1 on τ_S(θ) over the twin samples; undecided outside the twin's phases; η ≥ η0 ≥ 0 enforced |
| `common_seed_effect(q_a, q_alt)` | Ctrl-World's common-seed estimate τ̂_W (P6) |
| `pooled_sigma(q_w)` | σ_W of eq. (15), pooled over candidates, n(R − 1) degrees of freedom |
| `significance(tau_hat, sigma, s0)` → (s_W, bool) | s_W = \|τ̂_W\| / σ_W and whether s_W ≥ s0 |
| `verdict(twin_dec, w_significant, sign_tau_w)` → `Label` | the table of Step 6.4 |
| `combine_probes(labels)` | one candidate's label from its J probes: any failure, else any consistent, else no verdict |
| `null_action_label(object_motion_score, sigma, s0)` | label of the null action (P8); reported for RQ1, never in the weights |
| `probe_weight(label, s_w, s0, alpha_w, w_min, probed)` | p_{i,0} of eq. (19) in [w_min, 1]; the no-verdict case is floored at w_min (decided 26 Nov) |
| `candidate_pair_deltas(q)`, `ranking_agreement(...)` | candidate pairs Δ of Step 6.2, for the audit (E1) only |

### `twin.conformal`

`src/twin/conformal.py` · implemented (WP 1.5) · [API](reference/twin.conformal.md)

Conformal threshold, divergence chunk and grounded weights: Step 7 (7.3, 7.4, eq. (17), P12),
eq. (18) with the soft ablation of Step 8.1, and the calibration rules of Steps 5, 5.3 and 7.3.
numpy, `math` and `fractions`. Chunks are 0-based; `k* = None` stands for k* = ∞.

| Name | What it does |
|---|---|
| `abstains(kappa, kappa_max, phase_ok)` | chunks where the twin abstains: κ_k > κ_max, or outside the phases |
| `trajectory_score(S, m, abstain)` | eq. (17): T = max over non-abstaining chunks of S_k / m_k (−∞ if all abstain) |
| `conformal_rank(n, alpha)`, `conformal_threshold(T_scores, alpha)` | the ⌈(n+1)(1−α)⌉-th smallest calibration score (rank in exact rationals); raises when n is too small |
| `divergence_chunk(S, m, kappa, kappa_max, phase_ok, q_alpha)` | k*: the first non-abstaining chunk with S_k / m_k > q_α, or `None` |
| `grounded_weights(k_star, N, w_min, *, soft, ...)` | g of eq. (18): hard step at k*, or the soft ablation (logistic around q_α on the running max) |
| `combined_weights(p0, g)` | w_k = p_k g_k of eq. (18) with p_k = 1 for k ≥ 1; not clipped, so w ∈ [w_min², 1] |
| `split_fit_calibration(episode_ids, seed)` | the 20/20 split of the demonstrations (Step 5) |
| `per_chunk_scale(S_fit)` | m_k: median score per chunk on the fitting half (Step 7.3) |
| `calibrate(scores, abstain, fit_ids, calib_ids, alpha)` → `Calibration` | m from the fitting ids, q_α from the calibration ids |
| `appearance_floor(delta_q_s_appearance)` | η0 = 95th percentile of \|ΔQ_S\| and η = 2 η0 (Step 5.3) |
| `RefereeDefaults`, `DEFAULTS` | frozen constants s0 = 2, α = 0.1 |

## Trust weighting

### `rlinf_modified.algorithms.trust`

`src/rlinf_modified/algorithms/trust.py` · implemented (WP 1.2) · [API](reference/rlinf_modified.algorithms.trust.md)

Proposal Step 8.2: imputed rewards (eq. (20)) inside the group-normalised suffix advantages
(eq. (4)), with both scale options of decision D1 (`docs/thesis/notes/d1_scale_policy.md`). Torch.

| Name | What it does |
|---|---|
| `group_members(group_index)` | column indices of every group, [groups, G]; groups need not be contiguous (production groups span ranks) |
| `suffix_returns(r, dones, gamma)` | R_ik = Σ_{j≥k} γ^{j−k} r_ij, cut at done boundaries; the same operations as the old function |
| `trust_weighted_rewards(r, w, group_index)` | eq. (20) only: r̂ = w r + (1 − w) m_k |
| `trust_weighted_suffix_advantages(...)` → (A, `TrustStats`) | the full computation; `std_source` ∈ {`"weighted"` (A, default), `"unweighted"` (B)} |
| `TrustStats` | share of w < 1, mean w, std ratio per group and chunk, max \|A\| |
| `_impute`, `_normalise`, `_check_weights` | building blocks; the tests call `_impute` directly for w = 0 (P14 (c)), which the public functions reject |

### `rlinf_modified.algorithms.advantages`

`src/rlinf_modified/algorithms/advantages.py` · implemented · [API](reference/rlinf_modified.algorithms.advantages.md)

The synthetic engine's advantage function `grpo_action_suffix_advantages`, with optional
`weights` and `std_source`. With `weights=None` the original lines run unchanged (tested against a
frozen copy); otherwise it builds a contiguous group index and calls
`trust_weighted_suffix_advantages`.

## Scripts

| Script | What it does |
|---|---|
| `scripts/make_twin_ur5_mjcf.py` | writes `ur5_mjcf_xml()` to `src/twin/assets/ur5.xml` with `\n` line endings (same bytes on Windows and Linux) |
| `scripts/make_twin_fk_reference.py` | 1000 random joint vectors through the repo's `ur5_joint_actions_to_eef_states` in float64 → `tests/fixtures/twin_fk_reference_ur5.json`, with source hash and commit |
| `scripts/twin_view.py` | viewer: `--model ur5`, `--replay q.json/.npz`, `--demo-chunk [--chunks N]`, `--loop` |
| `scripts/make_code_deps.py` | the generated block of [deps.md](deps.md); `--check` fails if it is stale |
| `scripts/make_book_figures.py` | four figures of the book's FPO chapter, as PDF, into the folder given (CI: `docs/book/figures`) |
