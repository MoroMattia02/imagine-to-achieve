# Call flows

What happens when the code runs. Boxes are functions; an arrow means "calls"; the second line of
a box gives the data passed, with shapes for one chunk. Dashed boxes are not implemented yet.

## One chunk through the twin (today: kinematics only)

The path every chunk will take in training. It is what `TwinSession.step_chunk` runs today; once
T3 exists, the dashed call adds the physics.

```mermaid
flowchart TD
    ss["TwinSession.step_chunk(actions)<br/>actions (32, 10); stored eef_state (7,) and q (6,)<br/>→ ChunkResult; keeps next_state and q[-1] for the next chunk"]
    a2j["ActionsToJoints.step_chunk(state, actions, q)<br/>→ JointChunk: q (64, 6), gripper (64,), eef, action_check, ik, next_state (7,)"]
    chk["check_actions(actions)<br/>→ ActionReport; raises on hard errors"]
    e2t["actions_to_eef_targets(state, actions)<br/>torch, float32, autocast off<br/>→ EEFTargets: ctrl_states (1, 64, 7), ctrl_condition, next_state"]
    ld["load_eef_pose_adapter()<br/>loads the repo file once (cached)"]
    r1["repo.analytic_ur5_rot6d_delta_actions_to_eef_states<br/>chains the 32 deltas: (32, 7)"]
    r2["repo.state_to_ctrl_world_eef_state<br/>the current state in Ctrl-World's format"]
    clip["gripper clip to [q01, q99]<br/>inline, when the statistics are set"]
    r3["repo.resample_eef_state_sequence_by_fps<br/>15 → 30 Hz: 64 states"]
    st["eef_state_to_T(ctrl_states[0])<br/>T_WE (64, 4, 4), then T_BE = T_WB⁻¹ T_WE"]
    tp["track_path(T_BE, q, dt=1/30)"]
    dls["ik_dls(T_BE[i], q_prev)<br/>64 times, each seeded with the previous solution"]
    inner["fk · pose_error (so3_log) · jacobian (joint_frames) · SVD"]
    br["branch_of(q_i)<br/>flags: converged, at limit, speed, branch switch, σ_min"]
    sc["scene.step_chunk(q, gripper)<br/>only if a scene is attached (T3, skeleton)"]:::planned
    ss --> a2j
    a2j --> chk
    a2j --> e2t
    e2t --> ld
    e2t --> r1
    e2t --> r2
    e2t --> clip
    e2t --> r3
    a2j --> st
    a2j --> tp
    tp --> dls
    dls --> inner
    tp --> br
    ss -.-> sc
    classDef planned stroke-dasharray: 5 5
```

`repo.*` are the repo's own functions in `eef_pose_adapter.py`, loaded by path. Two design points
are visible in the call tree:

- **The repo functions are called, not re-implemented.** `actions_to_eef_targets` goes through
  the same three functions as `CtrlWorldEnv._convert_via_analytic_ur5_rot6d` in production, in
  float32, so the twin's 64 targets equal Ctrl-World's conditioning bit for bit.
- **The two pieces of state are chained.** The EEF state for the next chunk is the repo's
  `next_state` (open loop, like Ctrl-World); the IK seed for the next chunk is the last solved
  joint vector. So the arm follows exactly the commanded path; if it cannot, the IK flags say so.

## Model generation, rendering and the viewer

**(a) Generate the model.** The robot model is generated and checked; it is never hand-edited.

```mermaid
flowchart LR
    mk["make_twin_ur5_mjcf.main()"] --> gen["robot.ur5_mjcf_xml()"] --> xml[("src/twin/assets/ur5.xml")]
    tst["test: file == generator output"] -.-> xml
```

**(b) Load and render.** The renderer reads `data` and never changes it.

```mermaid
flowchart LR
    load["robot.load_ur5_model()"] --> mod["mujoco.MjModel.from_xml_string"]
    mod --> dat["mujoco.MjData(model)<br/>set qpos, mj_forward"]
    dat --> rr["TwinRenderer(model).render(data, cam)<br/>(192, 320, 3) uint8"]
```

**(c) The viewer** plays a joint path, from a file or from synthetic chunks run through the twin
(the call tree above).

```mermaid
flowchart LR
    vm["twin_view.main()"] --> lt["load_trajectory(path)<br/>--replay"]
    vm --> dc["demo_chunk_trajectory(n)<br/>--demo-chunk: TwinSession"]
    lt --> pl["play(q, fps, loop)<br/>load_ur5_model, launch_passive<br/>per frame: qpos = q[i], mj_forward, sync"]
    dc --> pl
```

!!! note "Passive viewer"
    `mujoco.viewer.launch_passive(model, data)` opens a window that *shows* `data` but does not
    step the simulation itself. The script sets `qpos` to the next frame of the path, calls
    `mj_forward` (pose update, no physics), and `viewer.sync()` redraws. It is a kinematic replay,
    which is what is needed to check IK paths.

## Trust-weighted advantages

In production the plugin will call `trust_weighted_suffix_advantages` directly, with the
cross-rank group ids (WP 5.1).

```mermaid
flowchart TD
    g["grpo_action_suffix_advantages(..., weights, std_source)<br/>advantages.py; with weights=None the original lines run unchanged"]
    t["trust_weighted_suffix_advantages(r, w, dones, mask, group_index, ...)<br/>→ advantages (float32) × loss mask, and TrustStats"]
    cw["_check_weights → group_members(group_index)<br/>members [groups, G]"]
    im["_impute(r, w, members)<br/>eq. (20): r̂ = w r + (1 − w) m_k, m_k = Σ w r / Σ w"]
    s1["suffix_returns(r̂, dones, γ)<br/>R̂ [T, N]"]
    s2["suffix_returns(r, dones, γ)<br/>R [T, N], for option B and the statistics"]
    no["_normalise(R̂, R, members, std_source, ε)<br/>(R̂ − mean) / (s + ε), s from R̂ (A) or R (B)"]
    g -->|weights given| t
    t --> cw
    t --> im
    t --> s1
    t --> s2
    t --> no
```

Two implementation details explain the tests. `group_members` gathers each group into a
[T, groups, G] layout that is exactly the reshape the old function used, which is what makes the
w ≡ 1 result *bit*-identical, not just close. And all members enter the mean and std whatever
their loss mask, as in both existing functions; the mask only multiplies the output.

## The referee maths: how the Phase 1 outputs feed each other

The functions of `compare.py`, `verdict.py` and `conformal.py` are tested one by one; nothing
calls them in sequence yet (the plugin will, WP 5.1; an end-to-end test is gap G1 in
`open_items_and_deviations.md`). This is the intended data flow per candidate i, not a call tree.

```mermaid
flowchart TD
    phi["per-view window features φ_t, φ_ref<br/>features.py, WP 4.2"]:::planned
    cf["compare.change_features (per view)<br/>→ compare.average_views"]
    gs["compare.grounded_scores<br/>→ S_k, κ_k for chunk k"]
    demo["calibration demonstrations (Step 5)"]:::planned
    cal["conformal.split_fit_calibration → conformal.calibrate<br/>→ m_k (fitting half), q_α (calibration half)"]
    ks["conformal.divergence_chunk (calls abstains)<br/>→ k* or None"]
    g["conformal.grounded_weights<br/>→ g_k"]
    probes["chunk-0 probe scores of the twin and of Ctrl-World<br/>probes.py WP 2.2, re-runs WP 4.1"]:::planned
    vd["verdict.twin_decision · common_seed_effect · pooled_sigma<br/>· significance · verdict · combine_probes"]
    pw["verdict.probe_weight<br/>→ p_0"]
    w["conformal.combined_weights<br/>→ w_k = p_k g_k"]
    adv["trust.trust_weighted_suffix_advantages"]
    phi --> cf --> gs --> ks
    demo --> cal --> ks
    ks --> g --> w
    probes --> vd --> pw --> w
    w --> adv
    classDef planned stroke-dasharray: 5 5
```

## The FK reference fixture

`make_twin_fk_reference.main()` calls `load_eef_pose_adapter()` and the repo's
`ur5_joint_actions_to_eef_states` in float64 on 1000 random joint vectors (seed 0), and writes the
inputs and outputs with metadata (source hash, commit) to
`tests/fixtures/twin_fk_reference_ur5.json`. `test_twin_fk.py` compares `robot.fk` with it; a
staleness test regenerates the table when torch is available and fails if the repo function
changed.

## Integration with the training code (planned, WP 5.1)

The vendored runtime in `third_party/` is not edited. The twin will follow the repo's plugin
pattern, `stage15_plugin/`: a `sitecustomize.py` that Python imports at start-up when its folder
is on `PYTHONPATH` (`stage15_plugin/launch_ray_node.sh`, line 89, prepends it on every Ray node).
It does nothing unless an environment variable is set; then it replaces selected runtime
functions (monkeypatching) and fails loudly if that does not work. For the twin:
`twin_plugin/sitecustomize.py`, gated by `RLINF_TWIN_MODE` ∈ {`off`, `log`, `weight`}, and
`RLINF_TWIN_ARM` selecting the training arm (T, T0, TG, S).

```mermaid
sequenceDiagram
    participant P as Policy (Cosmos)
    participant E as Env (CtrlWorldEnv)
    participant T as Twin plugin + TwinSession
    participant W as Env worker
    participant A as Actor (FSDP)
    E->>T: 1. reset (l. 2050), episode ids
    Note over T: load scene_cache, build Θ
    P->>E: 2. actions (B, 32, 10)
    E->>T: 3. wrapped chunk_step (l. 3155), after Ctrl-World
    Note over T: T2 once, then physics and render for every ϑ
    T->>E: 4. chunk-0 probes: get_state, re-run, load_state
    E->>W: 5. infos: ctrl_world_video_chunk* (env worker l. 1263-1272)
    T->>W: 6. features, verdicts, weights w_ik
    Note over W: attach trust_weight next to the rewards (l. 1404)
    W->>A: 7. rollout batch: rewards and weights
    Note over A: all-gather scalars (l. 1850, 1895-1896), trust-weighted advantages replace the call at l. 1917, then FPO
```

Line numbers are those of the current commit (`third_party/` is unchanged since `f4f669e`;
re-checked 26 Nov 2026). Files: env = `third_party/rlinf_runtime/rlinf/envs/world_model/world_model_ctrl_world_env.py`,
env worker = `.../rlinf/workers/env/env_worker.py`, actor = `.../rlinf/workers/actor/fsdp_actor_worker.py`.

1. **Reset** (`CtrlWorldEnv.reset`, line 2050) knows which episode each environment starts from
   (`episode_indices`). The plugin wraps it to reset the matching `TwinSession` from the cache.
2. **Every chunk** (`CtrlWorldEnv.chunk_step`, line 3155) receives the policy's actions
   `[B, chunk, action_dim]` and runs Ctrl-World through `_infer_next_chunk_frames` (line 2747).
   The wrapper calls the original, then steps the twins with the same actions. The subclass
   `CosmosSelfFeedbackCtrlWorldEnv` (line 3589) calls `super().chunk_step` in its own `chunk_step`
   (lines 3696 and 3702), so wrapping the base method covers it (read, not run: check).
3. **Probes at chunk 0** need Ctrl-World to predict again from the same state with another action
   and chosen seeds: `get_state()` (line 3444) serialises the env, including the noise generator
   state; `load_state()` (line 3508) restores it. Whether this restore is exact is assumption M4,
   tested first (WP 4.1).
4. **Ctrl-World's video** leaves the env in `infos` under `ctrl_world_video_chunk`, `_wrist`,
   `_extra` (read in `env_worker.py`, lines 1263-1272; these three keys at 1267-1269). This is
   where the comparison gets V^W.
5. **Weights** travel with the rewards. The actor gathers only *scalar* per-step records across
   ranks (`_compute_cross_rank_grpo_advantages`, line 1716; `all_gather` at lines 1850 and
   1895-1896), because a group of 16 is spread over 4 ranks. The weight becomes one more scalar
   column of that gather, and the trust-weighted function (WP 1.2) replaces the call to
   `validate_and_compute_group_suffix_advantages` (`rlinf/algorithms/cross_rank_grpo.py`,
   line 801; called at line 1917).

**First mode: log only.** In `log` mode the plugin computes everything and logs verdicts, scores,
spreads and weights, but forces w ≡ 1. Its acceptance test is that the advantages are
bit-identical to the baseline. This is also arm A of the proposal (E1, E2): the audit runs on the
original method.
