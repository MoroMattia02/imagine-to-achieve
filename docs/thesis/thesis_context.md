# Thesis context: Checking Imagination Against Physics

Short version of the thesis proposal (final version, 27 Oct 2026), written so that Claude Code can read it at the start of a session. Supervisor: Sichao Liu. If this file and the code disagree, say so instead of silently choosing one. See "Known differences" at the end.

Related files in this folder: `twin_implementation_plan.md` (code map and milestones T0 to T8), `twin_detailed_guide.md` (theory, reasons, tests per component).

## In one paragraph

The base paper, *Achieve What You Imagined* (arXiv 2609.33832), trains the action head of a world-action model (Cosmos 3) with reinforcement learning (FPO with GRPO-style group advantages) entirely in imagination. The reward compares the policy's imagined plan video with what a frozen action-conditioned world model (Ctrl-World) predicts the policy's actions will do. Real UR5 success over four tasks rises from 43.4% to 75.1% (laptop closing 22% to 68%) with no robot interaction in training. The reward is only as good as Ctrl-World; where it is physically wrong (mostly at contact) the policy is optimised against the model's errors and nothing in the loop detects it. Imagined success in the paper peaks after 9 to 11 updates and then declines, with no identified cause.

This thesis adds a **physics twin used as a referee**: a simple MuJoCo model of the scene, initialised automatically from the real first camera frame, receives exactly the same actions as Ctrl-World. Where the twin's answer does not depend on what it does not know, disagreement with Ctrl-World is evidence that the feedback is wrong, and that reward is down-weighted.

## The paper's loop (what the code implements)

- Policy: Cosmos3-Nano fine-tuned on UR5 data; only the action head is trained. World model: Ctrl-World, frozen. Only the first frame of each demonstration (start) and its final frames (goal image) come from real data.
- A rollout has N = 5 chunks; each chunk is 32 actions at 15 Hz, 10-D (body-frame position delta, rot6d rotation delta, absolute gripper). Groups of G = 16 candidates share a start frame.
- Reward per chunk: minus pixel MSE between the imagined plan video and Ctrl-World's predicted video, plus a goal term (MSE of the last predicted frame to the goal image) at the last chunk.
- Advantage: discounted suffix return (gamma = 0.95), centred and divided by the std within the group.
- Two facts the method uses: (Lemma 1) adding the same constant to every candidate's reward at a chunk changes no advantage, so only differences between candidates matter; (Lemma 2) at the start of an update a sample with zero advantage gives zero gradient.

## Research goal and questions

Goal: detect physically inconsistent world-model feedback and keep it out of policy training, using an independent physics simulation of the scene that is initialised from the real camera frame and run on the same actions.

Research question: *Can checking a world model's feedback against a physics twin of the scene make robot policies trained in imagination more reliable in the real world?*

- **RQ1 Detect:** how often and where (which phase of the task) do Ctrl-World's predicted consequences contradict physics, and of which kind (wrong reaction, ignores the action, invents an effect)?
- **RQ2 Explain:** do these errors grow as the policy trains and explain the late decline of imagined success (exploitation of Ctrl-World)?
- **RQ3 Improve:** if the policy learns only from feedback the twin trusts, does it succeed more often on the real robot?

Hypotheses (thresholds fixed before any RL run): H1 at least 10% of chunk-0 rewards with a verdict are failures, concentrated at gripper-lid contact; H2 the twin's predicted change is closer to the real change than Ctrl-World's during and after contact, and its decisive verdicts agree in sign with real effects on about 20 real action pairs more often than Ctrl-World's; H3 failure and divergence rates grow over updates and precede the decline; H4 trust weighting removes or delays the decline, and real laptop success is at least the paper's 68%, with a shuffled-weights control not improving.

## Method in nine steps

| Step | What |
|---|---|
| 1 General twin | MuJoCo: UR5 arm + gripper, table, laptop as two boxes with a hinge (state x = base position, base yaw, lid angle), three cameras, belief p(psi) over hinge friction/damping and contact friction. |
| 2 Initialiser | SAM 3 masks of laptop parts on the real first frame; fit x by render-and-compare (mask IoU); keep the near-optimal set of start states, not a single point. Runs offline once per start scene. |
| 3 Same actions | Actions converted to joint targets (IK) and tracked by a controller model fitted on the demos; twin state evolves deterministically for each element of the uncertainty set Theta = Psi_K x near-optimal set. |
| 4 Comparison | Both videos embedded with frozen V-JEPA 2; compare change since frame 0 (so constant appearance offsets cancel). |
| 5 Calibration | On the 40 laptop demos (20 fit / 20 calibrate): fit p(psi) and controller; phase map (where the twin beats Ctrl-World); thresholds; representation check. All before any RL. |
| 6 Chunk 0 | Controlled interventions from the same real start: probes (small smooth changes to the action), null action, candidate pairs. Verdict per reward: consistent, wrong reaction, ignores the action, invents an effect, or no verdict. Needs Ctrl-World state save/restore and common seeds. |
| 7 Later chunks | Twin runs open-loop from the real start in parallel; score = min over Theta of the grounded disagreement; flag the first chunk where it exceeds a conformal threshold (split conformal on the demos; false-alarm rate at most alpha under exchangeability); twin abstains when its own spread is large. |
| 8 Trust weights | w = p * g. g = w_min from the divergence chunk on; p from the chunk-0 verdict. Neutral imputation: r_hat = w r + (1 - w) m, m = sum(w r) / sum(w). w = 1 recovers the paper exactly; a reward with w = 0 adds exactly zero to the centred returns. |
| 9 Diagnostics | Arm-following check, share of physically inconsistent imagined successes (twin lid angle stays open while the classifier says success), optional re-synchronised residual. Analysis only. |

## Scope and constraints

- Same models as the paper: authors' UR5 Cosmos3-Nano policy, task-specific frozen Ctrl-World, the success classifier. Nothing in the video path or in Ctrl-World is changed.
- Main task: laptop closing (hinge is nearly kinematic, largest RL gain in the paper). The initialiser is also validated on first frames of the paper's four tasks (laptop, duck, Push-T, cups).
- Engine: MuJoCo on CPU (Isaac Sim needs RT-core GPUs, which the GH200 nodes lack).
- No object state is read from generated frames in the training signal. The twin gets only the real first frame and then actions. Comparisons use generic video features (V-JEPA), not task-specific perception.
- Boundary with a colleague's thesis: this work does not embed physical information in the world-action model, and has no goal representation, hindsight relabelling, curriculum or real-robot training data.
- Hand-in 19 Feb 2027. Robot access from 25 Jan 2027 (worst case 1 Feb); robot sessions are run by lab members from a written protocol. Compute: two RTX 4090, one RTX 5090, NAISS Arrhenius cluster (queued).

## Experiments and deliverables

- E0 referee validation before RL (initialiser on four tasks, replay of the 40 demos in twin and Ctrl-World per phase, representation checks, exact-restore check).
- E1 audit of the original method (verdict rates per type/phase/scene, candidate-pair agreement, null-action hallucination rate, divergence chunk distribution, arm-following error).
- E2 training dynamics (failure rate versus update, imagined success, share of physically inconsistent successes; trend and lag tests).
- E3 arms with equal budget: A original FPO; T full trust weighting; T0 chunk-0 only; TG grounded only; S shuffled weights.
- E4 real robot: paper's policy versus best trust-weighted policy, about 60 trials each on identical placements; about 20 action pairs from identical starts (which model predicts reality); replay of all real trials in both models.
- Deliverables: G1 the referee as open code; G2 the audit; G3 the trust-weighted laptop policy.

## Work plan (from the proposal)

| Period | Work |
|---|---|
| 15 Oct to 4 Nov | Reduced laptop run on the cluster with full logging; check the data. |
| 5 Nov to 2 Dec | General twin, initialiser, rendering, V-JEPA comparison, Ctrl-World save/restore. |
| 3 to 16 Dec | Calibration on demos (Step 5). |
| 17 Dec to 13 Jan | Arm A with audit (E1, E2); arms T, T0, TG, S at reduced profile. |
| 14 to 24 Jan | Full runs of A and the best arm; freeze policies; robot protocol dry run. |
| 25 Jan to 8 Feb | Robot sessions (E4). |
| to 19 Feb | Writing and hand-in. |

## Known differences between the proposal and the code (found on 13 Nov by reading the repo)

These are things to settle, not errors of the proposal text alone.

1. **Robot model.** The proposal says UR5e (MuJoCo Menagerie). The repo's FK uses the constants of the original UR5 and a 0.18 m TCP offset (`eef_pose_adapter.py`). The twin follows the repo until the lab confirms the robot.
2. **Advantage scale.** Neutral imputation keeps the centred returns exact, but the group std shrinks when many rewards are imputed, so the remaining members get larger normalised advantages (about 2x when 12 of 16 are imputed at one chunk). Decision D1 in the plan: implement both normalisations behind a flag.
3. **Where weights can be applied.** Groups of 16 are spread over 4 ranks and advantages are computed after an all-gather in the actor, so the trust-weighted mean has to be formed there, not in the env worker.
4. **Initialiser is offline.** Only 40 start scenes exist (32 training, 8 evaluation: 6, 7, 14, 20, 26, 31, 32, 37), so the initialiser runs once per episode and is cached.
5. **Ctrl-World noise** is common within a group (`common_random_numbers_within_group`), which matters for the seeds of the chunk-0 probes.
6. **Not in the repo:** camera intrinsics and extrinsics, a robot MJCF/URDF, gripper geometry, laptop dimensions. These are requests to the lab (see the plan, section 5), and are the critical path.
