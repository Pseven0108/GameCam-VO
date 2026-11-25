"""Scientific diagnostics from executed native BA results; no synthetic scores."""
import pathlib,csv,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'05_analysis/figures';OUT.mkdir(exist_ok=True)
ARMS=['D1_S1','D0_S1','D1_S0','D0_S0'];RGB=[19,233,401]

def rows(name):
    with (ROOT/'05_analysis'/name).open(newline='',encoding='utf-8') as stream:return list(csv.DictReader(stream))
def save(fig,name):
    for ext in ('png','pdf','svg'):fig.savefig(OUT/(name+'.'+ext),dpi=170,bbox_inches='tight')
    plt.close(fig)

def missing(ax,arm,rgb=None):
    label='NOT RUN'
    if arm=='D0_S1' and rgb==233:label='STOPPED: endpoint mismatch\nExcluded from complete-context summaries'
    if arm=='D0_S1' and rgb==401:label='Input captured; replay NOT RUN'
    ax.text(.5,.5,label,ha='center',va='center',transform=ax.transAxes,color='#6b6672',fontsize=9)
    ax.set_xticks([]);ax.set_yticks([]);ax.grid(False)

def main():
    metrics=rows('NATIVE_ITERATION_METRICS.csv');context=rows('CONTEXT_MECHANISM_SUMMARY.csv');feedback=rows('U_FEEDBACK_CONTRASTS.csv')
    plt.rcParams.update({'font.size':9,'font.family':'sans-serif','svg.fonttype':'none','pdf.fonttype':42,'axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.alpha':.15})
    colors=['#187a8d','#e3a526','#c94745','#5d589c']
    fig,axes=plt.subplots(4,3,figsize=(12,11),layout='constrained')
    for i,arm in enumerate(ARMS):
        for j,rgb in enumerate(RGB):
            ax=axes[i,j]
            if not any(r['arm']==arm and int(r['rgb'])==rgb for r in metrics):
                missing(ax,arm,rgb);ax.set_title(arm+' | RGB%03d'%rgb);continue
            for U,style in [('FROZEN','-'),('NATIVE_UPDATE','--')]:
                for c,color in zip('ABCD',colors):
                    selected=sorted([r for r in metrics if r['arm']==arm and int(r['rgb'])==rgb and r['U_mode']==U and r['cell']==c],key=lambda r:int(r['iteration']))
                    if selected:ax.plot([int(r['iteration']) for r in selected],[max(1e-12,float(r['dx_translation_norm'])) for r in selected],style+'o',color=color,label=c+' '+U,linewidth=1.4,markersize=4)
            ax.set_yscale('log');ax.set_xticks([1,2]);ax.set_title(arm+' | RGB%03d'%rgb)
            if j==0:ax.set_ylabel('Translation-step norm (native units)')
            if i==3:ax.set_xlabel('Internal iteration within one native call')
    handles,labels=axes[0,0].get_legend_handles_labels();fig.legend(handles,labels,loc='outside lower center',ncol=4,frameon=False)
    fig.suptitle('Partial same-state BA decomposition: 4 complete contexts\nStep size is not trajectory accuracy; RGB019 origins share the same initial state',fontsize=13)
    save(fig,'NATIVE_TRANSLATION_STEPS')

    fig,axes=plt.subplots(2,2,figsize=(10,7),layout='constrained')
    for arm,ax in zip(ARMS,axes.flat):
        if not any(r['arm']==arm for r in context):missing(ax,arm);ax.set_title(arm);continue
        for U,color,style in [('FROZEN','#187a8d','-'),('NATIVE_UPDATE','#c94745','--')]:
            selected=sorted([r for r in context if r['arm']==arm and r['U_mode']==U and r['iteration']=='2'],key=lambda r:int(r['rgb']))
            if selected:ax.plot([int(r['rgb']) for r in selected],[float(r['A_D_pair_loss_A_minus_D'])/max(float(r['A_D_pair_fixed_loss_before']),1e-30) for r in selected],style+'o',color=color,label=U)
        ax.axhline(0,color='black',linewidth=.7);ax.set_yscale('symlog',linthresh=.01);ax.set_xticks(RGB)
        ax.set_title(arm);ax.set_xlabel('Captured predecision RGB');ax.set_ylabel('(fixed loss A - D) / initial loss')
        if arm=='D0_S1':ax.text(.62,.5,'RGB233: stopped\nRGB401: not replayed',transform=ax.transAxes,ha='center',color='#6b6672')
    axes[0,0].legend(frameon=False);fig.suptitle('Two-iteration endpoints: common-weight A/D reprojection loss\nPositive: A has greater geometric residual; no GT accuracy implication')
    save(fig,'A_D_COMMON_WEIGHT_REPROJECTION')

    fig,axes=plt.subplots(2,2,figsize=(10,7),layout='constrained')
    for arm,ax in zip(ARMS,axes.flat):
        if not any(r['arm']==arm for r in feedback):missing(ax,arm);ax.set_title(arm);continue
        for c,color in zip('ABCD',colors):
            selected=sorted([r for r in feedback if r['arm']==arm and r['cell']==c and r['iteration']=='2'],key=lambda r:int(r['rgb']))
            ys=[]
            for row in selected:
                baseline=next(r for r in metrics if r['arm']==arm and r['rgb']==row['rgb'] and r['cell']==c and r['iteration']=='2' and r['U_mode']=='FROZEN')
                ys.append(float(row['native_minus_frozen_dx_translation_norm'])/max(float(baseline['dx_translation_norm']),1e-30))
            if selected:ax.plot([int(r['rgb']) for r in selected],np.maximum(1e-12,ys),'-o',label=c,color=color)
        ax.set_title(arm);ax.set_xticks(RGB);ax.set_yscale('log');ax.set_xlabel('Captured predecision RGB');ax.set_ylabel('U/affine feedback delta / frozen step')
        if arm=='D0_S1':ax.text(.62,.5,'RGB233: stopped\nRGB401: not replayed',transform=ax.transAxes,ha='center',color='#6b6672')
    axes[0,0].legend(frameon=False,ncol=4);fig.suptitle('Native joint U/affine feedback at internal iteration 2\nAffine is not independently held fixed in this comparison')
    save(fig,'U_AFFINE_SECOND_ITERATION_FEEDBACK')
    proof={'plots':3,'formats':['png','pdf','svg'],'measured_complete_contexts':len(set((r['arm'],r['rgb']) for r in metrics)),'failed_context_excluded_from_complete_summaries':True,'no_error_bars_or_independent_replicate_claim':True}
    (OUT/'FIGURE_GENERATION.json').write_text(json.dumps(proof,indent=2))
    print(json.dumps(proof))

if __name__=='__main__':main()
