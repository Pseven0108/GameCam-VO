"""Cross-check frozen scores and expose metric dependence; CPU only."""
import os,sys,json,csv
os.environ['CUDA_VISIBLE_DEVICES']='';sys.dont_write_bytecode=True
from task005a_analysis import ROOT,OLD,OUT,sha,dump,writecsv,verify_seal
with (OLD/'evaluation/CROSSOVER_SUMMARY.csv').open(encoding='utf-8-sig',newline='') as f:old=list(csv.DictReader(f))
with (OUT/'TASK005A_MATCHED_SUPPORT_STAGE_SCORES.csv').open(encoding='utf-8-sig',newline='') as f:new=list(csv.DictReader(f))
checks=[]
for r in old:
 actual=next(float(x['ate_sim3']) for x in new if x['arm']==r['arm'] and x['stage']=='EXPORTED' and x['support']=='ALL_487')
 delta=abs(actual-float(r['ate_sim3_game_units']));assert delta<1e-10
 checks.append({'arm':r['arm'],'recomputed_sim3':actual,'sealed_sim3':float(r['ate_sim3_game_units']),'absolute_difference':delta})
writecsv('TASK005A_METRIC_SENSITIVITY.csv',[{k:r[k] for k in ['arm','D','schedule','ate_sim3_game_units','ate_se3_inherited_sref_game_units','global_sim3_fit_scale','orientation_rmse_sim3_deg','endpoint312_328_global_sim3_ratio_pct']} for r in old])
by={r['arm']:r for r in old};contrasts=[]
for m in ['ate_sim3_game_units','ate_se3_inherited_sref_game_units','orientation_rmse_sim3_deg']:
 s1=float(by['B1'][m])-float(by['B2'][m]);s0=float(by['B3'][m])-float(by['B4'][m]);contrasts.append({'metric':m,'D_on_minus_off_S1':s1,'D_on_minus_off_S0':s0,'sign_reversal':s1*s0<0})
dump(OUT/'TASK005A_METRIC_SENSITIVITY.json',{'sealed_input_path':str(OLD/'evaluation/CROSSOVER_SUMMARY.csv'),'sealed_input_sha256':sha(OLD/'evaluation/CROSSOVER_SUMMARY.csv'),'independent_global_position_sim3_checks':checks,'contrasts':contrasts,'S_REF':19.1341794347,'S_REF_provenance':'Inherited historical Task004A E0 GT-derived alignment; diagnostic, not recovered metric scale','conclusion':'Sign reversal is established for global-Sim3 POSITION ATE; it is not a uniform claim across metric scale or orientation.'})
verify_seal();print(json.dumps(contrasts,ensure_ascii=False))
