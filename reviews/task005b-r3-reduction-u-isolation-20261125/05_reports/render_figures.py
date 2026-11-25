import os,sys,pathlib,json,csv
os.environ['CUDA_VISIBLE_DEVICES']=''
sys.path.insert(0,r'C:\Users\Administrator\Documents\GameCam-VO-Task004CB-20261125\cpu_plot_dependencies')
import numpy as np,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=pathlib.Path(__file__).resolve().parents[1];OUT=ROOT/'05_reports/figures';OUT.mkdir(parents=True,exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':140})
def rows(name):
    with (ROOT/'04_analysis'/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def main():
    a=rows('ISOLATED_PAIRWISE_ERRORS.csv');fig,ax=plt.subplots(1,2,figsize=(10,3.5))
    for p,(kind,field,title) in zip(ax,[('jjj','Jjj_data','Isolated Jjj scatter'),('linear','J_linear','Isolated J_linear reduction')]):
        values=np.array([float(r['max_abs']) for r in a if r['kind']==kind and r['field']==field])
        p.plot(np.arange(1,len(values)+1),values,'o',ms=3,color='#176b9c',alpha=.7);p.set(xlabel='Descriptive pair index (shared calls)',ylabel='Maximum absolute difference',title=title);p.ticklabel_format(axis='y',style='sci',scilimits=(0,0));p.set_ylim(bottom=0);p.grid(axis='y',alpha=.2)
    fig.suptitle('16 fixed-input calls per kernel; all 120 pairs meet unchanged tolerance',fontsize=11);fig.tight_layout();fig.savefig(OUT/'ISOLATED_REDUCTION_VARIATION.png',bbox_inches='tight');plt.close(fig)
    a=rows('U_FEEDBACK_VARIABILITY_COMPARISON.csv');fig,ax=plt.subplots(1,2,figsize=(10,3.8))
    for p,field,title in zip(ax,['iter2_dx','iter2_dz'],['Second-round pose increment dx','Second-round disparity increment dz']):
        y=[];labels=[];colors=[]
        for impl in ['reference','paths']:
            r=next(r for r in a if r['implementation']==impl and r['field']==field)
            for mode,color in [('native','#b54631'),('fixed','#176b9c')]:y.append(float(r[mode+'_RMS_SD']));labels.append(impl+'\n'+mode+' U');colors.append(color)
        p.bar(np.arange(4),y,color=colors,width=.6);p.set_xticks(np.arange(4),labels);p.set_ylabel('RMS of elementwise sample SD (n=4)');p.set_title(title);p.ticklabel_format(axis='y',style='sci',scilimits=(0,0));p.set_ylim(bottom=0)
        for i,v in enumerate(y):
            if v==0:p.annotate('exactly 0',(i,0),xytext=(0,7),textcoords='offset points',ha='center',fontsize=9)
        p.grid(axis='y',alpha=.2)
    fig.suptitle('Fixed U preserves affine/temp updates; one sealed D0 BA context',fontsize=11);fig.tight_layout();fig.savefig(OUT/'U_FEEDBACK_SECOND_ROUND_VARIABILITY.png',bbox_inches='tight');plt.close(fig)
    print('Rendered 2 diagnostic figures')
if __name__=='__main__':main()
