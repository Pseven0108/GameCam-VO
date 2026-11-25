"""CPU-only common comparison; retain R2's unchanged elementwise tolerance."""
import os,sys,pathlib,json,csv
os.environ['CUDA_VISIBLE_DEVICES']=''
sys.path.insert(0,r'C:\Users\Administrator\Documents\GameCam-VO-Task004CB-20261125\cpu_plot_dependencies')
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[1]
RECV=pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-TASK005B-R3-20261125-R1/expanded')
DATA=RECV/'results';OUT=ROOT/'04_analysis';OUT.mkdir(exist_ok=True)
FINAL=['dx_last','dz_last','poses','disps','uncertainties','temp_y_cdot','affine_weights']
def compare(a,b):
    a=np.asarray(a);b=np.asarray(b);assert a.shape==b.shape
    d=np.abs(a.astype('f8')-b.astype('f8'));tol=1e-6+1e-5*np.abs(a.astype('f8'))
    nbad=int(np.count_nonzero(d>tol));norm=float(np.linalg.norm(a.ravel().astype('f8')))
    result={'elements':int(a.size),'changed':int(np.count_nonzero(a!=b)),'violations':nbad,'max_abs':float(d.max(initial=0)),'rms':float(np.sqrt(np.mean(d*d))) if d.size else 0.,'rel_L2':float(np.linalg.norm(d.ravel())/(norm+1e-300)),'bitwise_equal':a.dtype==b.dtype and a.tobytes()==b.tobytes(),'PASS':nbad==0}
    if a.dtype==b.dtype==np.float32:
        ia=a.view(np.int32).astype('i8');ib=b.view(np.int32).astype('i8')
        oa=np.where(ia<0,-2147483648-ia,ia);ob=np.where(ib<0,-2147483648-ib,ib)
        result['max_ULP']=int(np.max(np.abs(oa-ob),initial=0))
    else:result['max_ULP']=''
    return result
def save_csv(name,rows):
    rows=list(rows);assert rows,name
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def save_json(name,x):(OUT/name).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def load(tag):
    with np.load(DATA/(tag+'.npz'),allow_pickle=False) as z:return {k:z[k] for k in z.files}
def dispersion(values):
    a=np.stack(values).astype('f8');spread=np.ptp(a,axis=0)
    return {'n_calls':len(values),'variable_elements':int(np.count_nonzero(spread)),'max_range':float(spread.max(initial=0)),'RMS_element_range':float(np.sqrt(np.mean(spread*spread))),'RMS_element_SD':float(np.sqrt(np.mean(np.var(a,axis=0,ddof=1))))}
