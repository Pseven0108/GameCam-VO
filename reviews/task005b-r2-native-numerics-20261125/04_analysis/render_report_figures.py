import os,sys,pathlib,json,csv
os.environ['CUDA_VISIBLE_DEVICES']=''
sys.path.insert(0,r'C:\Users\Administrator\Documents\GameCam-VO-Task004CB-20261125\cpu_plot_dependencies')
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from analyze_pairs import ROOT,RECV,FINAL,compare
out=ROOT/'05_reports/figures';out.mkdir(parents=True,exist_ok=True)
plain={p.stem:dict(np.load(p,allow_pickle=False)) for p in (RECV/'plain').glob('*.npz')}
trace={p.stem:dict(np.load(p,allow_pickle=False)) for p in (RECV/'trace').glob('*.npz')}
fig,axes=plt.subplots(1,2,figsize=(11,4.3),layout='constrained')
pairs=[('original_1','original_2'),('reference_1','reference_2'),('paths_1','paths_2')]
for ax,field in zip(axes,['dx_last','dz_last']):
 vals=[compare(plain[a][field],plain[b][field])['max_error_to_tolerance'] for a,b in pairs]
 ax.bar(['Installed repeat','Reference repeat','Paths repeat'],vals,color=['#bc4b51','#4c78a8','#59a14f'])
 ax.axhline(1,color='black',linestyle='--',linewidth=1,label='Original tolerance boundary')
 ax.set_ylabel('Maximum |error| / (1e-6 + 1e-5 |reference|)');ax.set_title(field);ax.tick_params(axis='x',rotation=15)
 for i,v in enumerate(vals):ax.text(i,v+0.03,f'{v:.3f}',ha='center',fontsize=9)
axes[0].legend(fontsize=8);fig.suptitle('D0_S1_RGB233: repeatability of two-iteration BA; two calls per implementation')
fig.savefig(out/'NATIVE_REPEATABILITY.png',dpi=170);plt.close(fig)
fields=['iter1_dx','iter1_dz','iter1_Jjj_data','iter1_J_total','iter1_J_linear','iter1_affine_after','iter1_U_after','iter2_Cii_geometry','iter2_dx','iter2_dz']
fig,axes=plt.subplots(1,2,figsize=(12,5.5),layout='constrained')
for label,color in [('trace_reference','#4c78a8'),('trace_paths','#59a14f')]:
 a,b=trace[label+'_1'],trace[label+'_2']
 metrics=[compare(a[n],b[n]) for n in fields]
 axes[0].plot([m['max_abs'] for m in metrics],np.arange(len(fields)),marker='o',color=color,label=label)
 axes[1].plot([m['max_error_to_tolerance'] for m in metrics],np.arange(len(fields)),marker='o',color=color,label=label)
for ax in axes:
 ax.set_yticks(np.arange(len(fields)),[n.replace('iter1_','Round1 ').replace('iter2_','Round2 ') for n in fields]);ax.invert_yaxis();ax.grid(axis='x',alpha=.2);ax.legend(fontsize=8)
axes[0].set_xscale('symlog',linthresh=1e-11);axes[0].set_xlim(left=0);axes[0].set_xlabel('Maximum absolute difference (mixed physical units)')
axes[1].axvline(1,linestyle='--',color='black',linewidth=1);axes[1].set_xlabel('Maximum error / original tolerance')
fig.suptitle('Earliest observed numerical divergence occurs in Round1 Jjj_data')
fig.savefig(out/'TWO_ROUND_FEEDBACK_CHAIN.png',dpi=170);plt.close(fig)
print(json.dumps({'figures':[str(p) for p in out.glob('*.png')]}))
