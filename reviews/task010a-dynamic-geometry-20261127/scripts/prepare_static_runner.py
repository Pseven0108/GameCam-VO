"""Adapt the sealed MDTracker inference interface only to admitted input identities."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
text=Path('D:/aaa/GameCam-VO-TASK009/experiments/TASK009/scripts/run_mdtracker.py').read_text()
text=text.replace("ap=argparse.ArgumentParser();", "ap=argparse.ArgumentParser();ap.add_argument('--dataset',required=True);")
text=text.replace("root=Path(args.cache_root);ids=list(range(301,301+args.frames));rgbds=[];hashes=[]", "root=Path(args.cache_root); ds=next(d for d in json.loads((Path(__file__).resolve().parents[3]/'experiments/TASK010-A/private/DATA_MANIFEST.json').read_text()) if d['name']==args.dataset); ids=ds['rgb_ids']; rgbds=[];hashes=[]")
text=text.replace("root/'original_rgb'/f'{fid:05d}.jpg'", "Path(ds['rgb_dir'])/(f'{fid:05d}'+ds.get('image_suffix','.jpg'))")
text=text.replace("root/'original_rgb'/f'{ids[t]:05d}.jpg'", "Path(ds['rgb_dir'])/(f'{ids[t]:05d}'+ds.get('image_suffix','.jpg'))")
(ROOT/'experiments/TASK010-A/scripts/infer_static.py').write_text(text)
