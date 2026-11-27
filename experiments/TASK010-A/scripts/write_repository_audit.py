"""Compose source availability audit from retrieved identities and inspected entrypoints."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'experiments/TASK010-A'
records=json.loads((TASK/'02_literature_and_code/SOURCE_SNAPSHOTS.json').read_text())
text=['# Official source identity and executable-scope audit','',
    'Retrieved source archives are outside the research repository. The exact commits and downloaded archive identities below are retained without vendoring external model source/weights into the review. No default branch or historical source was replaced.','',
    '| Project | Official commit | Retrieved status | Root license metadata |',
    '|---|---|---|---|']
for r in records:
    link=f"[{r['repo']}](https://github.com/{r['repo']}/tree/{r['commit']})" if 'commit' in r else r['repo']
    text.append(f"| {link} | {r.get('commit','UNAVAILABLE')} | {r['status']} | {r.get('license','NOT_ESTABLISHED')} |")
text += ['',
    '## Actual interfaces and exclusions','',
    '- GMOS: `core/pi3_encoder.py`, `core/sam2_encoder.py`, `core/gmos_s.py`; independent official GMOS-S forward, CPU offloading between encoders. The full instance propagator is not executed.',
    '- Conference GeoMotion: direct Pi3 motion detector in the inspected source, explicit RGB[0,1] and recorded flow magnitude. The standalone demo has an additional normalization path; our adapter avoids double ImageNet normalization.',
    '- Full GeoMotion: `motion_seg_inference_raft.py` helpers and `pi3/models/pi3_conf_flow_cam_lowfeature_wo_mean_raft.py`; independent official raw detector, recurrent RAFT hidden features checked against a native torchvision forward hook. Optional SAM2 post-refinement is not part of this detector test. Actual completion/resource outcome is in the final report, not inferred from this source audit.',
    '- Pi3MOS: reused fixed TASK008 model source and official checkpoint, independent `Pi3.forward` only. It produces motion probability, raw confidence, local points and pose. It does not launch DPVO or Pi3MOS-SLAM BA. The checkpoint/source identities and strict-load receipt accompany each new model run.',
    '- The original Pi3 GitHub location returned404; the admitted GMOS source contains the encoder implementation needed for GMOS-S. This is not a claim of a successful fresh clone of that unavailable URL.',
    '- RoMo: official geometry/SAM2 implementation inspected; the task-specific RAFT/FB/MAGSAC verifier is independent and not a reproduction of the full RoMo pipeline.',
    '- DynOSeg: inspected release states code is forthcoming. No runnable model/weight is fabricated.',
    '- DYNAPO and MonST3R: source/reference audit only; no paid VLM service, global optimization or inferred benchmark scores.',
    '- BA-Track MDTracker: previously admitted tensor-only checkpoint and unmodified source; an independent static-target comparison, with predicted Metric3D depth rather than the complete published UniDepth pipeline.',
    '',
    '## Production protection','',
    'The native runner imports frozen DROID-W frontend, DepthVideo, Backend and Filler classes from the preserved TASK009 compatibility workspace. New hooks and runners live only under TASK010-A. The Windows and WSL model runtimes differ and are not advertised as the formal remote3090 baseline. Runtime receipts identify actual extension and tracker checkpoint hashes; `ORIGINAL_ASSET_PROTECTION.json` performs the final historical read-only hash check.',
    '',
    'The fresh worktree branch starts at sealed TASK009 commit `ff0c9ed761dbcdd6d2fe7b2cda5651c6e173efe1`. The historical dirty worktree, its index, branches and all source/experimental artifacts remain untouched. Publication uses a new commit/branch and an isolated index; repository visibility and default branch are preserved.']
(TASK/'02_literature_and_code/REPOSITORY_AUDIT.md').write_text('\n'.join(text)+'\n')
print('Repository audit generated from actual official identities')
