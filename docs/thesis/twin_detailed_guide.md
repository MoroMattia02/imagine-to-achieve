# Scene digital twin: detailed guide (practice, theory, reasons)

Companion to `docs/thesis/twin_implementation_plan.md`. That file says **what** to build and **where** it hooks into the code (milestones T0 to T8). This one says **how to build each part, why it is built that way, and how to know it is right**. Short thesis summary: `docs/thesis/thesis_context.md`.

Legend:
- **(check)** = inferred or not verified. Nothing in the repo was executed (no torch or mujoco in my workspace), so every statement about the repo comes from reading commit `0d325b1`.
- **[cite]** = reference written from memory. Verify authors, year and venue before it goes into the thesis.
- Each part has the same order: *practical steps*, *theory*, *why this choice*, *tests*, *pitfalls*.

---

## 0. The twin on one page

**What it is.** A small MuJoCo model of the lab scene (UR5 arm, gripper, laptop on a table, three cameras) that is driven by the same actions that Ctrl-World receives, and renders what a physical world would show.

**What it is for.** In the thesis the policy is trained on rewards computed from Ctrl-World's imagined video. The twin is a second, independent opinion produced by a different mechanism (rigid-body physics with contact instead of a learned video prior). Where the two disagree in a way that physics cannot explain by uncertainty in its own parameters, the reward from that chunk is treated as untrustworthy.

**What it can claim.** "This imagined outcome is inconsistent with every physical scene I consider plausible", or "this imagined outcome is consistent with some plausible scene". It cannot claim "this is what the real world would do". The twin is a model; its agreement with reality has to be measured (section 11), not assumed.

**Why a simple twin is enough.** The task is one object type (a laptop with a hinge), one robot, one skill (closing the lid). The referee only needs to catch gross physical impossibilities (the lid closes without being touched, the lid passes through the gripper, the arm moves differently from the commanded path, nothing happens when the gripper pushes). That needs correct kinematics, a plausible hinge and contact model, and cameras that are roughly right. It does not need photorealism or exact friction.

**Order of dependence.**

```
frames/conventions (1) -> robot FK (2) -> actions to joint path (3) -> physics (4)
                                   \-> cameras (5) -> rendering (6) -> initialiser (7)
physics + initialiser + demos -> parameter belief and calibration (8)
twin render vs Ctrl-World video -> feature comparison (9) -> trust weights (10)
everything -> validation (11)
```

Sections 2, 3 (synthetic part), 4 and 10 (the weighting tests) need no lab data and no GPU. Start there.

---

## 1. Frames and conventions (read once, keep open)

Most twin bugs will be convention bugs, so write the conventions down before any code.

**Notation.** `T_AB` is the 4x4 matrix `[R p; 0 1]` that maps coordinates expressed in frame B into frame A. Chaining: `T_AC = T_AB · T_BC`. Inverse: `T_BA = T_AB^-1`.

**Frames.**

| Frame | Meaning | Where it comes from |
|---|---|---|
| W | frame in which the recorded EEF poses are expressed | dataset (not documented in the repo) |
| B | robot base frame (UR base link) | UR convention |
| E | end-effector (TCP, 0.18 m along z from the flange in the repo FK) | repo FK |
| C_v | camera v (main = `d435_rgb`, wrist = `d405_0_rgb`, extra = `d405_1_rgb`) | calibration (section 5) |
| L | laptop base frame; lid frame is L rotated about the hinge by θ | twin |

**What the repo uses (verified by reading).**

- State vector (Ctrl-World side): `[x, y, z, rx, ry, rz, gripper]`. `rx,ry,rz` is an **axis-angle rotation vector**. When the cached state has 8 values the gripper is the mean of the absolute values of channels 6 and 7 (`state_to_ctrl_world_eef_state`, `eef_pose_adapter.py:306`).
- Action (policy side), 10-D: `[pos_delta(3), rot6d_delta(6), gripper_abs(1)]`.
- Chaining (`analytic_ur5_rot6d_delta_actions_to_eef_states`, line 681): `p_{i+1} = p_i + R_i · pos_delta · gain` and `R_{i+1} = R_i · R_delta`, i.e. `T_{i+1} = T_i · ΔT` with the delta expressed in the **current EEF (body) frame**. The close config sets `adapter_translation_gain: 1.0` and `adapter_rotation_gain: 1.0` (function default 0.15, overridden in `ctrl_world_close_laptop_grpo_cosmos_native_unipc_large.yaml`). Gripper is an absolute value passed through, not a delta.
- rot6d is the first two **columns** of the rotation matrix; the third column is their cross product; the result is projected to SO(3) with an SVD and a determinant fix (`_rot6d_to_matrix`, line 648).
- Gripper clamp: `adapter_gripper_hard_clamp: true` with `adapter_gripper_hard_mode: clip_only` clips the absolute gripper value between the q01 and q99 of the action statistics.
- Time: policy chunk = 32 actions at 15 Hz; Ctrl-World runs at 30 Hz (`action_fps_resample: true`), so a chunk becomes 64 conditioning states. Resampling is **linear in state space**, including the axis-angle channels (`_maybe_resample_adapter_states`; check the exact interpolation before reusing).
- Conditioning alignment: Ctrl-World gets `[s_t, ..., s_{t+H-1}]`, the current state plus all but the last predicted state, and the last state seeds the next call (`_align_adapter_states_for_ctrl_world`).
- `compute_eef_rigid_alignment` (line 495) returns `T_target_from_source` that maps a **base-frame FK pose to the recorded EEF pose** for the same instant. So the repo already treats "recorded poses live in a frame W that differs from the robot base B by a fixed rigid transform". The twin needs the same transform (call it `T_WB`).

**Rules for the twin code.**

1. Store rotations as matrices or quaternions internally; convert to axis-angle only at the boundary where the repo's state vector is read or written.
2. Never convert rot6d yourself: **import the repo function by file path** (as the plan says), so twin and Ctrl-World see identical EEF targets.
3. Put every transform in one place with names like `T_WB`, `T_BE`, `T_WC_main`, and unit tests that compose and invert them.

**Why this matters.** Axis-angle has a branch problem near θ = π (a rotation by r and by r − 2π·r/|r| is the same rotation); the repo has `_match_axis_angle_branch` for that. If the twin compares against Ctrl-World's numbers through axis-angle it will report false jumps. Compare rotations by the geodesic angle `arccos((tr(R_a^T R_b) − 1)/2)` instead.

---

## 2. Robot kinematics (milestone T1)

### Practical steps

1. Write a **pure-numpy forward kinematics** function from the standard UR5 DH constants in the repo (`ur5_joint_actions_to_eef_states`, `eef_pose_adapter.py:434`): d1 = 0.089159, a2 = −0.425, a3 = −0.39225, d4 = 0.10915, d5 = 0.09465, d6 = 0.0823, and a TCP offset of 0.18 m along the last z axis. The twist angles in the usual UR5 convention are (π/2, 0, 0, π/2, −π/2, 0) **(check against the repo function)**.
2. Generate a **reference table** once: 1000 random joint vectors inside the joint limits, and the repo FK output for each. Save it as a test fixture. (This is the only time you need the repo's torch function; afterwards the numpy version tests against the table.)
3. Generate the **MuJoCo XML programmatically from the DH numbers** (a script, not a hand-edited file), with a site `tcp` at the TCP offset. Meshes for rendering come from a UR5 mesh set (the ROS-Industrial `universal_robot` package has UR5 meshes **(check)**; the MuJoCo Menagerie has a UR5e, which differs in link constants **(check)**, so use it for appearance only, never for kinematics).
4. Test: MuJoCo `site_xpos`/`site_xmat` of `tcp` equals the table for all 1000 joint vectors. Acceptance: position < 1e-5 m, rotation < 1e-5 rad.

### Theory

A serial arm is a chain of rigid transforms, `T_BE(q) = T_01(q1) T_12(q2) ... T_56(q6) · T_tcp`. In the standard Denavit–Hartenberg convention each joint contributes `T_{i-1,i} = Rz(θ_i) · Tz(d_i) · Tx(a_i) · Rx(α_i)` and rotates about the **previous frame's z axis** [cite: Denavit & Hartenberg 1955; Siciliano et al., *Robotics: Modelling, Planning and Control*, 2009].

SO(3) is the set of 3x3 matrices with `R^T R = I` and `det R = +1`. A rotation by angle θ about unit axis n is given by Rodrigues' formula `R = I + sin θ [n]x + (1 − cos θ) [n]x^2`. This is the map between axis-angle and matrices the repo uses.

### Why this choice

- **Why DH from scratch rather than loading a ready URDF.** The repo's own FK is the ground truth that Ctrl-World's conditioning came from. If the twin disagrees with it by even a few mm the twin is not comparing the same robot. A script that builds the kinematic tree from the same constants makes the parity test meaningful.
- **Why numpy first.** The parity test then runs anywhere (laptop, CI) without torch or MuJoCo, and also guards the later MuJoCo model.
- **UR5 versus UR5e.** The repo constants are those of the original UR5. If the real robot is a UR5e (the proposal text says so) the numbers differ by centimetres at the wrist. This is request 5 to the lab; until answered, follow the repo.

### Pitfall specific to MuJoCo

In DH the joint axis is the z axis of the *previous* frame, while MuJoCo defines a hinge in the *child body's* frame. When you write the XML you have to express that axis and its position in the child frame (`joint pos` and `axis`), or place each body's frame on its own joint axis (the "modified DH" or Menagerie style). Either is fine; **the T1 parity test is what tells you that you got it right**, so do not skip it.

### Tests and acceptance

- T1 parity (above).
- Zero-configuration sanity: at q = 0 the TCP pose matches a hand computation.
- Joint limits and wrapping: a joint at 2π − ε and at −ε must give the same pose.

---

## 3. From actions to a robot trajectory (milestone T2)

### Practical steps

1. **EEF path.** Reuse the repo's chain for one chunk: starting EEF state (7-D, axis-angle) and a `[B,H,10]` action array in, a `[B,H,7]` absolute EEF sequence out. Then resample 15 Hz to 30 Hz the same way the env does, so that the twin follows exactly the conditioning states Ctrl-World received.
2. **Frame alignment.** If the recorded EEF poses are in W and the robot model is in B, apply `T_BW = T_WB^-1` to each target. Estimate `T_WB` once from demos (section 8) or take it from the lab.
3. **Inverse kinematics (IK).** Convert each target pose to joint angles by **damped least squares with warm start**: start from the previous frame's `q`, and iterate `Δq = J^T (J J^T + λ² I)^-1 e` until the pose error `e` is below 1e-4 (position in m, rotation in rad). `e` stacks the position error and the rotation error given by the log map of `R_target R_cur^T`. Use MuJoCo's `mj_jacSite` for `J`. Clamp to joint limits. Start with λ around 0.01 to 0.05 and tune on the demos.
4. **Initial joint state.** If the dataset's `observation.state` contains joints, use them. If it only has the EEF pose, solve IK for frame 0 and choose among the up-to-eight UR5 configurations by closeness to the usual "elbow up, wrist down" home pose (check with the lab).
5. **Gripper.** Map the absolute gripper scalar (clipped between q01 and q99) to finger opening with a linear map fixed by the two end values. The finger geometry is request 4.
6. **Controller model.** Start with ideal tracking: joint position actuators with high gain driving the IK targets, 16 physics substeps per 30 Hz frame (`opt.timestep = 1/480`). Add a first-order lag only if the demo replays show one (section 8).

### Theory

- **Differential kinematics.** The end-effector twist is linear in joint velocities, `v = J(q) q̇`. Inverting it numerically with a damped pseudo-inverse is the classical way to avoid blow-up near singularities: damping λ trades tracking accuracy against joint-velocity size [cite: Nakamura & Hanafusa 1986; Wampler 1986].
- **UR arms have closed-form IK** with up to eight solutions (shoulder left/right, elbow up/down, wrist flipped) [cite: Hawkins 2013, "Analytic inverse kinematics for the Universal Robots UR-5/UR-10 arms"]. The numerical solver above stays on one branch because it starts from the previous solution; that is what you want for a continuous motion.
- **Open-loop chaining.** Because each delta is expressed in the current EEF frame (`T_{i+1} = T_i ΔT`), the absolute path is the product of the deltas. Errors do not get corrected, but the twin follows the same chained path as Ctrl-World, so any drift is common to both and cancels in the comparison. What the twin adds is whether that path is **reachable** (IK converges inside the limits) and what it **does to the scene**.

### Why this choice

- **Dynamic arm with position actuators** rather than teleporting joints each step: contact forces then come from a finite-stiffness controller, like a real arm, and the lid is pushed with a bounded force. Setting `qpos` every step gives infinite stiffness and violent contact. (Fallback if the actuator tuning is painful: a mocap-welded fingertip body with a soft weld; it is simpler but the arm links are then only visual.)
- **Reuse of the repo's conversion.** The proposal already notes that errors inside the repo's conversion are invisible to the twin because both share it. The only guard is the demo check below.

### Tests and acceptance

- **Synthetic:** sample random reachable poses, check `FK(IK(x)) = x` within 1 mm and 0.1 degree; check continuity (no joint jumps larger than a threshold along smooth paths).
- **Real, the important one:** for demo episodes, convert the *recorded* actions with the repo chain, run IK, and compare with the recorded `observation.state` of the following frames. Report the error distribution. If it is large the problem is in a convention (gain, frame, rot6d layout, resampling), not in the twin, and it must be fixed before going on.
- **Reachability statistic:** share of chunks of baseline rollouts for which IK fails or hits limits. This is itself a useful diagnostic for the thesis.

### Pitfalls

- Linear interpolation of axis-angle vectors is not a geodesic. Fine for small steps; if the twin interpolates separately, use spherical interpolation and verify that it agrees with the repo within tolerance, or just reuse the repo's resampled states.
- Near θ = π, axis-angle jumps; always compare with the geodesic angle (section 1).
- Joint wrap-around (±2π) breaks IK continuity if you normalise angles.

---

## 4. Physics of the scene (milestone T3)

### Practical steps

1. **Geometry from measurements** (request 3): base box (w × d × h), lid box (thickness, width, height), hinge line position, joint range [0, θ_max]. Until the lab answers, use placeholder dimensions of a 13–15 inch laptop (check) and keep them as parameters.
2. **Bodies and joints:** table (static), laptop base (free joint, so it can slide when pushed), lid (hinge joint about the hinge line), gripper fingers (from the arm model).
3. **Hinge parameters:** `damping` (viscous), `frictionloss` (dry friction), `armature` (small), `range`, soft limit. The lid mass and centre of mass are parameters too.
4. **Contacts:** friction coefficients for finger–lid, lid–base, base–table; contact softness (`solref`, `solimp`); keep default contact margins small.
5. **Scripted closing run:** a hand-written EEF path that pushes the lid shut (e.g. from above onto the lid's free edge). Run it and look at the video.
6. **Null-action test:** hold the arm still from a rest scene for 5 s. Nothing may move.
7. **Determinism:** same inputs, same trajectory, byte for byte; run it twice and compare.

### Theory

- **Dynamics with contact.** MuJoCo integrates `M(q) q̈ + c(q, q̇) = τ + J_c^T f_c`, where contact forces `f_c` come from a convex optimisation that respects friction cones and is **soft** by design: constraints are regularised, so contacts have a finite stiffness and damping controlled by `solref` (a time constant and damping ratio) and `solimp` (how the impedance varies with penetration) [cite: Todorov, "Convex and analytically-invertible dynamics with contacts and constraints", ICRA 2014; Todorov, Erez & Tassa, MuJoCo, IROS 2012; MuJoCo documentation, "Computation" chapter].
- **Friction.** Coulomb friction with a cone `|f_t| ≤ μ f_n` per contact. A geom pair uses the **maximum** of the two geoms' friction coefficients by default **(check)**. There are three friction values per geom: sliding, torsional, rolling.
- **A laptop hinge is friction-dominated.** A real lid stays where you leave it because hinge friction torque exceeds the gravity torque at that angle. In the model that is `frictionloss` (a dry friction torque about the hinge) larger than `m g ℓ sin(θ)` over the working range. This has two consequences: the lid motion is nearly quasi-static (it moves only while something pushes it), and `frictionloss` has a **lower bound** set by "the lid must not fall on its own".

### Why this choice

- **The null-action test is the single most informative physics test**, because the cheapest way for a bad twin to "agree" with a flawed imagined video is to let the lid fall shut by itself. If frictionloss is too small the twin reports success without the robot, and the referee becomes useless exactly where it is needed. It follows that this lower bound goes in the parameter prior (section 8) as a constraint.
- **Free joint for the base:** pushing the lid down presses the base into the table, but a lateral push can slide it; whether it does matters for the final lid angle.
- **No deformable bodies, no screen, no keys.** Not needed for the verdict; each adds parameters you cannot identify from three RGB views.

### Parameters, prior and what they mean (these define ψ)

| Parameter | Role | Prior (starting guess, tune on demos) |
|---|---|---|
| hinge frictionloss | holds lid open; resistance while closing | wide log-uniform, lower bound from "lid stays" |
| hinge damping | speed-dependent resistance | log-uniform |
| lid mass and COM | gravity torque | measured mass if available, else ± 30 % |
| base mass | does it slide | log-uniform |
| μ finger–lid, μ base–table | pushing and sliding | uniform in a plausible range |
| contact `solref`/`solimp` | softness | narrow, mostly a numerical choice |
| controller lag | arm tracking | 0 to 2 frames |

### Tests and acceptance

- Null action: displacement of every body below 1e-6 m after 5 s.
- Scripted close: lid ends within a few degrees of fully closed, base moves less than a set threshold; repeatable.
- **Timestep convergence (verification):** halve `timestep` and the final lid angle changes by less than 0.5 degree.
- **Stability across the prior:** sample 200 ψ from the prior; none yields NaN, explosion or interpenetration deeper than a few mm.

### Pitfalls

- Too-stiff contact with a large timestep can inject energy; keep 16 substeps per 30 Hz frame and check energy.
- Thin boxes (lid) can tunnel through fingers at speed; use sensible geom thickness and the substep count above.
- MuJoCo's friction combination and cone type (pyramidal versus elliptic) change results slightly; fix them and record them in the config **(check which is the default in your MuJoCo version)**.

---

## 5. Cameras (milestone T4)

### Practical steps

1. **Intrinsics** (request 2): `fx, fy, cx, cy` and distortion for each of the three RealSense cameras at the recorded resolution.
2. **Account for the resize.** The loop uses 192 × 320 per view, so the original frames were resized, possibly with a crop or a stretch. Scale the intrinsics accordingly: `fx' = fx · W'/W`, `fy' = fy · H'/H`, and likewise for `cx, cy`; if there was a crop, subtract the crop offset first. Find the exact preprocessing in the dataset wrapper or ask the lab **(check)**.
3. **Extrinsics.**
   - Fixed camera (`d435_rgb`): `T_WC` in the world frame. Best from lab calibration. Otherwise estimate by **robot-based calibration**: render the (known-pose) robot silhouette from a candidate camera pose and maximise overlap with the real robot in several frames with diverse arm configurations; 6 parameters.
   - Wrist cameras: constant `T_EC` from the end-effector (hand-eye calibration). Ask the lab for the mount drawings or a calibration file; else estimate by the same silhouette idea using the fixed gripper parts visible in the wrist views.
4. **Check by projection:** project the TCP into each image for a few demo frames and look at the overlay.

### Theory

- **Pinhole model:** a 3D point `X = (X, Y, Z)` in camera coordinates projects to `u = fx X/Z + cx`, `v = fy Y/Z + cy`, plus a distortion map [cite: Hartley & Zisserman, *Multiple View Geometry*, 2004]. Extrinsics are the rigid transform from the world to the camera.
- **Hand-eye calibration** solves `AX = XB` for the fixed transform between a hand-mounted camera and the end-effector [cite: Tsai & Lenz 1989]. Here the robot itself plays the role of the calibration target.
- **Identifiability:** the camera pose is determined by silhouettes only if the robot pose varies enough across frames (a still arm constrains it poorly along some directions). Use frames from different phases of one or several demos.

### Why this choice

Comparisons are made in **image or feature space** (section 9), so a wrong camera shifts the twin's render and shows up as a persistent disagreement with every video, real or imagined. Calibrating the cameras against *real* frames first removes that source of disagreement, so any remaining disagreement with Ctrl-World is less likely to be a twin artifact.

### Tests and acceptance

- Reprojection of the TCP within a few pixels in demo frames (the gripper centre, not the image corner).
- Robot-mask IoU on **held-out frames** (not used in the extrinsics fit), per camera; record the distribution. This number bounds how much a render of the robot can be trusted.

### Pitfalls

- RealSense colour streams are normally close to undistorted, but verify **(check)**; wrist D405 optics differ from D435.
- If the fixed camera moved between sessions, one calibration is wrong for part of the dataset; request 2 asks exactly this.

---

## 6. Rendering (milestone T4)

### Practical steps

1. Use MuJoCo's off-screen renderer. On a Linux machine with a GPU set `MUJOCO_GL=egl`; on a headless CPU-only machine `osmesa` works but is much slower **(check availability on the aarch64 GH200 nodes)**. On Windows the default backend is used (EGL is a Linux setting).
2. Set camera intrinsics exactly. Newer MuJoCo versions have camera attributes in pixel units (`focalpixel`, `principalpixel`, `resolution`) so you do not have to convert to a vertical field of view **(check the attribute names in the installed version)**.
3. Render three outputs per view: RGB, depth, and a **segmentation map** with ids per object (robot, lid, base, table). Masks come from the id map.
4. **Texture:** start with flat colours. Later, project the first real frame onto the table/laptop to texture them if the feature comparison needs it.
5. Measure the render time per frame early (T0), because the in-loop budget in the plan is dominated by it.

### Theory

Analysis-by-synthesis (render-and-compare) is a standard way to estimate scene parameters from images when no differentiable renderer is used: render under hypothesised parameters, compare to the observation, search. The comparison metric decides what can be identified.

### Why this choice

- **Segmentation masks, not appearance.** Silhouette overlap is almost independent of lighting, texture and colour, which are exactly the things a flat-colour twin gets wrong.
- **The comparison to Ctrl-World uses change features** (section 9): the difference between a frame and the first frame in feature space. A constant appearance gap (colour, texture, lighting) appears in both frames and cancels in the difference, which is why a plain render can be compared with generated video at all.

### Tests

- Same pose, same render (determinism).
- Mask IoU of rendered robot versus real robot on held-out frames (section 5).
- Time per frame at 192 × 320 for 1 and 3 views.

---

## 7. The initialiser: SAM 3 plus render-and-compare (milestone T5)

### What it solves

Given the first frame of an episode (3 views) and the known robot pose, find the scene state `x = (p_x, p_y, yaw, θ_lid)` of the laptop on the table (and optionally scale if the laptop size is not known) that explains the images. This runs **once per episode and is cached**, because there are only 40 start scenes (32 train, 8 eval).

### Practical steps

1. **Masks.** Run SAM 3 (text-prompted concept segmentation, or points/boxes as fallback) on each view for "laptop screen/lid" and "laptop base/keyboard"; save the masks and an overlay image. Check that the weights and licence are available on your machine **(check)**.
2. **Loss.** For a candidate `x`, render the segmentation map, restrict to pixels not covered by the (slightly dilated) rendered robot, and compute `L(x) = Σ_v [ (1 − IoU_lid,v) + (1 − IoU_base,v) ]`.
3. **Stage 1, coarse global search** on half-resolution masks: grid or random sample over `p_x, p_y` (table region), `yaw` (steps of about 15 degrees), `θ` (steps of about 10 degrees). Keep the best 20 candidates.
4. **Stage 2, local refinement:** CMA-ES or Nelder–Mead from each of the best candidates (derivative-free, because mask IoU is not differentiable). Keep the best `x*` and its loss `L*`.
5. **Stage 3, near-optimal set.** Sample around `x*` and keep all `x` with `L(x) ≤ L* + ε`. Cap at |Θ| = 16 by farthest-point selection so the set is diverse. `ε` is the **mask-noise floor**: re-evaluate `L(x*)` after eroding and dilating the SAM masks by 1 to 3 pixels and take a high percentile of the increase.
6. **Cache** `Θ_0 = {x_1..x_16}` as `scene_cache/episode_XXX.json` together with `L*`, `ε` and the overlay images.
7. **Review all 40 overlays by eye** and tag the ambiguous ones.

### Theory

- **Why a set and not a point.** Silhouettes from few views can leave ambiguity: lid angle near edge-on, near-symmetric yaw, depth versus scale along the camera ray. The pipeline therefore carries the set of scenes that fit about equally well, `Θ_0`, and the referee later asks whether the imagined outcome is consistent with *any* of them (the "near-optimal set" of the proposal). A single estimate would hide this uncertainty and turn small fitting errors into systematic false alarms.
- **Why IoU.** Bounded in [0, 1], scale-free, robust to colour; its weakness (flat regions where it does not change) is handled by the global search in stage 1.
- **Occlusion** by the arm is handled by rendering the arm at its known pose and excluding its pixels, rather than learning an occlusion model.

### Tests and acceptance

- Leave-one-view-out: fit with two views, measure IoU on the third.
- **About 10 hand-labelled frames** (lid angle in degrees with a protractor on the image, position in cm): report the error. This is the only ground truth for the initialiser.
- Share of episodes whose near-optimal set is wide (ambiguous) is reported rather than hidden.
- Re-fit a rendered scene with known parameters (synthetic check): the fit recovers them within tolerance.

### Pitfalls

- SAM may segment the laptop's reflection, the screen content or the hand; look at all overlays.
- The robot mask must be right (section 5) or the exclusion region eats the laptop.
- Do not tune ε per episode to make fits look good; one rule for all 40.

---

## 8. Parameter belief ψ and calibration on demos (proposal Step 5)

### Practical steps

1. **Observables from demos.** Run the section 7 fitter on several frames of each demo (e.g. every 0.5 s), giving a lid-angle track `θ̂_e(t)` and base displacement for each demo `e`. These are the only "measurements" of what actually happened.
2. **Simulate each demo** in the twin with its recorded actions and a candidate ψ, producing `θ_e(t; ψ)`.
3. **Summary statistics:** final lid angle, time of first contact, angle at fixed times, whether the lid closed, base displacement.
4. **Rejection ABC.** Draw ψ from the prior, simulate all calibration demos, accept ψ when the distance between simulated and observed summary statistics is below a tolerance. The accepted sample is the belief `p(ψ)` used later (section 9 and the proposal's probes). The simulator is cheap, so tens of thousands of draws are feasible on CPU.
5. **Frame alignment** `T_WB` and any controller lag are estimated in the same stage from the demos where joints are recorded.
6. **Split:** use a subset of demos for calibration and a **separate held-out set for validation** (section 11); do not look at the validation demos during calibration.

### Theory

- **Approximate Bayesian computation** replaces the likelihood by simulation plus a distance on summary statistics; the accepted draws approximate the posterior when the tolerance is small and the statistics are informative [cite: Beaumont, Zhang & Balding 2002; Marin et al. 2012]. It is the right tool when the likelihood of images given physics parameters is intractable but simulation is cheap.
- **Why a belief and not a best fit.** Friction, damping and mass are only weakly identified from a handful of demos; the *spread* of `p(ψ)` is the honest statement of what the twin does not know, and the referee has to tolerate that spread (a verdict of "inconsistent" should mean inconsistent for all plausible ψ).
- **Identifiability by intervention.** The probes of Step 6 (chunk-0 probes with a null action and with chosen actions) are interventions that separate effects which passive observation cannot; the proposal's identification-by-intervention result applies there.

### Tests and acceptance

- **Posterior predictive check:** simulate held-out demos with draws from `p(ψ)`; the real lid-angle track must fall inside the predictive band for most of them (report coverage).
- **Prior sensitivity:** repeat with a wider and a narrower prior; if the verdicts change a lot, say so.
- Report the **phase map**: in which phases of the closing task (approach, contact, push, closed) the twin's prediction error is small and where it is large. That map tells you where the referee can be trusted.

### Pitfalls

- Never calibrate and validate on the same demos.
- If Ctrl-World was fine-tuned on some of the demos (request 6), do not use those for the Ctrl-World-versus-real checks.

---

## 9. Comparing twin and Ctrl-World (proposal Steps 4 and 7)

### Practical steps

1. **Same inputs.** For each chunk, run the twin with the same chunk of EEF targets and the same starting scene (the current scene state of this rollout, section 10), and render the three views at 192 × 320, 30 Hz, to match the Ctrl-World video clip.
2. **Features.** Embed each clip with the frozen video encoder used in the proposal (V-JEPA family) **(check checkpoint, input clip length and resolution, patch/tubelet size)**. Compute change features `Δφ_t = φ(frame_t) − φ(frame_0)` for both sources, optionally pooled over the lid region using the twin's masks so the comparison is sensitive to the lid.
3. **Distance.** Cosine distance between `Δφ` of the twin and of Ctrl-World for each time step and each view; summarise per chunk (maximum and mean over time). (The proposal's definition uses the Euclidean norm of the difference of unit-normalised change features; keep to the proposal's definition for the thesis results.)
4. **Over the set:** repeat for each `x ∈ Θ` and each ψ draw; keep the **minimum** (best-case) distance: the closest plausible scene.
5. **Threshold** (section 11): a chunk is flagged "inconsistent" when even the best-case distance exceeds the calibrated threshold.

### Theory

- **Why differences.** Real or imagined appearance differs from a flat-colour render in colour, texture and lighting, but those offsets are present in both the first frame and later frames of the same source. Subtracting the first-frame feature removes most of it and leaves "what changed", which is what the physics predicts.
- **Why the minimum over the plausible set.** The referee should flag only what cannot be explained. Taking the best case over `Θ × p(ψ)` makes false alarms the less likely mistake, which is the conservative direction for a method that down-weights rewards.

### Tests

- On real demo frames: real-video features versus twin features should be small and should be larger when the twin is deliberately perturbed (lid angle changed, arm path changed): the statistic must have **power**.
- Negative control: compare each episode's twin against Ctrl-World video from a **different** episode; the distance must be larger than the matched pair.
- Positive control on imagined data: a Ctrl-World rollout where the gripper never touches the lid but the lid closes (any such example found in baseline logs) must be flagged.

### Pitfalls

- Frame rate, clip length and resolution must match what the encoder expects.
- A feature gap that exists on real demos too (twin versus real) is the twin's modelling error; it is already included in the calibrated threshold, but only if calibration used the same pipeline.

---

## 10. Integration and trust weighting (milestones T7 and T8)

### Practical steps

1. **TwinSession per rollout.** One twin instance per env, reset when the env resets (the reset knows the episode ids; look up `scene_cache`), advanced one chunk at a time with the chunk's EEF targets. Held by the plugin, keyed by env id. Follow the existing `stage15_plugin` pattern: `sitecustomize.py` plus a monkeypatch, enabled by an env var (`RLINF_TWIN_MODE`), with no edits in vendored files except one short marked patch where advantages are computed.
2. **Log-only mode first.** The plugin computes verdicts and writes them to the rollout record but leaves the reward unchanged. On the smoke profile (`close_smoke_2n4g.yaml`) the advantages must equal the baseline exactly (w = 1).
3. **Weights.** Each chunk gets `w ∈ {0, 1}` (hard) or `[0, 1]` (soft) from the verdict. Per-chunk `w` travels with the rollout batch like the metadata fields, and the **actor gathers it with the rewards** after the all-gather (`fsdp_actor_worker.py:1716`), because the groups of 16 are spread over four ranks.
4. **Neutral imputation.** For each group and chunk, a distrusted reward is replaced by the mean over the trusted members of that group at that chunk. After centring, it contributes zero to that member's advantage. Then the suffix returns and the group normalisation proceed as in `validate_and_compute_group_suffix_advantages` (`cross_rank_grpo.py:801`). (The proposal's formula is `r_hat = w r + (1 - w) m` with `m = sum(w r) / sum(w)`; with hard weights this is the same thing.)
5. **Decision D1 (the scale question).** Imputation shrinks the group standard deviation, and the division by that standard deviation then **inflates** the remaining members' advantages (with 12 of 16 imputed at one chunk, each of the other four gets about twice the magnitude). Implement both variants behind a flag: (A) normalise by the std of the imputed returns; (B) normalise by the std of the original returns. Run B as an ablation arm and report the difference.

### Theory

- **GRPO** uses advantages `A_i = (R_i − mean)/std` within a group; only differences between members matter (proposal Lemma 1), and a member whose centred return is zero receives no push (Lemma 2).
- **Neutrality of imputation** (the proposition "trust weighting is safe and exactly neutral", Proposition 14 in the compiled proposal; check the number in your PDF): `w ≡ 1` recovers the paper's method exactly, and a distrusted reward adds exactly zero to the centred returns. What the proposition does not say is anything about the *scale* after normalisation; that is D1.

### Tests (T8, can start now on the synthetic engine, torch only)

1. `w ≡ 1` reproduces both the synthetic and the vendored advantage function bit for bit.
2. A zero-weight reward adds exactly zero to the centred returns of every member.
3. Permuting group members leaves the advantages (up to permutation) unchanged, and the result does not depend on how members are split over ranks.
4. All weights zero in a group gives zero advantages (no NaNs: the `1e-6` in the denominator matters). (With `w_min > 0` in the proposal the weights are never exactly zero; test both.)
5. D1 variants: A and B differ as predicted on a worked example (the factor of about two above).
6. Plugin in log-only mode on the smoke profile changes nothing.

### Pitfalls

- Do the weighting **after** the all-gather, never in the env worker.
- Check dtype and device when adding a field to the gathered batch.
- Terminal goal reward is added at the last chunk; make sure its weight follows the last chunk's weight (decide this explicitly and document it).

---

## 11. Verification and validation: how you know the twin is good enough

**Definitions.** *Verification* asks whether the code solves the model equations correctly; *validation* asks whether the model is a good description of reality for the intended use [cite: Oberkampf & Roy, *Verification and Validation in Scientific Computing*, 2010; ASME V&V 10 and V&V 20].

**Verification (cheap, automatic, always on).**

| Check | Where |
|---|---|
| FK parity with repo, 1000 poses | T1 |
| FK(IK(x)) = x | T2 |
| Null action leaves state unchanged | T3 |
| Timestep convergence | T3 |
| Determinism | T3 |
| w = 1 reproduces baseline advantages | T7, T8 |

**Validation (needs real data, done once, reported).**

| Quantity | Data | Report |
|---|---|---|
| Initialiser error | ~10 hand-labelled frames | lid angle error (deg), position (cm) |
| Robot mask IoU | held-out frames | distribution per camera |
| Twin-versus-real feature gap by phase | held-out demos | the phase map |
| Posterior predictive coverage | held-out demos | share inside the band |
| Verdict power | perturbed twins, other-episode controls | detection rates |

**Calibration of the threshold.**

- *Split conformal prediction*: take calibration scores `s_1..s_n` (here: the best-case twin-versus-**real** distances on calibration demos, computed with the full pipeline), set the threshold `τ` to the `⌈(n+1)(1−α)⌉`-th smallest, and for a new exchangeable score `P(s_{n+1} ≤ τ) ≥ 1 − α` [cite: Lei et al. 2018; Angelopoulos & Bates 2021, "A gentle introduction to conformal prediction"]. That is the proposal's false-alarm bound.
- *Limit of the guarantee:* the bound needs exchangeability between calibration scores (demo replays with human actions) and test scores (policy rollouts with imagined video). That assumption is **not** exact. Reduce the gap by using **one threshold per phase** (a Mondrian-style split) [cite: Vovk et al.], and say in the thesis that the bound is nominal and then check empirically on held-out demos.
- Choose α once (e.g. 0.1) and report how the share of flagged chunks changes with α.

**Splits (write them down before looking at any result).**

- Calibration demos: used for ψ, `T_WB`, controller lag, thresholds.
- Validation demos: used for nothing before the reported validation.
- Eight evaluation scenes (6, 7, 14, 20, 26, 31, 32, 37): the RL evaluation; do not use their demos for calibration either (check if demos exist for them).

---

## 12. First two weeks, concretely (assuming the lab answers late)

| Day | Work | Output |
|---|---|---|
| Mon 16 Nov | Send the six lab requests. Create `src/twin/` skeleton, install `mujoco`, headless render (T0). Create the conventions file (section 1). | Render of an empty scene, time per frame |
| Tue | Numpy DH FK and reference table from the repo function (T1). | Parity test red or green |
| Wed | MJCF generator from DH, parity in MuJoCo. | T1 done |
| Thu | Action conversion wrapper (import by path), IK with warm start, synthetic IK tests (T2 synthetic). | T2 synthetic done |
| Fri | Laptop MJCF with placeholder dimensions, hinge, scripted close, null-action test (T3 start). | Video of scripted close |
| Mon 23 Nov | Finish T3 (timestep convergence, determinism, parameter sweep), T8 weighting tests on the synthetic engine. | T3, T8 done |
| Tue to Fri | When lab data arrives: cameras (T4), SAM 3 and initialiser (T5). If it has not: build the initialiser on synthetic renders so only the real masks are missing. | T4 or synthetic T5 |

The critical path is the lab data, not the code.

---

## 13. References to verify before citing (from memory)

- Denavit & Hartenberg, "A kinematic notation for lower-pair mechanisms based on matrices", J. Applied Mechanics, 1955.
- Siciliano, Sciavicco, Villani & Oriolo, *Robotics: Modelling, Planning and Control*, Springer, 2009.
- Nakamura & Hanafusa, "Inverse kinematic solutions with singularity robustness for robot manipulator control", J. Dyn. Sys. Meas. Control, 1986.
- Wampler, "Manipulator inverse kinematic solutions based on vector formulations and damped least-squares methods", IEEE Trans. SMC, 1986.
- Hawkins, "Analytic inverse kinematics for the Universal Robots UR-5/UR-10 arms", Georgia Tech technical report, 2013.
- Zhou, Barnes, Lu, Yang & Li, "On the continuity of rotation representations in neural networks", CVPR 2019.
- Levinson et al., "An analysis of SVD for deep rotation estimation", NeurIPS 2020.
- Todorov, Erez & Tassa, "MuJoCo: A physics engine for model-based control", IROS 2012.
- Todorov, "Convex and analytically-invertible dynamics with contacts and constraints: theory and implementation in MuJoCo", ICRA 2014.
- Hartley & Zisserman, *Multiple View Geometry in Computer Vision*, 2004.
- Tsai & Lenz, "A new technique for fully autonomous and efficient 3D robotics hand/eye calibration", IEEE Trans. Robotics and Automation, 1989.
- Lee et al., "Camera-to-robot pose estimation from a single image" (DREAM), ICRA 2020; Labbé et al., "Single-view robot pose and joint angle estimation via render & compare", CVPR 2021.
- Beaumont, Zhang & Balding, "Approximate Bayesian computation in population genetics", Genetics, 2002; Marin, Pudlo, Robert & Ryder, "Approximate Bayesian computational methods", Statistics and Computing, 2012.
- Oberkampf & Roy, *Verification and Validation in Scientific Computing*, Cambridge University Press, 2010.
- Lei, G'Sell, Rinaldo, Tibshirani & Wasserman, "Distribution-free predictive inference for regression", JASA, 2018; Angelopoulos & Bates, "A gentle introduction to conformal prediction and distribution-free uncertainty quantification", 2021; Vovk, Gammerman & Shafer, *Algorithmic Learning in a Random World*, 2005.

---

## 14. What I could not verify

- No code was run: the parity test, IK behaviour, contact behaviour and render times are plans with acceptance criteria, not results.
- Dataset content: whether `observation.state` holds joints or EEF pose, the camera preprocessing, which episodes Ctrl-World was fine-tuned on, and whether demos exist for all eight evaluation scenes.
- MuJoCo specifics (camera attribute names, default friction combination, cone type, EGL on the aarch64 nodes) depend on the installed version.
- SAM 3 and V-JEPA interfaces and licences.
- All citations are from memory.
