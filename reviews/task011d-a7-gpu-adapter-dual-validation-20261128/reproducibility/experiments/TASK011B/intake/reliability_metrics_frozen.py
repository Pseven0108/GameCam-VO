"""Independent CPU evaluation. No SLAM, model import, training or pseudo GT."""
from dataclasses import dataclass
from typing import Tuple
import numpy as np
from scipy.stats import spearmanr,pearsonr,rankdata


class AdmissionError(ValueError):pass


@dataclass(frozen=True)
class GTAdmission:
    independent_depth_gt: bool
    pixel_alignment_verified: bool
    depth_convention_verified: bool
    units_matched: bool
    dataset_id: str
    depth_unit: str

    def require(self):
        if not all((self.independent_depth_gt,self.pixel_alignment_verified,self.depth_convention_verified,self.units_matched)):
            raise AdmissionError('Independent GT, alignment, depth convention and matched units are all required')
        if not self.dataset_id or self.depth_unit in ('','UNKNOWN','UNVERIFIED'):
            raise AdmissionError('GT identity/unit unspecified')


def vector(x,name):
    a=np.asarray(x,dtype=np.float64).reshape(-1)
    if a.size==0 or not np.isfinite(a).all():raise ValueError(name+' must be finite and nonempty')
    return a


def depth_errors(pred,gt,mask,admission,epsilon=1e-12):
    admission.require()
    p=np.asarray(pred,dtype=np.float64);g=np.asarray(gt,dtype=np.float64);m=np.asarray(mask,dtype=bool)
    if not(p.shape==g.shape==m.shape):raise ValueError('Pixel grids differ')
    if not np.isfinite(epsilon) or epsilon<0:raise ValueError('Invalid error epsilon')
    valid_gt=m&np.isfinite(g)&(g>0)
    bad_pred=valid_gt&(~np.isfinite(p)|(p<=0))
    if bad_pred.any():raise AdmissionError('Invalid predictions on valid GT; retain failure instead of silently filtering')
    if not valid_gt.any():raise AdmissionError('No valid GT pixels')
    return np.abs(p[valid_gt]-g[valid_gt])/(g[valid_gt]+epsilon),np.abs(np.log(p[valid_gt])-np.log(g[valid_gt])),valid_gt


def binary_ranking(event,risk):
    y=np.asarray(event)
    s=vector(risk,'risk')
    if y.ndim!=1 or y.shape!=s.shape or not np.isin(y,[0,1,False,True]).all():raise ValueError('Invalid binary event')
    y=y.astype(bool);n=y.size;p=int(y.sum());neg=n-p
    if p==0 or neg==0:
        return {'AUROC':None,'AUPRC':None,'positive_count':p,'negative_count':neg,'status':'SINGLE_CLASS_UNDEFINED'}
    ranks=rankdata(s,method='average')
    auc=(ranks[y].sum()-p*(p+1)/2)/(p*neg)
    order=np.argsort(-s,kind='stable');ss=s[order];yy=y[order]
    ends=np.r_[np.flatnonzero(ss[1:]!=ss[:-1]),n-1]
    tp=np.cumsum(yy)[ends];fp=(ends+1)-tp
    recall=tp/p;precision=tp/(tp+fp)
    ap=np.sum(np.diff(np.r_[0.,recall])*precision)
    return {'AUROC':float(auc),'AUPRC':float(ap),'positive_count':p,'negative_count':neg,'status':'OK'}


def risk_coverage(error,risk):
    """Finite-sample, tie-averaged risk: constant risk is EXACTLY random.

    k retained pixels, coverage k/N. Within each score tie use expected prefix
    sum under uniform tie permutation; no arbitrary input-index advantage.
    Add the right limit at coverage=0 only to define trapezoidal integration.
    AUSE/AURG here use raw mean AbsRel, not a normalized or RMSE curve.
    """
    e=vector(error,'error');s=vector(risk,'risk')
    if e.shape!=s.shape or (e<0).any():raise ValueError('Invalid errors/risk')
    order=np.argsort(s,kind='stable');ss=s[order];ee=e[order]
    ends=np.r_[np.flatnonzero(ss[1:]!=ss[:-1])+1,len(ss)]
    starts=np.r_[0,ends[:-1]];prefix=np.empty(len(e));total=0.
    for a,b in zip(starts,ends):
        prefix[a:b]=total+np.arange(1,b-a+1)*ee[a:b].mean();total+=ee[a:b].sum()
    k=np.arange(1,len(e)+1)
    curve=prefix/k;oracle=np.cumsum(np.sort(e))/k;random=np.full(len(e),e.mean())
    coverage=np.r_[0.,k/len(e)]
    curve=np.r_[curve[0],curve];oracle=np.r_[oracle[0],oracle];random=np.r_[random[0],random]
    integrate=getattr(np,'trapezoid',np.trapz)
    return {'coverage':coverage,'risk':curve,'oracle':oracle,'random':random,
            'AUSE_raw_AbsRel':float(integrate(curve-oracle,coverage)),
            'AURG_raw_AbsRel':float(integrate(random-curve,coverage)),
            'risk_convention':'tie-averaged finite-sample raw mean AbsRel, k/N coverage; right limit at zero'}


def correlation(error,score):
    e=vector(error,'error');s=vector(score,'score')
    if e.shape!=s.shape:raise ValueError('Shapes differ')
    if np.ptp(e)==0 or np.ptp(s)==0:
        return {'Spearman':None,'Pearson':None,'status':'CONSTANT_UNDEFINED'}
    return {'Spearman':float(spearmanr(e,s).statistic),'Pearson':float(pearsonr(e,s).statistic),'status':'OK'}


def evaluate_signal(error,raw_signal,direction='higher_is_risk',thresholds=(0.1,0.2,0.5)):
    e=vector(error,'error');raw=vector(raw_signal,'raw signal')
    if e.shape!=raw.shape:raise ValueError('Pixel count differs')
    if direction not in ('higher_is_risk','higher_is_confidence'):raise ValueError('Direction must be declared')
    risk=raw if direction=='higher_is_risk' else -raw
    rc=risk_coverage(e,risk)
    return {'raw_signal_direction':direction,'error_vs_raw':correlation(e,raw),
            'error_vs_declared_risk':correlation(e,risk),
            'thresholds':{str(t):binary_ranking(e>t,risk) for t in thresholds},
            'AUSE_raw_AbsRel':rc['AUSE_raw_AbsRel'],'AURG_raw_AbsRel':rc['AURG_raw_AbsRel'],
            'calibration_ECE':None,'ECE_status':'NOT_A_PROBABILITY_NO_CALIBRATION',
            'risk_curve':rc}


def reliability_bins(error,raw_signal,bins=10):
    e=vector(error,'error');s=vector(raw_signal,'score')
    if e.shape!=s.shape or not isinstance(bins,int) or bins<1:raise ValueError('Invalid bins')
    edges=np.unique(np.quantile(s,np.linspace(0,1,bins+1)))
    if len(edges)==1:edges=np.array([edges[0]-0.5,edges[0]+0.5])
    ids=np.searchsorted(edges[1:-1],s,side='right')
    return [{'bin':int(i),'n':int((ids==i).sum()),'raw_score_mean':float(s[ids==i].mean()),
             'mean_error':float(e[ids==i].mean()),'error_gt_0_2_rate':float((e[ids==i]>0.2).mean()),
             'is_probability_calibration':False} for i in np.unique(ids)]


def probability_calibration(prob,event,*,fitted_on_sequences,test_sequences,event_definition,bins=10):
    if not isinstance(bins,int) or isinstance(bins,bool) or bins<1:raise ValueError('Positive bin count required')
    if not event_definition or not fitted_on_sequences or not test_sequences:
        raise AdmissionError('Explicit event and sequence-separated calibration required')
    if set(fitted_on_sequences)&set(test_sequences):raise AdmissionError('Calibration/test sequence leakage')
    p=vector(prob,'probability');y=np.asarray(event)
    if y.shape!=p.shape or not np.isin(y,[0,1]).all() or (p<0).any() or (p>1).any():raise ValueError('Invalid probabilities/event')
    ids=np.minimum((p*bins).astype(int),bins-1);rows=[];ece=0.
    for i in np.unique(ids):
        own=ids==i;conf=float(p[own].mean());freq=float(y[own].mean())
        ece+=own.mean()*abs(conf-freq);rows.append({'bin':int(i),'n':int(own.sum()),'probability_mean':conf,'event_rate':freq})
    return {'ECE':float(ece),'event_definition':event_definition,'bins':rows}


def flip_disagreement(original,flipped_prediction,epsilon=1e-6):
    a=np.asarray(original,dtype=np.float64);b=np.asarray(flipped_prediction,dtype=np.float64)
    if a.shape!=b.shape or a.ndim!=2:raise ValueError('TTA grids differ')
    b=b[:,::-1]
    if not np.isfinite(a).all() or not np.isfinite(b).all() or (a<=0).any() or (b<=0).any():
        raise AdmissionError('Invalid TTA depth; do not replace with confident zeros')
    return np.abs(a-b)/(a+epsilon),np.abs(np.log(a+epsilon)-np.log(b+epsilon))


def entropy_from_logits(logits):
    a=np.asarray(logits,dtype=np.float64)
    if a.ndim<2 or a.shape[0]<2 or not np.isfinite(a).all():raise ValueError('Finite depth-bin logits required')
    z=a-np.max(a,axis=0,keepdims=True)
    exp=np.exp(z);p=exp/exp.sum(axis=0,keepdims=True)
    logp=np.log(np.maximum(p,np.finfo(float).tiny))
    return -(p*logp).sum(axis=0)/np.log(a.shape[0])


def depth_bin_statistics(logits,anchors):
    a=np.asarray(logits,dtype=np.float64);d=vector(anchors,'depth anchors')
    if a.ndim<2 or a.shape[0]!=len(d) or (d<=0).any() or not np.all(np.diff(d)>0):
        raise ValueError('Actual positive sorted anchors required; bin count is not assumed')
    entropy=entropy_from_logits(a)*np.log(len(d))
    z=a-a.max(axis=0,keepdims=True);p=np.exp(z);p/=p.sum(axis=0,keepdims=True)
    ds=d.reshape((-1,)+(1,)*(a.ndim-1));mean=(p*ds).sum(axis=0)
    variance=(p*(ds-mean)**2).sum(axis=0)
    return {'entropy':entropy,'entropy_normalized':entropy/np.log(len(d)),
            'variance':variance,'mean_initial_depth':mean,'max_probability':p.max(axis=0),
            'effective_bins':np.exp(entropy),'bin_count':len(d)}


def unpad_grid(grid,pad_tblr):
    a=np.asarray(grid)
    if a.ndim!=2 or len(pad_tblr)!=4:raise ValueError('2D grid and four padding values required')
    t,b,l,r=pad_tblr
    if any(not isinstance(x,(int,np.integer)) or x<0 for x in (t,b,l,r)) or t+b>=a.shape[0] or l+r>=a.shape[1]:
        raise ValueError('Invalid padding')
    return a[t:a.shape[0]-b,l:a.shape[1]-r]


def preprocess_geometry(height,width,canonical=(616,1064)):
    if height<=0 or width<=0:raise ValueError('Invalid image size')
    scale=min(canonical[0]/height,canonical[1]/width)
    hh,ww=int(height*scale),int(width*scale)
    dh,dw=canonical[0]-hh,canonical[1]-ww
    return {'input_hw':[height,width],'scaled_hw':[hh,ww],'pad_tblr':[dh//2,dh-dh//2,dw//2,dw-dw//2],
            'canonical_hw':list(canonical),'depth_restore':'unpad then bicubic align_corners=False; fx/1000 then clamp0..300',
            'confidence_restore':'unpad same grid then bilinear align_corners=False; no depth-unit scaling; raw retained'}


def supervised_confidence_loss(conf,pred,gt,mask):
    """Finite-positive-target transcription for auditing mask exclusion, no training."""
    c=vector(conf,'confidence');p=vector(pred,'prediction');g=vector(gt,'target');m=np.asarray(mask,dtype=bool)
    if c.shape!=p.shape or p.shape!=g.shape or m.shape!=g.shape or (g<=0).any():raise ValueError('Finite positive target domain required')
    valid=(np.abs(g-p)<g)&m
    target=(1-np.abs((p-g)/g))*valid
    loss=np.sum(np.abs(c-target)*valid)/(valid.sum()+1e-6)
    return float(loss),target,valid


def grouped_bootstrap(values,groups,seed=43,repetitions=2000):
    """Equal-weight group macro mean; whole groups, never pixels, are resampled."""
    v=vector(values,'values');g=np.asarray(groups)
    if g.shape!=v.shape or repetitions<100:raise ValueError('Invalid groups/bootstrap count')
    ids=np.unique(g)
    if len(ids)<2:
        return {'mean':float(v.mean()),'lower95':None,'upper95':None,'groups':len(ids),
                'status':'INSUFFICIENT_GROUPS_NO_GENERALIZATION_INTERVAL'}
    macro=np.array([v[g==i].mean() for i in ids])
    rng=np.random.default_rng(seed)
    draws=macro[rng.integers(0,len(ids),size=(repetitions,len(ids)))].mean(axis=1)
    q=np.quantile(draws,[.025,.975])
    return {'mean':float(macro.mean()),'lower95':float(q[0]),'upper95':float(q[1]),
            'groups':len(ids),'status':'GROUP_BOOTSTRAP','seed':seed,'repetitions':repetitions}
