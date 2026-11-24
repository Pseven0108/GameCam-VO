"""Render offline review figures from verified analysis tables; no RGB payloads."""
import csv
import os
from pathlib import Path

os.environ['CUDA_VISIBLE_DEVICES']=''
os.environ['MPLBACKEND']='Agg'

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FixedLocator, FuncFormatter, MaxNLocator
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'figures'
BRANCH='FIXED_K_NATIVE_RESIZE'
MODELS=('DROID-SLAM','DROID-W')
ENV=('Day','Sunset','Rain','Night','Snow')
COLOR=('#176B87','#B64B36')
INK='#20303C'
GRAY='#596675'
TYPES={'K':'KEYFRAME','F':'FILLED_FRAME'}
KINDS=('KK','KF','FK','FF')

mpl.rcParams.update({'font.family':['Arial','DejaVu Sans'], 'font.size':8.5,
    'axes.labelsize':8.3, 'axes.titlesize':9.5, 'axes.titleweight':'bold',
    'axes.labelcolor':INK, 'axes.edgecolor':'#A3ADB5', 'axes.linewidth':.7,
    'xtick.color':GRAY, 'ytick.color':GRAY, 'xtick.labelsize':7.7, 'ytick.labelsize':7.7,
    'axes.spines.top':False, 'axes.spines.right':False, 'text.color':INK, 'grid.color':'#E4E9ED',
    'legend.frameon':False, 'savefig.facecolor':'white'})


def read(name):
    with (ROOT/name).open(encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))


def key_legend():
    return [Line2D([0],[0],marker=m,linestyle='None',color=c,label=name,markersize=4.8)
            for name,c,m in zip(MODELS,COLOR,('o','s'))]


def save(fig,name):
    fig.canvas.draw()
    extent=fig.bbox
    for item in [*fig.texts,*fig.legends]:
        bb=item.get_window_extent(fig.canvas.get_renderer())
        if bb.x0 < -1 or bb.y0 < -1 or bb.x1 > extent.x1+1 or bb.y1 > extent.y1+1:
            raise ValueError(f'figure content would be clipped: {name} {item}')
    fig.savefig(OUT/name,dpi=230)
    print(f'Wrote {name}',flush=True)
    plt.close(fig)


def val007():
    table=read('VAL007_FRAME_SERIES.csv')
    sections={(int(x['first_rgb']),int(x['last_rgb']),x['model']):x for x in read('VAL007_CASE_INTERVALS.csv')}
    for x in read('VAL007_ANCHOR_INTERVALS.csv'):
        key=(int(x['first_rgb']),int(x['last_rgb']),x['model'])
        if key[:2] in {(312,328),(299,353)}:
            assert key not in sections
            sections[key]=x
    assert len(sections)==8
    fig=plt.figure(figsize=(7.35,5.8),layout=None)
    fig.text(.095,.957,'val_007: compression is already in the keyframe anchors',fontsize=14,weight='bold')
    fig.text(.095,.915,'VIPER Validation  |  Night  |  fixed K  |  stride 1  |  complete 487-frame export',color=GRAY)
    grid=fig.add_gridspec(2,2,left=.115,right=.963,bottom=.22,top=.81,hspace=.58,wspace=.45,
                          height_ratios=(1.08,1.02))
    ax,bx=fig.add_subplot(grid[0,0]),fig.add_subplot(grid[0,1]); cx=fig.add_subplot(grid[1,:])
    for j,(m,c,mark) in enumerate(zip(MODELS,COLOR,('o','s'))):
        series=[x for x in table if x['model']==m]
        idx=np.array([int(x['rgb_id']) for x in series])
        assert np.array_equal(idx,np.arange(1,488))
        err=np.array([float(x['translation_error_game_units']) for x in series])
        bx.plot(idx,err,lw=1.25,color=c,linestyle=('--','-')[j],zorder=3)
        selection=[x for x in series if 299<=int(x['rgb_id'])<=353]
        if j==0:
            gt=np.array([[float(x['gt_x']),float(x['gt_z'])] for x in selection]); gt-=gt[0].copy()
        xy=np.array([[float(x['aligned_x']),float(x['aligned_z'])] for x in selection]); xy-=xy[0].copy()
        ax.plot(*xy.T,color=c,lw=1.2,linestyle=('--','-')[j],zorder=3+j)
        key=[i for i,x in enumerate(selection) if x['keyframe']=='True']
        ax.scatter(*xy[key].T,c=c,s=11,marker=mark,zorder=5+j,linewidths=.35,edgecolors='white')
        if j==1:
            a,b=xy[[312-299,328-299]]
            ax.scatter(*a,c=c,s=23,marker='s',edgecolors='white',linewidths=.45,zorder=8)
            ax.annotate('312 and 328',xy=(a+b)/2,xytext=(11,23),textcoords='offset points',
                        ha='left',fontsize=7.7,color=c,arrowprops=dict(arrowstyle='-',color=c,lw=.75))
    ax.plot(*gt.T,color=INK,lw=1.05,label='GT',alpha=.85,zorder=2)
    ax.set_title('a   Local X–Z displacement',loc='left',pad=7)
    ax.set(xlabel='ΔX from RGB 299 (game units)',ylabel='ΔZ (game units)',aspect='equal')
    ax.grid(lw=.55)
    bx.axvspan(299,353,color='#D6E3E9',zorder=0)
    bx.text(326,.95,'299–353',transform=bx.get_xaxis_transform(),ha='center',va='top',fontsize=7,color=GRAY)
    bx.set_title('b   Position error over time',loc='left',pad=7)
    bx.set(xlabel='Original RGB ID',ylabel='Aligned position error (game units)',xlim=(1,487),ylim=(0,None))
    bx.xaxis.set_major_locator(MaxNLocator(5)); bx.yaxis.set_major_locator(MaxNLocator(4)); bx.grid(axis='y',lw=.65)

    targets=((309,325),(301,353),(312,328),(299,353))
    bar_y=np.arange(4)[::-1]; delta=.145
    for k,(a,b) in enumerate(targets):
        y=bar_y[k]
        if k==2:
            cx.axhspan(y-.42,y+.42,color='#F7EDEA',zorder=0)
        for j,(m,c) in enumerate(zip(MODELS,COLOR)):
            q=sections[a,b,m]; ratio=float(q['scaled_displacement_ratio']); dy=delta if j==0 else -delta
            cls=q['endpoint_type'].replace('KEYFRAME','K').replace('FILLED_FRAME','F').replace('->','→')
            cx.barh(y+dy,ratio,height=.24,color=c,zorder=4,alpha=.9)
            cx.text(ratio+.014,y+dy,f'{ratio:.3f}  {cls}',va='center',color=c,fontsize=7.6,
                    weight='bold' if k==2 and j==1 else 'normal')
    cx.axvline(1,color=INK,lw=.85,ls=(0,(3,2)),zorder=5)
    cx.set_title('c   Estimated endpoint displacement relative to GT',loc='left',pad=7)
    cx.set(xlim=(0,1.24),ylim=(-.55,3.55),yticks=bar_y,
           yticklabels=[f'{a} → {b}' for a,b in targets],xlabel='Displacement ratio  (GT = 1.0)')
    cx.grid(axis='x',lw=.6); cx.tick_params(axis='y',length=0)
    legend=[Line2D([0],[0],color=INK,label='GT',lw=1.05),
            *[Line2D([0],[0],color=c,marker=m,label=model,lw=1.2,markersize=4.3,linestyle=ls)
              for model,c,m,ls in zip(MODELS,COLOR,('o','s'),('--','-'))]]
    fig.legend(handles=legend,loc='lower left',bbox_to_anchor=(.104,.108),ncol=3,fontsize=8.4)
    fig.text(.115,.067,'Markers: retained keyframes. K = keyframe; F = filled. Ratios use the original segment scale.',color=GRAY,fontsize=7.8)
    fig.text(.115,.037,'Panel a subtracts each curve’s own RGB 299 position to show motion. No local alignment was fitted.',color=GRAY,fontsize=7.8)
    save(fig,'VAL007_KEYFRAME_COMPRESSION.png')


def matched_board(rpe):
    rows=read('RPE_ENDPOINT_ENVIRONMENT_PAIRED.csv' if rpe else 'POSE_ERROR_ENVIRONMENT_PAIRED.csv')
    categories=KINDS if rpe else ('K','F')
    measures=('translation','rotation')
    def find(env,kind,metric):
        cand=[q for q in rows if q['calibration_branch']==BRANCH and q['environment']==env and q['metric']==metric]
        if rpe:
            kt='->'.join(TYPES[p] for p in kind)
            cand=[q for q in cand if q['contrast']=='W_MINUS_SLAM_MATCHED_RGB' and q['offset']=='60' and q['slam_type']==q['wild_type']==kt]
        else:
            cand=[q for q in cand if q['population']=='MATCHED' and q['temporal_third']=='all' and q['frame_type']==TYPES[kind]]
        if len(cand)>1:
            raise ValueError(f'duplicate plot row: {env}/{kind}/{metric}')
        return cand[0] if cand else None
    data={(e,k,m):find(e,k,m) for e in ENV for k in categories for m in measures}
    fig,axes=plt.subplots(len(categories),2,figsize=(7.35,8.9 if rpe else 5.8),squeeze=False)
    fig.subplots_adjust(left=.174,right=.96,top=.84 if rpe else .79,bottom=.15 if rpe else .218,
                        wspace=.43,hspace=.72 if rpe else .70)
    fig.text(.12,.955,'Matched-endpoint RPE at 60 frames' if rpe else 'Pose error at shared frame types',fontsize=14,weight='bold')
    fig.text(.12,.919,'Fixed K  |  45 source sequences  |  sequence RMSE medians  |  same RGB IDs',fontsize=8.5,color=GRAY)
    handles=key_legend(); handles.extend([Line2D([0],[0],color='#905A32',marker='*',linestyle='None',label='n < 5',markersize=6)])
    fig.legend(handles=handles,ncol=3,loc='lower left',bbox_to_anchor=(.109,.855 if rpe else .815))
    for j,metric in enumerate(measures):
        values=[float(q[s+'_seq_rmse_median']) for (e,k,m),q in data.items() if m==metric and q and int(q['paired_sequences'])
                for s in ('left','right')]
        step=np.floor(np.log10(min(values))); top=np.ceil(np.log10(max(values))); ticks=10.**np.arange(step,top+1)
        xl=(max(ticks[0],min(values)/1.65),min(ticks[-1],max(values)*1.65))
        for i,kind in enumerate(categories):
            a=axes[i,j]; labels=[]
            for y,e in enumerate(ENV):
                q=data[e,kind,metric]; n=int(q['paired_sequences']) if q else 0
                labels.append(f'{e}   {n}'+('*' if 0<n<5 else ''))
                if not n:
                    a.text(.06,y,'no pairs',transform=a.get_yaxis_transform(),va='center',fontsize=7.5,color=GRAY)
                    continue
                left,right=(float(q[s+'_seq_rmse_median']) for s in ('left','right'))
                if min(left,right)<=0:
                    raise ValueError('log axis requires positive values')
                a.plot([left,right],[y,y],color='#B1BBC4',lw=.9,zorder=2)
                a.scatter(left,y,marker='o',color=COLOR[0],s=16,zorder=3,edgecolor='white',linewidth=.4)
                a.scatter(right,y,marker='s',color=COLOR[1],s=16,zorder=4,edgecolor='white',linewidth=.4)
            unit='game units' if j==0 else 'deg'
            letter='abcdefgh'[2*i+j]
            subtitle=' → '.join(kind) if rpe else ('Keyframe' if kind=='K' else 'Filled frame')
            a.set(xscale='log',xlim=xl,ylim=(4.6,-.6),
                  yticks=np.arange(5),yticklabels=labels)
            a.set_title(f'{letter}   {subtitle}  ·  {metric.title()}',loc='left',pad=4)
            a.grid(axis='x',which='major',lw=.7); a.tick_params(axis='y',length=0)
            for label,e in zip(a.get_yticklabels(),ENV):
                q=data[e,kind,metric]
                if q and 0<int(q['paired_sequences'])<5:
                    label.set_color('#905A32')
            kept=[x for x in ticks if xl[0]<=x<=xl[1]]
            if len(kept)<2:
                kept=list(np.geomspace(*xl,3))
            a.xaxis.set_major_locator(FixedLocator(kept)); a.xaxis.set_major_formatter(FuncFormatter(lambda x,_:f'{x:g}'))
            a.minorticks_off()
            if i==len(categories)-1:
                a.set_xlabel(f'RMSE ({unit}), log scale')
    fig.text(.12,.061 if rpe else .085,'n is the number of paired source sequences in each row; * marks sparse support.',color=GRAY,fontsize=8)
    fig.text(.12,.036 if rpe else .052,'Different frame or endpoint classes can use different sequences and pairs.',color=GRAY,fontsize=8)
    save(fig,'ENVIRONMENT_MATCHED_RPE60.png' if rpe else 'ENVIRONMENT_MATCHED_POSE.png')


if __name__=='__main__':
    OUT.mkdir(exist_ok=True)
    val007()
    matched_board(False)
    matched_board(True)
