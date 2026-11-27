# Observation gating, geometric strength and depth priors

## Why a small global attenuation is not algebraically harmless

With a frozen BA state and frozen U, let the geometric normal-equation blocks be pose curvatureA, pose/depth cross-blockE, diagonal depth curvatureCg and right-hand-sidebg. A uniform external observation multiplierg scales these geometric terms linearly. It does not scale the frozen Metric3D prior, the learned eta damping or native post-Schur pose damping.

The resulting Schur system therefore includes

`H(g) = g A − g² E (g Cg + Cprior)^−1 Eᵀ`,

followed by DROID-W's original damping. In general, `H(g)` is not `g H(1)`. A background score tail that attenuates nearly every observation can change the geometry/prior balance even if mean attenuation is only several percent. This is a same-state algebraic mechanism, not proof of the historical closed-loop failure: native U, keyframe states and later residual targets also evolve.

The uniform same-mean legacy control tests whether spatially selective suppression differs from changing total geometric strength. The runs are closed-loop trajectories, not fixed-state native BA replays. Native numerical variability requires repeated baselines; a single favourable run is insufficient.

## Neutral evidence and geometry verification

For source and predicted-target scoresMi,Mj, use `p=max(Mi,Mj)`, `s=clip((p−0.4)/0.4,0,1)` and `G=1−0.75s`. Both endpoints below0.4 preserve original weights bit-for-bit. This avoids two-end multiplication of weak, ambiguous background scores. It does not establish that all low-score pixels are truly static.

An independent verifier uses FP32 RAFT, forward/backward consistency, and robust MAGSAC epipolar estimation. The geometric evidence score has a1pixel neutral region and reaches1at4pixels. Missing or degenerate evidence remains neutral. The fusion gate uses `s_model × s_geometry × w_native_source_U`; source U already suppressing an observation reduces the incremental external penalty. The original native U array and its update are untouched.

Implementation limit: the numerical U coefficient is not switched by each call's `enable_udba`. If native UBA is disabled, it remains a heuristic conservative modulator, not an already-active native weight. Exact per-stage de-duplication is therefore not established. The two model/geometry signals are separate computational paths, not proven statistically independent calibrated probabilities.

Sampson residual cannot detect all motion along an epipolar line. Pure rotation, planar scenes, a dominant moving object and flow errors can invalidate F. Camera-flow residuals from native predicted pose/disparity are therefore also recorded, but they combine depth/pose/flow errors and are not labelled motion GT.

## Separate depth candidate

Pi3 local-point z is a relative camera depth, distinct from disparity, a motion score and DROID U. One robust median scale per short window aligns its static-support predictions to Metric3D **prediction** units. A conservative inverse-depth blend is

`d_blend = 0.75 / depth_Metric3D + 0.25 / (s_window depth_Pi3)`.

The stored depth is `1/d_blend`, only where both values are finite/positive, motion score<0.4 and their aligned ratio lies in[0.5,2]. Other pixels retain Metric3D exactly. Temporal scaleP95/P05must not exceed2. No Confidence score is used as a calibrated probability. This is an offline exploratory VO ablation, not evidence of more accurate metric depth or a production CADP implementation.
