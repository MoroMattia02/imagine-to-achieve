# Scene digital twin: code map and implementation plan

Basis: repository `imagine-to-achieve/imagine-to-achieve`, commit `0d325b1` (read on 13 Nov 2026). The code was read, not run (no torch or mujoco in my workspace). Line numbers refer to that commit. Statements marked **(check)** are inferred, not verified.

Thesis context: `docs/thesis/thesis_context.md` (short version of the final proposal, Steps 1-9, E0-E4). Proposition numbers below refer to the compiled proposal PDF (the lemma and proposition counters are shared; check the numbers in your PDF). Companion: `docs/thesis/twin_detailed_guide.md` (theory, reasons, tests).

---

## 1. What the code showed, and what it changes

1. **The production loop is the vendored RLinf runtime, not `src/rlinf_modified`.** `src/rlinf_modified/engine/real.py` only builds Hydra overrides and launches `third_party/rlinf_runtime/examples/embodiment/train_embodied_agent.py`. `src/rlinf_modified/rewards.py` and `algorithms/advantages.py` are used by the synthetic engine and the tests only. So production hooks sit in vendored files, and the synthetic engine is a torch-only testbed for anything that does not need real assets.

2. **GRPO groups are spread over four ranks.** `group_size: 16`, `members_per_rank: 4`. Advantages are computed after an all-gather of per-chunk scalar rewards (`fsdp_actor_worker.py:1716`). The trust-weighted group mean (proposal Step 8) can therefore only be formed at that point, not in the env worker.

3. **The reward is one scalar per chunk, and every rollout has exactly five chunks.** `reward_type: chunk_level` sums the 32 per-step rewards; the terminal-goal term is added at the last chunk. `ignore_terminations: true`, `max_episode_steps: 160`, so there are no early dones and the loss mask is all ones. This simplifies Step 8.

4. **Ctrl-World can save and restore its state.** `CtrlWorldEnv.get_state()` / `load_state()` (lines 3444 / 3508) include the RNG generator state and the noise-call index. Exact restore (assumption M4) is plausible and chunk-0 probes (Step 6) need no change to Ctrl-World. It still has to be tested.

5. **Ctrl-World noise is common within a group** (`common_random_numbers_within_group: true`, `fixed_ctrl_seed: 42`; vision seeds are per member). Candidate pairs in a group already share Ctrl-World noise. For probes with R different seeds, the seed has to be controlled explicitly through `_common_noise_call_index`.

6. **There are only 32 + 8 start scenes.** `tasks.py` fixes 32 training episodes and 8 evaluation episodes (6, 7, 14, 20, 26, 31, 32, 37). Resets read the first frame (three views plus `observation.state`) from the LeRobot dataset `close_desktop_lerobot_joint_3cam`. So **the initialiser runs offline once per episode and is cached by episode id**. It never runs inside the RL loop, and all 40 fits can be inspected by hand.

7. **The robot in the code is the original UR5, not the UR5e.** `ur5_joint_actions_to_eef_states` (`eef_pose_adapter.py:434`) uses d1=0.089159, a2=-0.425, a3=-0.39225, d4=0.10915, d5=0.09465, d6=0.0823 and a TCP offset of 0.18 m along z. The UR5e has different link constants. MuJoCo Menagerie has a UR5e **(check)**. The proposal text says UR5e and should be corrected; the twin needs a UR5 model checked against this function.

8. **Actions are 10-D body-frame deltas, chained open-loop.** `[pos_delta(3), rot6d_delta(6), gripper_abs(1)]`, converted to absolute EEF poses by `analytic_ur5_rot6d_delta_actions_to_eef_states` (`eef_pose_adapter.py:681`, translation gain 1.0 for close) starting from the env's tracked EEF state. The robot trajectory is a deterministic function of the initial EEF state and the actions. The twin can reuse this exact pure-torch function and then do IK. Because both models share this conversion, the twin cannot detect an error in it. Test T2 guards against that.

9. **Camera names** (`ctrl_world_close_laptop_grpo_cosmos_native_unipc_large.yaml`): main = `d435_rgb`, wrist = `d405_0_rgb`, extra = `d405_1_rgb`. Per-view size is 192x320 in the loop. **Nothing in the repo gives camera intrinsics or extrinsics, a robot MJCF/URDF, or gripper geometry.** These come from the lab or are estimated.

10. **A hook pattern already exists.** `stage15_plugin/` uses `sitecustomize.py` plus monkeypatching, gated by an env var (`RLINF_STAGE15_MODE`), and `launch_ray_node.sh` prepends it to `PYTHONPATH` on Ray nodes. A `twin_plugin/` can follow the same pattern with no edits to vendored files, which keeps the thesis diff small.

11. **Std normalisation weakens the effect of down-weighting (found by reading the code, not in the proposal).** `validate_and_compute_group_suffix_advantages` (`cross_rank_grpo.py:801`) divides by the group std. Imputing distrusted rewards with the trusted mean shrinks that std, so the remaining members get larger normalised advantages: with 12 of 16 imputed at one chunk, each of the 4 trusted members gets about 2x the |advantage| (the sum of squares stays at G-1). The neutrality proposition (part (c), "a reward with w = 0 adds exactly zero to the centred returns"; Proposition 14 in the compiled proposal) is still true, but the group as a whole is not pushed less. I found no global advantage renormalisation in the embodied path (`normalize_advantages` is only referenced in the base actor class, lines 1107 and 1175). Decision D1 below.

---

## 2. Code map: method steps to code

| Step | Where in the code | How to hook it |
|---|---|---|
| 1 General twin | New `src/twin/` package (nothing in the repo) | Offline; no hook |
| 2 Initialiser | Dataset first frames via `LeRobotBookTrajectoryDatasetWrapper._get_first_frame` (keys above, `observation.state`); env reset `world_model_ctrl_world_env.py:2050` knows the episode ids | Offline script over 40 episodes, cache `scene_cache/episode_XXX.json`; env looks up by `reset_state_ids` |
| 3 Same actions in the twin | `_convert_via_analytic_ur5_rot6d` (`world_model_ctrl_world_env.py:1599`) calls `analytic_ur5_rot6d_delta_actions_to_eef_states` | Wrap `CtrlWorldEnv.chunk_step` (3155); twin consumes the same absolute EEF sequence |
| 4 Compare | Ctrl-World views leave the env in `infos` (`world_model_video_chunk*`, `ctrl_world_video_chunk*`), collected in `env_worker.env_interact_step` (`env_worker.py:1235`) | Compute twin renders and V-JEPA change features in the env worker, next to the video |
| 5 Calibration on demos | Dataset plus the pure functions above; Ctrl-World replay via `reset(episode_indices=...)` and `chunk_step` with demo actions | Offline scripts; Ctrl-World replay needs a GPU |
| 6 Chunk-0 probes and null action | `get_state` / `load_state`, `_ctrl_world_group_generators` (2595), `_infer_next_chunk_frames` (2747) | Save state, run a frames-only variant (skip `_infer_next_chunk_rewards`, 2381) with the probe action and chosen seed, restore state |
| 7 Grounded comparison | One twin object per env, advanced chunk by chunk with the same actions | Held by the plugin, keyed by env id, reset at `reset` |
| 8 Trust-weighted rewards | Reward built in `_attach_cosmos_video_reward` (`env_worker.py:1936`), terminal term in `_apply_terminal_goal_reward` (1645), source chosen in `_select_training_rewards` (1404); advantages in `_compute_cross_rank_grpo_advantages` (`fsdp_actor_worker.py:1716`) and `cross_rank_grpo.py:801` | Env worker attaches a per-chunk `trust_weight` to the rollout batch (like the metadata fields); actor gathers it with the rewards; imputation happens before the suffix returns |
| 9 Diagnostics and logging | `trajectory_records` (`_initialize_trajectory_records`, `fsdp_actor_worker.py:2138`), `src/rlinf_modified/analysis.py` | Add verdict, divergence chunk, weight and spread fields |

---

## 3. Decisions to settle

- **D1 Scale policy for imputed advantages.** (A) as proposed: normalise by the std of the imputed returns. (B) normalise by the std of the original (unweighted) returns, so imputation does not inflate the remaining advantages. Recommended: implement both behind a flag and run B as an ablation arm; with w=1 both equal the paper.
- **D2 Two phases.** Phase A, offline referee and audit (RQ1, RQ2): log actions and Ctrl-World outputs from baseline runs and evaluate the twin offline on any CPU machine. Phase B, in-loop weighting (RQ3). This decouples twin development from the aarch64 cluster stack.
- **D3 Plugin or patch.** Recommended: plugin (as in item 10), with a short marked patch only for the actor-side gather.
- **D4 Demos for the phase map.** The Cosmos policy was trained on 32 train / 8 val (checkpoint name). Which episodes Ctrl-World was fine-tuned on is unknown. Ask; prefer unseen episodes for Step 5.2.

---

## 4. Twin implementation plan

### Modules

The repo uses a `src/` layout (`pyproject.toml`: `package-dir = {"" = "src"}`, pytest `pythonpath = ["src"]`, tests in a flat `tests/`), so the twin follows it:

```
src/twin/
  assets/            UR5 MJCF (+meshes), laptop and gripper definitions
  robot.py           UR5 model, FK, IK, controller model (delay, gains)
  actions.py         T_S: reuse repo conversion (import by file path), then IK
  scene.py           LaptopScene: x=(px,py,yaw,theta), psi; reset, step_chunk -> states
  cameras.py         K_v, T_v, extrinsics estimation
  render.py          headless 3-view render, masks, texture from the first frame
  init_fit.py        SAM 3 masks + fit + near-optimal set, per-episode cache
  features.py        V-JEPA change features (later)
tests/test_twin_*.py
twin_plugin/         sitecustomize + hook, gated by RLINF_TWIN_MODE (root level, like stage15_plugin/)
```

Import the two repo functions by file path rather than `import rlinf...`, so the twin does not drag in the runtime's package init.

### Milestones

| # | Work | Where | Needs | Acceptance |
|---|---|---|---|---|
| T0 | Package skeleton, `mujoco` install, headless render | local | nothing | Off-screen 192x320 render works; time per frame recorded |
| T1 | UR5 MJCF from the DH constants above, TCP site at (0,0,0.18) | local | repo FK values | For 1000 random in-limit joint vectors, MuJoCo TCP pose equals the repo FK (position < 1e-5 m, rotation < 1e-5 rad) against a reference table generated once with the repo function |
| T2 | Action to joint targets: repo conversion, then IK (damped least squares, warm start, limits, branch continuity) | local, then dataset | dataset for the real check | Synthetic: FK(IK(x)) within 1 mm / 0.1 deg. Demos: IK of the converted demo actions versus recorded `observation.state`; report the error distribution and fix conventions before going on |
| T3 | Laptop (base box, lid box, hinge with friction, damping, limit), gripper fingers, scripted close | local | laptop dimensions, gripper geometry (lab) | Scripted path closes the lid; scene settles at rest; **null action leaves the state unchanged** (the null-verdict proposition, Proposition 8 in the compiled proposal); deterministic; stable across the parameter range |
| T4 | Cameras and renderer: intrinsics, extrinsics, textured render, masks | lab data | intrinsics, calibration or robot-silhouette fit | Projected TCP lands near the gripper in demo frames; held-out-frame robot-mask IoU reported |
| T5 | Initialiser over the 40 first frames, cache per episode | GPU machine | SAM 3 weights, dataset | Leave-one-view-out IoU; about 10 hand-labelled frames (lid angle in degrees, position in cm); overlay images for all 40 scenes checked by eye; ambiguous share reported |
| T6 | Demo replay harness (E0): replay real actions in twin and Ctrl-World, compare to the real video through change features, per phase | GPU machine | data, V-JEPA | Runs on the 8 held-out episodes and produces the phase map |
| T7 | Integration: `TwinSession` per env, `twin_plugin`, logging, weight field to the actor | cluster | T1-T6 | Smoke profile (`close_smoke_2n4g.yaml`) with the plugin in log-only mode reproduces baseline advantages exactly (w=1) and logs twin outputs |
| T8 | Trust-weighting unit tests on the synthetic engine | local | nothing | w=1 equals both advantage functions; a zero-weight reward adds exactly zero; both D1 variants implemented |

T1, T2 (synthetic part), T3 and T8 need no lab data and no GPU and can start now.

### Timeline against the proposal (5 Nov - 2 Dec for the twin)

- Week of 16 Nov: T0, T1, T2 synthetic, T8; send the lab requests on Monday.
- Week of 23 Nov: T3, then T4/T5 as soon as the lab data arrives.
- 30 Nov - 2 Dec: T5 finished, T6 started. T7 will spill into the calibration block (3 - 16 Dec).
- This is tight. The critical path is the lab data (section 5), not the code. If it arrives after about 20 Nov, T5 moves past 2 Dec. These durations are my estimates.

### Compute budget to measure in T0 and T7

Renders per rank per update = trajectories per rank x |Theta| x chunks x views x frames = 16 x 16 x 5 x 3 x 32, which is about 1.2e5 at |Theta|=16 and 32 frames (4 envs per rank x 4 rollout epochs; 8 CPU cores per rank if the 32 CPUs per node are shared by 4 ranks). Cheap reductions: subsample frames, use |Theta| of 8, render at lower resolution. Check that EGL and the aarch64 wheels (mujoco, SAM 3) work on the GH200 nodes **(check)**.

---

## 5. Requests to the lab (critical path)

1. Output of the dataset check: `meta/info.json` (features, fps), the keys and dimensions of one episode (`observation.state`, `action`), episode lengths, and any camera-parameter files.
2. Camera intrinsics for the three RealSense cameras at the recorded resolution (e.g. `rs-enumerate-devices -c`); whether the fixed cameras moved between sessions; any extrinsic or hand-eye calibration; how the wrist camera is mounted.
3. Laptop measurements with a ruler (base width x depth x height, lid thickness and height, hinge position, maximum opening angle) plus a photo; confirm it is the same laptop in all 40 demos.
4. Gripper model and finger geometry; how the lid is closed in the demos (closed fingers pushing the lid edge, or something else).
5. Robot: confirm UR5 (not UR5e), the 0.18 m TCP offset, controller type, control rate and latency.
6. Which episodes Ctrl-World was fine-tuned on.

---

## 6. Risks specific to the twin

- **Closing contact is the hard part to model.** Gripper geometry and lid friction decide whether the referee is right where it matters; this is what the phase map (Step 5.2) is for.
- **Camera extrinsics** may have to be estimated from robot silhouettes if the lab has no calibration; this needs a good UR5 mesh model (T1).
- **Shared action conversion**: errors in the repo's EEF conversion are invisible to the twin; T2 on real demos is the only guard.
- **CPU rendering throughput** in the loop (see budget); fallback is Phase A (offline audit) plus a coarser in-loop check.
