"""Prepare the existing approved publisher for this task, without publishing."""
import ast,shutil
from pathlib import Path
from common import TASK


def main():
    old=Path('D:/aaa/GameCam-VO-TASK011A/experiments/TASK011A/private/publication/publish_review.py')
    text=old.read_text(encoding='utf-8')
    changes={
        "ROOT=Path('D:/aaa/GameCam-VO-TASK011A')":"ROOT=Path('D:/aaa/GameCam-VO-TASK011B')",
        "PRIVATE=ROOT/'experiments/TASK011A/private/publication'":"PRIVATE=ROOT/'experiments/TASK011B/private/publication'",
        "GameCam-VO-Task011A":"GameCam-VO-Task011B",
        "TASK011A: reproduce depth-risk evidence and audit Native/Flip fusion tradeoffs":
            "TASK011B: complete native-precision validity-aware CADP-DR 20-window comparison",
        "TASK011A — Depth reliability reassessment and Native/Flip fusion":
            "TASK011B — Validity-aware depth reliability and actual CADP-DR utility",
    }
    for before,after in changes.items():
        if before not in text:raise RuntimeError('Existing approved publication template drifted')
        text=text.replace(before,after)
    start=text.index("    body=f'''TASK011A completed locally")
    end=text.index("    if release['draft']:",start)
    body="""    decision=json.loads((ROOT/manifest['review_directory']/'10_FINAL_REPORT/TASK011B_DECISION.json').read_text())
    body=f'''TASK011B completed:20 fixed VIPER windows ×7 arms,140 real formal outcomes.

{decision['complete_64_frame_trajectories']} complete64-frame trajectories; {decision['algorithm_failures']} retained algorithm failures. Native CPU preprocessing/CUDA autocast preserved.10 prior FP32 engineering pilots excluded from formal estimates. No new training or production-baseline edits.

- [Fixed-commit final report](https://github.com/Pseven0108/GameCam-VO/blob/{commit}/{manifest['review_directory']}/FINAL_REVIEW.md)
- [Complete expanded review](https://github.com/Pseven0108/GameCam-VO/tree/{commit}/{manifest['review_directory']})
- [Fixed-commit complete ZIP SHA](https://github.com/Pseven0108/GameCam-VO/blob/{commit}/review_packages/{expected[1].name})

Full review includes actual per-run trajectories/logs/metrics, exact native BA-grid depth/U states and control coefficients, CPU float evidence, native regression arrays, isolated candidate source, configs, tests and figures. Raw RGB/GT, full-resolution duplicate prior arrays, embedded-RGB native videos, weights and environments are excluded; original full outputs remain on the user's D: and are linked by SHA and precise derivation manifests.

A0 already includes the native depth prior; A1 is the isolated D1 endpoint. One seed,20 sequences, explored Validation, no blind-test/generalization or probability-calibration claim. Geometry need is an inverse-normal proxy; no unapproved uniform-attenuation or new-stage run was added. All negative outcomes are retained. Read the report and paired confidence intervals before selecting a next stage.
'''
"""
    text=text[:start]+body+text[end:]
    start=text.index("    with urlopen(Request(asset['browser_download_url']")
    end=text.index("    print(json.dumps(receipt,indent=2),flush=True)",start)
    verification="""    downloaded=PRIVATE/'PUBLIC_COMPLETE_ZIP_VERIFY.zip'
    if downloaded.exists():raise RuntimeError('Preserve earlier uncertain public-download copy')
    identity=hashlib.sha256();downloaded_bytes=0
    with urlopen(Request(asset['browser_download_url'],headers={'User-Agent':'GameCam-VO-Public-Verification'}),timeout=180) as r, downloaded.open('xb') as f:
        for block in iter(lambda:r.read(4*1024**2),b''):
            f.write(block);identity.update(block);downloaded_bytes+=len(block)
    assert identity.hexdigest()==manifest['archive_sha256']
    assert downloaded_bytes==asset['size']
    with zipfile.ZipFile(downloaded) as z:
        assert z.testzip() is None
        rows=list(csv.DictReader(io.StringIO(z.read('SHA256_MANIFEST.csv').decode())))
        assert len(rows)==manifest['internal_sha256_count']
        for row in rows:
            b=z.read(row['path']);assert len(b)==int(row['bytes']) and hashlib.sha256(b).hexdigest()==row['sha256']
        assert z.read('FINAL_REVIEW.md')==(ROOT/manifest['review_directory']/'FINAL_REVIEW.md').read_bytes()
    receipt.update(status='PUBLIC_VERIFIED',zip_sha256=manifest['archive_sha256'],zip_bytes=downloaded_bytes,zip_crc='PASS',internal_sha256_verified=len(rows),release_url=public['html_url'],zip_public_url=asset['browser_download_url'],public_download_used_credentials=False,release_tag_bound_to_fixed_commit=True,local_current_ZIP_cleanup_permitted=True);save(receipt)
    downloaded.unlink()
"""
    text=text[:start]+verification+text[end:]
    # All authenticated operations go through the already-authorized server
    # wrapper. No GitHub token is read from the local credential manager.
    marker="receipt_path=PRIVATE/'PUBLICATION_RECEIPT.json'"
    text=text.replace(marker,marker+"\nimport sys\nsys.path.insert(0,str(ROOT/'experiments/TASK011B/scripts'))\nfrom publication_server_bridge import request as server_request, push as server_push, upload as server_upload")
    start=text.index('def api(');end=text.index('\ndef sha(',start)
    text=text[:start]+'''def api(method,path='',token=None,value=None):
    return server_request(method,path,value)

'''+text[end:]
    start=text.index('def token():');end=text.index('\ndef main():',start)
    text=text[:start]+'''def token():
    return 'SERVER_WRAPPER_ONLY_NO_LOCAL_TOKEN'


def upload(path,release,credential):
    return server_upload(path,release)

'''+text[end:]
    start=text.index("        r=subprocess.run(['git','-c','credential.interactive=never','push'")
    end=text.index("        receipt['status']='PUSHED';save(receipt)",start)
    text=text[:start]+'''        proof=server_push(receipt['commit'],manifest['parent_sha'],manifest['branch'])
        (PRIVATE/'git_push.log').write_text(json.dumps(proof,indent=2)+'\\n',encoding='utf-8')
'''+text[end:]
    ast.parse(text)
    dest=TASK/'private/publication/publish_review.py'
    dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():
        if dest.read_text(encoding='utf-8')==text:
            print('SAME_UNUSED_PUBLICATION_CLIENT_ALREADY_PREPARED',flush=True)
            return
        if (dest.parent/'PUBLICATION_RECEIPT.json').exists() or (dest.parent/'publication.index').exists():
            raise FileExistsError('Do not overwrite an active publisher')
        backup=dest.with_name('publish_review_unused_local_template_001.py')
        if backup.exists():raise FileExistsError('Preserve prior unused publisher template')
        shutil.copy2(dest,backup)
    dest.write_text(text,encoding='utf-8')
    print('PUBLICATION_CLIENT_PREPARED_NO_NETWORK_MUTATION',flush=True)


if __name__=='__main__':main()
