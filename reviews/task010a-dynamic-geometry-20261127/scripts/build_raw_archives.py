"""Full float-array delivery in bounded GitHub Release assets, without raw RGB/GT."""
import csv
import hashlib
import io
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'experiments/TASK010-A'
DEST=ROOT/'deliveries/TASK010A_RAW'


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
    return h.hexdigest()


def main():
    DEST.mkdir(parents=True,exist_ok=True);assets=[]
    groups={'GMOS':['gmos'],'PI3MOS':['pi3mos'],'GEOMOTION_CVPR':['geomotion'],
        'GEOMOTION_FULL':['geomotion_full'],'FLOW_GEOMETRY':['flows'],
        'DEPTH_PRIORS_STATIC':['priors','priors_blend','static']}
    for name,folders in groups.items():
        files=sorted(p for folder in folders for p in (TASK/'outputs'/folder).rglob('*') if p.is_file())
        if not files:raise RuntimeError('Missing complete raw group '+name)
        if any('rgb' in p.parts or p.name=='offline_gt.npz' or p.suffix in ['.pth','.pt','.safetensors'] for p in files):
            raise RuntimeError('Raw data/weights must not enter review assets')
        pairs=[(p,p.relative_to(TASK/'outputs').as_posix()) for p in files]
        if name=='DEPTH_PRIORS_STATIC':
            # Reused inputs are still part of full evidence, but the historical
            # offline GT and RGB must not be redistributed with predicted fields.
            roster=json.loads((TASK/'private/DATA_MANIFEST.json').read_text())
            old=Path(next(d['prior_cache'] for d in roster if d['name']=='night007_dev'))
            for p in sorted(old.iterdir()):
                if p.is_file() and (p.name.startswith(('depth_','feature_')) and p.suffix=='.npy' or p.name=='receipt.json'):
                    pairs.append((p,'priors/night007_dev_reused/'+p.name))
            old_static=Path('D:/aaa/GameCam-VO-TASK009/experiments/TASK009/outputs/mdtracker_metric_32f_160x280_fp32_r1')
            for p in sorted(old_static.iterdir()):
                if p.is_file() and (p.suffix=='.npz' or p.name in ['receipt.json','input_manifest.json','statistics.json']):
                    pairs.append((p,'static/night007_dev_reused/'+p.name))
        records=[{'path':alias,'bytes':p.stat().st_size,'sha256':digest(p)} for p,alias in pairs]
        manifest=io.StringIO();w=csv.DictWriter(manifest,fieldnames=['path','bytes','sha256']);w.writeheader();w.writerows(records)
        archive=DEST/f'TASK010A_RAW_{name}.zip'
        if archive.exists():raise RuntimeError('Raw archive already exists; never silently overwrite')
        # NPZ arrays are already compressed. STORE avoids lossy conversion and
        # unnecessary recompression while keeping each asset below2GiB.
        with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_STORED,allowZip64=True) as z:
            for (p,_),r in zip(pairs,records):z.write(p,r['path'])
            z.writestr('SHA256_MANIFEST.csv',manifest.getvalue())
            z.writestr('README.txt','Full original float outputs and receipts. No model weights, raw RGB or evaluation GT. Internal SHA manifest excludes itself.\n')
        if archive.stat().st_size>=2*1024**3:raise RuntimeError('Asset exceeds bounded release size')
        with zipfile.ZipFile(archive) as z:
            if z.testzip() is not None:raise RuntimeError('Raw archive CRC failure')
            for r in records:
                if hashlib.sha256(z.read(r['path'])).hexdigest()!=r['sha256']:raise RuntimeError('Raw archive SHA failure')
        sha=digest(archive);archive.with_suffix('.zip.sha256').write_text(sha+'  '+archive.name+'\n')
        asset={'name':archive.name,'source':str(archive),'bytes':archive.stat().st_size,'sha256':sha,
            'file_count':len(records),'zip_crc':'PASS','internal_sha256':'ALL_PASS',
            'browser_download_url':'https://github.com/Pseven0108/GameCam-VO/releases/download/task010a-research-20261127/'+archive.name}
        assets.append(asset);print('RAW_ARCHIVE_READY',name,asset['bytes'],flush=True)
    (TASK/'private/RAW_ASSET_UPLOAD_MANIFEST.json').write_text(json.dumps(assets,indent=2))
    public=[{k:v for k,v in a.items() if k!='source'} for a in assets]
    (TASK/'09_reproducibility/RAW_EVIDENCE_ASSET_INDEX.json').write_text(json.dumps(public,indent=2))
    print('All original prediction/flow/prior arrays packaged; historical data and weights excluded')


if __name__=='__main__':main()
