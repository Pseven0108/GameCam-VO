"""Extract two predeclared short Downtown windows from verified local ZIP spans."""
import bisect
import hashlib
import io
import json
from pathlib import Path
import zipfile
import cv2
import numpy as np
from scipy.spatial.transform import Rotation, Slerp

ROOT=Path(__file__).resolve().parents[3]
TASK=ROOT/'experiments/TASK010-A'
HISTORY=Path('D:/aaa/GameCam-VO/experiments/DROIDW_ORIGINAL_DOMAIN_REPRODUCTION_R1')


class ChunkArchive:
    def __init__(self):
        paths=sorted((HISTORY/'download_chunks').glob('*.bin'))
        self.spans=[(int(p.stem.split('-')[0]),int(p.stem.split('-')[1])+1,p) for p in paths]
        self.starts=[s[0] for s in self.spans]
        self.tail=(HISTORY/'evidence/official-directory.bin').read_bytes()
        self.total=8485995201;self.tail_start=8484261292;self.offset=0;self.verified=set()

    def seek(self,offset,whence=0):
        self.offset=offset+(0,self.offset,self.total)[whence];return self.offset

    def tell(self):return self.offset
    def seekable(self):return True
    def read(self,size=-1):
        if size<0:size=self.total-self.offset
        out=[]
        while size:
            if self.offset>=self.tail_start:
                data=self.tail[self.offset-self.tail_start:self.offset-self.tail_start+size]
            else:
                index=bisect.bisect_right(self.starts,self.offset)-1
                start,stop,path=self.spans[index]
                if not start<=self.offset<stop:raise OSError('Required range not cached')
                if path not in self.verified:
                    expected=json.loads(path.with_suffix('.json').read_text())['sha256']
                    if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise ValueError('Historic chunk hash mismatch')
                    self.verified.add(path)
                with path.open('rb') as f:
                    f.seek(self.offset-start);data=f.read(min(size,stop-self.offset))
            if not data:break
            self.offset+=len(data);size-=len(data);out.append(data)
        return b''.join(out)


def main():
    manifest=json.loads((TASK/'private/DATA_MANIFEST.json').read_text())
    archive=ChunkArchive()
    K=np.array([[893.342715,0,778.820175],[0,894.663808,588.956733],[0,0,1.]])
    dist=np.array([-.152652,.105404,-.000751,.000176,-.020031])
    cv2.setNumThreads(1)
    with zipfile.ZipFile(archive) as z:
        for scene in ['downtown1','downtown2']:
            name=scene+'_holdout';out=TASK/'private/datasets'/name
            (out/'rgb').mkdir(parents=True,exist_ok=False)
            members=sorted(i for i in z.namelist() if i.startswith(f'DROID-W/{scene}/images_anonymized/') and i.endswith('.jpg'))
            selected=members[600:632]  # chosen without inspecting GT or candidate results
            times=np.array([float(Path(p).stem) for p in selected])
            gt=np.loadtxt(io.BytesIO(z.read(f'DROID-W/{scene}/traj_gt_fastlivo.txt')))
            keep=(times>=gt[0,0])&(times<=gt[-1,0])
            if not keep.all():raise RuntimeError('Predeclared real window outside reference coverage')
            rotations=Slerp(gt[:,0],Rotation.from_quat(gt[:,4:8]))(times).as_matrix()
            poses=np.tile(np.eye(4),(len(times),1,1));poses[:,:3,:3]=rotations
            poses[:,:3,3]=np.column_stack([np.interp(times,gt[:,0],gt[:,i]) for i in range(1,4)])
            records=[]
            for fid,member,t in zip(range(601,633),selected,times):
                data=z.read(member)  # Python ZIP verifies original CRC
                image=cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_COLOR)
                if image is None or image.shape!=(1200,1600,3):raise RuntimeError('Real RGB invalid')
                image=cv2.undistort(image,K,dist)
                path=out/f'rgb/{fid:05d}.jpg'
                # PNG lossless bytes retained under .png, avoiding re-encoding the original JPEG.
                path=path.with_suffix('.png');cv2.imwrite(str(path),image)
                records.append({'rgb_id':fid,'timestamp':float(t),'archive_member':member,
                    'original_jpeg_sha256':hashlib.sha256(data).hexdigest(),
                    'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'preprocessing':'OpenCV undistort; lossless PNG'})
            h,w=216,288;sx=w/1600;sy=h/1200
            k=np.array([sx*K[0,0],sy*K[1,1],sx*(K[0,2]+.5)-.5,sy*(K[1,2]+.5)-.5])
            kk=np.tile(k,(32,1));ids=np.arange(601,633)
            np.savez_compressed(out/'offline_gt.npz',rgb_ids=ids,c2w=poses,intrinsics=kk,timestamps=times)
            np.save(out/'intrinsics.npy',kk)
            manifest.append({'name':name,'domain':'REAL_DROIDW_DOWNTOWN','environment':'RealOutdoor',
                'sequence':scene,'split':'HELD_OUT_FROM_TASK010A_SELECTION_PAPER_EVAL_DOMAIN',
                'rgb_ids':ids.tolist(),'rgb_dir':str(out/'rgb'),'image_suffix':'.png',
                'offline_gt':str(out/'offline_gt.npz'),'hw':[h,w],'rgb_manifest':records,
                'pose_unit':'Published FAST-LIVO2 reference metres; not independent metrology',
                'gt_timestamp_association':'Translation linear interpolation + quaternion SLERP; no GT supplied to inference'})
    (TASK/'private/DATA_MANIFEST.json').write_text(json.dumps(manifest,indent=2))
    public=[{k:v for k,v in row.items() if k not in ('rgb_dir','prior_cache','offline_gt')} for row in manifest]
    (TASK/'09_reproducibility/DATASET_WINDOWS.json').write_text(json.dumps(public,indent=2))
    print('Admitted 2 real windows, 64 frames, CRC/decode/SHA and undistortion complete')


if __name__=='__main__':main()
