"""Reuse verified R2 publication transport for a new isolated R3 branch/release."""
import pathlib,re,ast
ROOT=pathlib.Path(__file__).resolve().parents[1]
OLD=ROOT.parent/'GAMECAM_TASK005B_R2_NUMERICAL_EQUIVALENCE_20261125_R1/07_release/publish_review.py'
s=OLD.read_text(encoding='utf-8')
s=s.replace('Full immutable evidence Release','Full immutable evidence Release')
s=s.replace('GameCam-TASK005B-R2-20261125-R1','GameCam-TASK005B-R3-20261125-R1')
s=s.replace("SOURCE=pathlib.Path(r'C:\\Users\\Administrator\\Documents\\GameCam-TASK005B-GPU-20261125-R1\\publication_repository_task005b_gpu_mechanism')","SOURCE=pathlib.Path(r'C:\\Users\\Administrator\\Documents\\GameCam-TASK005B-R2-20261125-R1\\publication_repository_task005b_r2_numerics')")
s=s.replace("SOURCE=pathlib.Path(r'C:\\Users\\Administrator\\Documents\\GameCam-TASK005B-R3-20261125-R1\\publication_repository_task005b_r2_numerics')","SOURCE=pathlib.Path(r'C:\\Users\\Administrator\\Documents\\GameCam-TASK005B-R2-20261125-R1\\publication_repository_task005b_r2_numerics')")
s=s.replace('publication_repository_task005b_r2_numerics\'\nBASE','publication_repository_task005b_r3_reduction_U\'\nBASE')
s=s.replace("REPO=RECV/'publication_repository_task005b_r2_numerics'","REPO=RECV/'publication_repository_task005b_r3_reduction_U'")
s=s.replace('task005b-r2-native-numerics-20261125','task005b-r3-reduction-u-isolation-20261125')
s=s.replace('TASK005B-R2','TASK005B-R3')
start=s.index(" status=f'''");end=s.index("'''",start+12)+3
replacement=""" status=f'''# GameCam-VO · TASK005B-R3 reduction and U feedback isolation

Completed 16 isolated Jjj calls, 16 isolated J_linear calls and 20 two-iteration BA replays on the sealed D0_S1_RGB233 context. Both isolated reductions fluctuate under fixed inputs. Fixed U retains native affine/temp updates and blocks only U feedback into the next round. See the final report for endpoint gates, causal limits and readiness decisions. No S0, remaining S1 matrix, full-sequence model run or shutdown.

[Final review]({REL}/FINAL_REVIEW.md) · [Isolation results]({REL}/R3_REDUCTION_ISOLATION.md) · [U feedback]({REL}/R3_U_FEEDBACK.md) · [Readiness decision]({REL}/R3_CANDIDATE_READINESS.md) · [Complete review ZIP]({url})

The complete ZIP ({p['ZIP_bytes']:,} bytes) contains the exact full input archive, fixed R2 intermediate, all 52 output NPZ files, complete scientific logs and independent diagnostic binary. CRC and all {p['manifest_items']} internal SHA-256 entries verified. Reports and CSV files are expanded for direct review.

Task004C-B, Task005A, TASK005B-R1 and R2 remain sealed. Instance remains running.
'''"""
s=s[:start]+replacement+s[end:]
s=s.replace("'task005b-gpu-mechanism-20261125']:","'task005b-gpu-mechanism-20261125','task005b-r2-native-numerics-20261125']:")
s=s.replace('Record TASK005B-R3 native repeatability and two-round feedback evidence','Record TASK005B-R3 isolated reductions and U feedback controls')
s=s.replace('TASK005B-R3 — native repeatability and endpoint equivalence review','TASK005B-R3 — isolated CUDA reductions and U feedback review')
body_start=s.index("'body':'DIAGNOSTIC COMPLETE;")
body_end=s.index("','draft':False",body_start)
s=s[:body_start]+"'body':'Completed 16 isolated Jjj calls, 16 isolated J_linear calls and 20 two-iteration native BA controls. Both atomic reductions fluctuate independently. U-only fixed controls retain native affine/temp updates. Complete evidence, unchanged-tolerance checks and readiness limits are in the final report and ZIP. No S0 or remaining mechanism-matrix expansion."+s[body_end:]
s=s.replace("['FINAL_REVIEW.md','R2_DECISION.json','R2_FEEDBACK_TRACE.md','04_analysis/FEEDBACK_CHAIN_AUDIT.json','04_analysis/PLAIN_PAIRWISE_ERRORS.csv']","['FINAL_REVIEW.md','R3_DECISION.json','R3_U_FEEDBACK.md','04_analysis/ISOLATED_SUMMARY.json','04_analysis/BA_REPEATABILITY_SUMMARY.csv']")
s=re.sub(r'^SOURCE=.*$',lambda m:"SOURCE=pathlib.Path(r'C:\\Users\\Administrator\\Documents\\GameCam-TASK005B-R2-20261125-R1\\publication_repository_task005b_r2_numerics')",s,flags=re.MULTILINE)
ast.parse(s)
(ROOT/'07_release/publish_review.py').write_text(s,encoding='utf-8',newline='\n')
print('Prepared R3 publisher; no network mutation performed')
