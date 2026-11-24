import pathlib,json,sys,os
ROOT=pathlib.Path(sys.argv[1]);OUT=ROOT/'analysis'
s=json.loads((OUT/'REVIEW_SUMMARY_DATA.json').read_text());Arows=s['A'];res=s['residuals']
import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
fig,axs=plt.subplots(2,2,figsize=(10,7.1));colors=['#336A86','#C17D35']
for j,arm in enumerate(['E0','E1']):
 rr=[r for r in Arows if r['arm']==arm];cc=[r for r in res if r['arm']==arm]
 axs[0,j].bar(['D=1','D=0'],[float(r['fixed_scale_displacement_ratio_pct']) for r in rr],color=colors,width=.55);axs[0,j].axhline(100,color='#555555',ls='--',lw=1);axs[0,j].set_title(arm+' captured input state');axs[0,j].set_ylabel('312 to 328 displacement ratio (%)');axs[0,j].set_ylim(0,155)
 for i,r in enumerate(rr):axs[0,j].text(i,float(r['fixed_scale_displacement_ratio_pct'])+3,f"{float(r['fixed_scale_displacement_ratio_pct']):.2f}%",ha='center',fontsize=9)
 vals=[float(r['common_geometry_sse_fixed_initial_U']) for r in cc];axs[1,j].bar(['D=1','D=0'],vals,color=colors,width=.55);axs[1,j].set_ylabel('Common-support geometry SSE');axs[1,j].set_ylim(0,max(vals)*1.2)
 for i,v in enumerate(vals):axs[1,j].text(i,v+max(vals)*.03,f'{v:.3f}',ha='center',fontsize=9)
 for ax in axs[:,j]:ax.spines[['right','top']].set_visible(False);ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
fig.suptitle('Fixed native BA inputs: D response depends on the captured state',fontsize=13);fig.text(.5,.016,'One call per branch; two inner iterations; W=U=1. No Filler or full-sequence score. Fixed scale = 19.1341794347.',ha='center',fontsize=8);fig.tight_layout(rect=(0,.04,1,.95));fig.savefig(OUT/'TASK004C_FIXED_STATE_COMPARISON.png',dpi=170);fig.savefig(OUT/'TASK004C_FIXED_STATE_COMPARISON.pdf');plt.close(fig)

print(json.dumps({'plot_created':True,'torch_imported':'torch' in sys.modules}))
