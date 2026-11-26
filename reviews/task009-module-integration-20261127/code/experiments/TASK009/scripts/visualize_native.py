"""Render saved real native BA correspondences and cached prior diagnostics."""
import argparse
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[3]
ORIGINAL=Path(r'D:\aaa\GameCam-VO')
RGB=ORIGINAL/'experiments/task008_pi3mos/retrieved/outputs/night007/original_rgb'
PI3=ORIGINAL/'experiments/task008_pi3mos/retrieved/outputs/night007/A/predictions'


def main():
    p=argparse.ArgumentParser();p.add_argument('--runs',nargs='+',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    fig,axes=plt.subplots(len(a.runs),2,figsize=(11,3*len(a.runs)),squeeze=False,constrained_layout=True)
    for row,run in enumerate(a.runs):
        p=sorted((run/'native_ba_observations').glob('*.npz'))[-1]
        with np.load(p,allow_pickle=False) as z:
            source,target=int(z['source_rgb']),int(z['target_rgb'])
            xy=z['target'][::3,::3].reshape(-1,2)*8
            weight=z['weight'][::3,::3].mean(-1).flatten()
            ax=axes[row,0];ax.imshow(Image.open(RGB/f'{source:05d}.jpg').resize((384,216)))
            yy,xx=np.meshgrid(np.arange(0,27,3)*8,np.arange(0,48,3)*8,indexing='ij')
            ax.scatter(xx,yy,s=6,c='lime');ax.set_title(f'{run.name}: source RGB{source}',fontsize=9)
            ax=axes[row,1];ax.imshow(Image.open(RGB/f'{target:05d}.jpg').resize((384,216)))
            valid=np.isfinite(xy).all(-1)&(xy[:,0]>=0)&(xy[:,0]<384)&(xy[:,1]>=0)&(xy[:,1]<216)
            ax.scatter(xy[valid,0],xy[valid,1],s=9,c=weight[valid],cmap='viridis',vmin=0,vmax=1)
            ax.set_title(f'Actual predicted target RGB{target}; color = BA input weight',fontsize=9)
        for ax in axes[row]:ax.set_xlim(0,383);ax.set_ylim(215,0);ax.axis('off')
    fig.suptitle('Saved DROID native correspondences; before native UBA weighting',fontsize=12)
    fig.savefig(a.output/'native_correspondences.png',dpi=150);plt.close(fig)
    ids=[301,312,325,332]
    fig,axes=plt.subplots(4,4,figsize=(14,9),constrained_layout=True)
    for i,fid in enumerate(ids):
        with np.load(PI3/f'{fid:05d}.npz',allow_pickle=False) as z:
            dynamic=z['dynamic_probability_model'];confidence=z['confidence_model'];depth=z['depth_model']
        im=Image.open(RGB/f'{fid:05d}.jpg').resize((384,216))
        axes[i,0].imshow(im);axes[i,0].set_title(f'RGB{fid}')
        axes[i,1].imshow(dynamic,cmap='magma',vmin=0,vmax=1);axes[i,1].set_title('Pi3 dynamic probability')
        lo,hi=np.percentile(confidence[np.isfinite(confidence)],[1,99])
        axes[i,2].imshow(confidence,cmap='viridis',vmin=lo,vmax=hi);axes[i,2].set_title('Pi3 confidence (uncalibrated)')
        valid=np.isfinite(depth)&(depth>0)
        vmax=np.percentile(depth[valid],95) if valid.any() else 1
        axes[i,3].imshow(np.where(valid,depth,np.nan),cmap='turbo',vmin=0,vmax=vmax);axes[i,3].set_title('Auxiliary z; not metric GT')
        for ax in axes[i]:ax.axis('off')
    fig.savefig(a.output/'prior_diagnostics.png',dpi=140);plt.close(fig)


if __name__=='__main__':main()
