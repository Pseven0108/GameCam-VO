"""Risk ranking and calibration are separate operations, with sequence guards."""
import numpy as np
from scipy.optimize import minimize
from scipy.special import expit
from scipy.stats import rankdata,spearmanr
from sklearn.isotonic import IsotonicRegression

METHODS=['NativeOnly','FlipOnly','RankFusion','MaxFusion','RankW25','RankW75']
CORE=METHODS[:4]

def percentile(a):
    a=np.asarray(a,dtype=np.float64)
    if not a.size or not np.isfinite(a).all():raise ValueError('Finite nonempty entire-image score domain required')
    return ((rankdata(a,method='average')-.5)/a.size).reshape(a.shape)

def scores(confidence,flip):
    native=-np.asarray(confidence,dtype=np.float64);flip=np.asarray(flip,dtype=np.float64)
    if native.shape!=flip.shape:raise ValueError('Input pixel grids differ')
    n,f=percentile(native),percentile(flip)
    return {'NativeOnly':native,'FlipOnly':flip,'RankFusion':.5*n+.5*f,'MaxFusion':np.maximum(n,f),
            'RankW25':.25*n+.75*f,'RankW75':.75*n+.25*f},n,f

def split_guard(calibration_sequence,evaluation_sequence):
    if not calibration_sequence or not evaluation_sequence or calibration_sequence==evaluation_sequence:raise ValueError('Calibration/evaluation sequence leakage')

def fit_logistic(x,y,calibration_sequence='0000',evaluation_sequence='0001'):
    split_guard(calibration_sequence,evaluation_sequence)
    x=np.asarray(x,dtype=float);y=np.asarray(y,dtype=float)
    if x.shape!=y.shape or x.ndim!=1 or not len(x) or not np.isfinite(x).all() or not np.isin(y,[0,1]).all():raise ValueError('Invalid calibration vectors')
    mean=float(x.mean());sd=float(x.std());sd=sd if sd>0 else 1.
    z=(x-mean)/sd;prevalence=float(y.mean())
    if not 0<prevalence<1:raise ValueError('Calibration event needs both classes')
    def objective(t):
        logits=t[0]*z+t[1];p=expit(logits)
        return float(np.mean(np.logaddexp(0,logits)-y*logits)),np.array([np.mean((p-y)*z),np.mean(p-y)])
    fit=minimize(objective,[0.,np.log(prevalence/(1-prevalence))],jac=True,bounds=[(0,None),(None,None)],method='L-BFGS-B',options={'maxiter':200,'ftol':1e-12})
    if not fit.success:raise RuntimeError('Monotone logistic failed: '+str(fit.message))
    return {'mean':mean,'sd':sd,'slope':float(fit.x[0]),'intercept':float(fit.x[1]),'n':len(x),'calibration_prevalence':prevalence,'calibration_sequence':calibration_sequence,'evaluation_sequence':evaluation_sequence,'fit_on_evaluation':False,'converged':True}

def logistic_predict(x,model):
    v=model['slope']*(np.asarray(x)-model['mean'])/model['sd']+model['intercept']
    return expit(v),v

def probability_metrics(p,logits,y):
    p=np.asarray(p,dtype=float);v=np.asarray(logits,dtype=float);y=np.asarray(y,dtype=float)
    if not(p.shape==v.shape==y.shape) or not np.isfinite(p).all() or not np.isfinite(v).all() or ((p<0)|(p>1)).any():raise ValueError('Invalid probability fields')
    bins=np.minimum((10*p).astype(int),9);ece=0.;rows=[]
    for i in np.unique(bins):
        own=bins==i;mp=float(p[own].mean());my=float(y[own].mean());ece+=float(own.mean())*abs(mp-my)
        rows.append({'bin':int(i),'n':int(own.sum()),'predicted_probability':mp,'observed_event_frequency':my})
    return {'Brier':float(np.mean((p-y)**2)),'NLL':float(np.mean(np.logaddexp(0,v)-y*v)),'ECE10':ece,'p_min':float(p.min()),'p_max':float(p.max())},rows

def fit_regression(x,error,calibration_sequence='0000',evaluation_sequence='0001'):
    split_guard(calibration_sequence,evaluation_sequence)
    x=np.asarray(x,dtype=float);e=np.asarray(error,dtype=float)
    if x.shape!=e.shape or x.ndim!=1 or not np.isfinite(x).all() or not np.isfinite(e).all() or (e<0).any():raise ValueError('Invalid AbsRel regression calibration')
    fit=IsotonicRegression(increasing=True,out_of_bounds='clip').fit(x,e)
    return fit,{'x_thresholds':fit.X_thresholds_.tolist(),'y_thresholds':fit.y_thresholds_.tolist(),'calibration_sequence':calibration_sequence,'evaluation_sequence':evaluation_sequence,'fit_on_evaluation':False,'n':len(x),'target':'AbsRel after calibration-only scale'}

def error_metrics(predicted_error,error):
    delta=np.asarray(predicted_error,dtype=float)-np.asarray(error,dtype=float)
    return {'AbsRel_prediction_MAE':float(np.mean(np.abs(delta))),'AbsRel_prediction_RMSE':float(np.sqrt(np.mean(delta**2)))}

def correlation(x,y):
    return float(spearmanr(np.asarray(x).ravel(),np.asarray(y).ravel()).statistic) if np.ptp(x)>0 and np.ptp(y)>0 else None
