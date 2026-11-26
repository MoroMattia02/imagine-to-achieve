# Dependencies

Which module imports which, for `src/twin/` and the two trust-weighting files. The graph and the
table between the markers are generated from the code by `scripts/make_code_deps.py`, and
`tests/test_docs.py` fails when they are stale: after changing an import, run
`python scripts/make_code_deps.py`.

An arrow A → B means "A imports from B". Dotted arrows are lazy imports (inside a function);
dashed boxes are heavy external libraries or a file loaded by path. numpy is named inside the box
of each module that uses it; the standard library is left out.

<!-- BEGIN GENERATED -->
<!-- Written by scripts/make_code_deps.py; do not edit by hand, rerun the script. -->

```mermaid
flowchart TD
    subgraph twin["src/twin/"]
        twin_actions["actions.py<br/>uses numpy"]
        twin_cameras["cameras.py<br/>uses numpy"]
        twin_compare["compare.py<br/>uses numpy"]
        twin_conformal["conformal.py<br/>uses numpy"]
        twin_ik["ik.py<br/>uses numpy"]
        twin_init_fit["init_fit.py<br/>uses numpy"]
        twin_render["render.py<br/>uses numpy"]
        twin_repo_import["repo_import.py"]
        twin_robot["robot.py<br/>uses numpy"]
        twin_scene["scene.py<br/>uses numpy"]
        twin_session["session.py<br/>uses numpy"]
        twin_transforms["transforms.py<br/>uses numpy"]
        twin_verdict["verdict.py<br/>uses numpy"]
    end
    subgraph rlinf_modified_algorithms["src/rlinf_modified/algorithms/"]
        rlinf_modified_algorithms_advantages["advantages.py"]
        rlinf_modified_algorithms_trust["trust.py"]
    end
    ext_mujoco["mujoco"]:::external
    ext_third_party_rlinf_runtime_rlinf_envs_world_model_eef_pose_adapter_py["eef_pose_adapter.py<br/>loaded by path"]:::external
    ext_torch["torch"]:::external
    rlinf_modified_algorithms_advantages --> rlinf_modified_algorithms_trust
    rlinf_modified_algorithms_advantages --> ext_torch
    rlinf_modified_algorithms_trust --> ext_torch
    twin_actions -.->|lazy| ext_torch
    twin_actions --> twin_ik
    twin_actions --> twin_repo_import
    twin_actions --> twin_transforms
    twin_compare --> twin_cameras
    twin_ik --> twin_robot
    twin_ik --> twin_transforms
    twin_init_fit --> twin_scene
    twin_render -.->|lazy| ext_mujoco
    twin_repo_import -.->|by path, lazy| ext_third_party_rlinf_runtime_rlinf_envs_world_model_eef_pose_adapter_py
    twin_robot -.->|lazy| ext_mujoco
    twin_session --> twin_actions
    twin_session --> twin_scene
    classDef external stroke-dasharray: 5 5
```

| Module | Imports from | Names | When |
|---|---|---|---|
| `rlinf_modified.algorithms.advantages` | `rlinf_modified.algorithms.trust` | `STD_SOURCES`, `StdSource`, `trust_weighted_suffix_advantages` | at import |
| `rlinf_modified.algorithms.advantages` | `torch` | the module | at import |
| `rlinf_modified.algorithms.trust` | `torch` | the module | at import |
| `twin.actions` | `torch` | the module | lazy, in `_repo_rot6d_to_matrix`, `actions_to_eef_targets` |
| `twin.actions` | `twin.ik` | `DEFAULT_IK`, `IKConfig`, `PathIKResult`, `UR5_MAX_JOINT_SPEED`, `track_path` | at import |
| `twin.actions` | `twin.repo_import` | `load_eef_pose_adapter` | at import |
| `twin.actions` | `twin.transforms` | `geodesic_angle`, `invert_T`, `make_T`, `rotvec_to_matrix` | at import |
| `twin.compare` | `twin.cameras` | `PHYSICAL_CAMERAS` | at import |
| `twin.ik` | `twin.robot` | `JOINT_LIMITS`, `TCP_OFFSET`, `UR5_DH`, `dh_transform`, `fk` | at import |
| `twin.ik` | `twin.transforms` | `geodesic_angle`, `invert_T`, `make_T`, `so3_log` | at import |
| `twin.init_fit` | `twin.scene` | `SceneState` | at import |
| `twin.render` | `mujoco` | the module | lazy, in `TwinRenderer.__init__` |
| `twin.repo_import` | `third_party/rlinf_runtime/rlinf/envs/world_model/eef_pose_adapter.py` | the whole file, with `importlib` | lazy, in `load_eef_pose_adapter` |
| `twin.robot` | `mujoco` | the module | lazy, in `load_ur5_model` |
| `twin.session` | `twin.actions` | `ActionsToJoints`, `JointChunk` | at import |
| `twin.session` | `twin.scene` | `ChunkRollout`, `LaptopScene`, `SceneState` | at import |

<!-- END GENERATED -->

## How to read it

- **No import cycles.** Every module imports only from modules that do not import it back
  (`tests/test_docs.py` checks this on the generated graph).
- **Base modules have no internal imports.** `transforms.py` and `robot.py` need only numpy,
  `repo_import.py` only the standard library. `scene.py` and `cameras.py` are skeletons that so far
  mostly define data classes. `verdict.py` and `conformal.py` are numpy only.
- **`ik.py` depends on the robot model**, because IK is FK run backwards and must use exactly the
  same DH table.
- **`actions.py` is the hub of T2.** It is the only module that touches the repo's conversion code
  (through `repo_import.py`), and it hands its result to `ik.py`.
- **`session.py` is the top:** it combines the kinematics (`actions.py`) and the physics
  (`scene.py`) for one environment.
- **The referee maths of Phase 1 stands apart.** `compare.py` imports only the camera names from
  `cameras.py`; `verdict.py` and `conformal.py` import nothing from the package. They are pure
  functions on arrays: they run without the scene, MuJoCo or torch, and nothing calls them yet
  (the plugin will, WP 5.1).
- **Heavy libraries are imported lazily.** `torch` is imported inside `actions_to_eef_targets`
  and `_repo_rot6d_to_matrix` (and needed by the repo file); `mujoco` inside `load_ur5_model` and
  `TwinRenderer.__init__`. So `import twin.ik` works on a machine without torch or MuJoCo, and the
  numpy-only tests run anywhere. `trust.py` and `advantages.py` are torch code and import it at the
  top.

!!! note "Lazy import"
    An `import` written inside a function instead of at the top of the file. It runs only when
    the function is first called. Here it keeps optional, heavy dependencies (torch, MuJoCo, an
    OpenGL context) out of modules that do not always need them.

## Trust weighting and production

The trust-weighting code lives in `src/rlinf_modified/algorithms/`, because it is about the RL
update, not the scene. `trust.py` stands alone; `advantages.py` calls it when `weights` is given;
the plugin (planned) will call it in production, where the tests already show that it equals the
vendored function bit for bit at full trust.

```mermaid
flowchart LR
    adv["advantages.py<br/>synthetic engine"] -->|imports| tw["trust.py<br/>torch only"]
    tst["tests/test_trust_weighting.py"] --> adv
    tst --> tw
    pl["twin_plugin/<br/>WP 5.1, planned"]:::planned -.-> tw
    pl -.->|replaces its advantage call| cr["cross_rank_grpo.py<br/>vendored, production"]:::planned
    tw -.-|equal at w = 1, tested| cr
    classDef planned stroke-dasharray: 5 5
```

## Where the next work packages plug in

The roadmap's next modules fit into the graph at fixed places (dashed: not in the repo yet).
Building them there keeps the layering: no cycles, heavy imports lazy, the Phase 1 maths free of
scene imports.

```mermaid
flowchart TD
    pl["twin_plugin/<br/>WP 5.1-5.2: hooks, arms, dump"]:::planned
    pr["probes.py<br/>WP 2.2"]:::planned
    ft["features.py<br/>WP 4.2, V-JEPA 2"]:::planned
    se["session.py<br/>with Θ (T7)"]
    fit["init_fit.py<br/>WP 3.2"]
    tc["task_config.py<br/>WP 3.2"]:::planned
    kin["actions.py<br/>(+ ik, robot, transforms)"]
    sc["scene.py<br/>filled in WP 2.3"]
    rd["render.py, cameras.py<br/>MJCF cameras, masks: WP 3.1"]
    subgraph pure["pure functions on arrays (no scene imports)"]
        cmp["compare.py"]
        ver["verdict.py"]
        con["conformal.py"]
        tw["trust.py"]
    end
    pl -.-> se
    pl -.-> pr
    pl -.-> ft
    pl -.-> fit
    pl -.-> pure
    pr -.-> kin
    pr -.-> sc
    se --> kin
    se --> sc
    se -.-> rd
    fit --> sc
    fit -.-> rd
    fit -.-> tc
    classDef planned stroke-dasharray: 5 5
```

| Module | WP | Proposal step and role | Now |
|---|---|---|---|
| `compare.py` | 1.3 | Step 4: change features, D̃, grounded score S and spread κ (on feature arrays) | implemented |
| `verdict.py` | 1.4 | Steps 6.3-6.4: twin decision, Ctrl-World significance, verdict table, p_{i,0} | implemented |
| `conformal.py` | 1.5 | Step 7: conformal threshold, divergence chunk, g_{i,k}; Step 5 calibration rules | implemented |
| `probes.py` | 2.2 | Step 6.2: probe generator and null action, feasibility through `ActionsToJoints` | planned |
| `scene.py` (filled) | 2.3 | Steps 1, 3: laptop physics (T3) | skeleton |
| `cameras.py`, `render.py` (masks) | 3.1 | Steps 1, 3: MJCF cameras, segmentation masks (T4) | skeleton |
| `task_config.py`, `init_fit.py` | 3.2 | Step 2: per-task configuration, render-and-compare fit (T5) | planned, skeleton |
| `features.py` | 4.2 | Step 4: V-JEPA 2 window features φ_t | planned |
| `twin_plugin/` | 5.1-5.2 | integration hooks, arm modes, rollout dump | planned |
