# Data types

The records passed between modules. Shapes are for one chunk (B environments, 32 policy steps at
15 Hz, 64 frames at 30 Hz; N chunks per rollout; K twin samples). Field-level documentation is on
the API pages.

## Results passed between modules

| Type | Defined in | Fields |
|---|---|---|
| `ActionReport` | `twin.actions` | `ok`, `errors`, `warnings`, plus per-step diagnostics: `trans_norm`, `rot_angle`, `rot6d_col_norms`, `rot6d_cos`, `rot6d_residual`, `nonfinite`, `degenerate_rot6d`, `gripper_out_of_range` |
| `EEFTargets` | `twin.actions` | `policy_states` (B, 32, 7), `ctrl_states` (B, 64, 7), `ctrl_condition` (B, 64, 7), `next_state` (B, 7) |
| `IKResult` | `twin.ik` | `q` (6,), `converged`, `iters`, `pos_err`, `rot_err`, `at_limit` (6,), `min_singular_value` |
| `PathIKResult` | `twin.ik` | `q` (64, 6), `converged` (64,), `pos_err`, `rot_err`, `at_limit` (64, 6), `joint_step`, `speed_violation`, `min_singular_value`, `branch_switch`, `iters`; property `feasible` |
| `JointChunk` | `twin.actions` | `q` (64, 6), `gripper` (64,), `eef`, `action_check`, `ik`, `next_state` (7,); property `feasible` |
| `SceneState` | `twin.scene` | `laptop_xy` (2,), `laptop_yaw`, `lid_angle` (0 = closed), `q` (6,), `gripper` |
| `ChunkRollout` | `twin.scene` | `states` (list), `lid_angle`, `contact_finger_lid`, `max_penetration` (64 values each) |
| `ChunkResult` | `twin.session` | `joints`, `rollout`, `renders` (dict per camera) |
| `EpisodeFit` | `twin.init_fit` | `episode_id`, `best`, `near_optimal`, `iou_per_view`, `q0` |
| `Label` | `twin.verdict` | enum: `CONSISTENT`, `WRONG_REACTION`, `IGNORES_ACTION`, `INVENTS_EFFECT`, `NO_VERDICT` (Step 6.4) |
| `TwinDecision` | `twin.verdict` | `Literal["effect+", "effect-", "none", "undecided"]` (Definition 1) |
| `Calibration` | `twin.conformal` | `m` (N,) from the fitting half, `q_alpha`, `T_calib` in the order of the calibration ids |
| `TrustStats` | `rlinf_modified.algorithms.trust` | `weight_below_one_share`, `weight_mean`, `std_ratio` [T, groups], `adv_abs_max` |

## Configuration records

Frozen dataclasses with a module-level default instance.

| Type | Defined in | Default | Holds |
|---|---|---|---|
| `AdapterConfig` | `twin.actions` | `PRODUCTION_ADAPTER` | gains, translation frame and sign, rotation mode, 15/30 Hz, resampling, Ctrl-World chunk, gripper clip |
| `ActionCheckConfig` | `twin.actions` | `DEFAULT_CHECK` | step-size limits, rot6d tolerances, degeneracy thresholds, gripper range |
| `IKConfig` | `twin.ik` | `DEFAULT_IK` | tolerances, iteration limit, damping schedule, maximum step, joint limits |
| `LaptopGeometry` | `twin.scene` | `DEFAULT_GEOMETRY` | base and lid sizes, hinge offset, maximum lid angle (placeholders) |
| `PhysicsParams` | `twin.scene` | `DEFAULT_PARAMS` | one ψ: hinge friction, damping, armature, masses, friction coefficients, contact softness, controller lag |
| `RefereeDefaults` | `twin.conformal` | `DEFAULTS` | s0 = 2, α = 0.1 |

`CameraIntrinsics` (fx, fy, cx, cy, width, height; `K`, `resized`) and `Camera` (name,
intrinsics, `T_WC`, `attached_to_eef`) in `twin.cameras` describe one camera; real values come
from the lab or WP 3.3.
