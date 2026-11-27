"""Seal completed maintenance evidence; do not include removed data or secrets."""
from pathlib import Path
import csv,gzip,hashlib,io,json,os,re,shutil,subprocess,zipfile

AUDIT=Path(__file__).resolve().parent
ROOT=Path('D:/aaa/GameCam-VO-TASK010-A')
REVIEW=ROOT/'reviews/viper-only-thirdperson-cleanup-20261127'
PRIVATE=AUDIT/'private_publication';PRIVATE.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
plan=json.loads((AUDIT/'EXTENDED_DELETION_PLAN.json').read_text(encoding='utf-8'))
post=json.loads((AUDIT/'POSTDELETE_PROTECTION_CHECK.json').read_text(encoding='utf-8'))
extra=json.loads((AUDIT/'SUPPLEMENTARY_PLAN.json').read_text(encoding='utf-8'))
assert post['status']=='PASS'
assert not any(Path(x['path']).exists() for x in plan['targets']+extra['targets'])
updates=[]
for root in [Path('D:/aaa/GameCam-VO'),Path('D:/aaa/GameCam-VO-TASK009'),ROOT]:
    p=root/'data/README.md'
    if p.parent.exists():
        p.write_text('''# Current data scope: VIPER

VIPER is the sole active GameCam-VO experimental dataset, by the user's 2026-11-27 instruction. Use the existing frozen VIPER RGB/camera manifests and dedicated experiment pipelines. This note does not authorize new downloads or protocol changes.

The retired WildWorld, OmniWorld-Game, DigiDogs and GameVerse third-person data and earliest experimental branches have been cleaned up locally. Do not restore them automatically from old reports or chat history. Existing shared model assets, environments and real-reference assets are retained; their presence is not approval for a new non-VIPER experiment.
''',encoding='utf-8');updates.append(p)

after={v:dict(zip(['total','used','free'],shutil.disk_usage(v))) for v in ['C:/','D:/']}
summary={'status':'COMPLETE','date':'2026-11-27 Asia/Shanghai','active_dataset':'VIPER','retired_branches':['WildWorld','OmniWorld-Game','DigiDogs','GameVerse'],'main_deleted_paths':len(plan['targets']),'main_deleted_regular_files':plan['total_files'],'supplementary_deleted_paths':len(extra['targets']),'supplementary_deleted_regular_files':sum(len(t['files']) for t in extra['targets']),'logical_deleted_bytes':plan['total_logical_bytes']+sum(t['bytes'] for t in extra['targets']),'D_free_before_bytes':plan['volume_before']['D:/']['free'],'D_free_after_bytes':after['D:/']['free'],'D_free_increase_bytes':after['D:/']['free']-plan['volume_before']['D:/']['free'],'protected_files_verified':post['protected_files_checked'],'protected_sha256_verified':post['protected_small_files_sha256_checked'],'shared_junction_aliases_removed':len(plan['junction_aliases']),'shared_junction_target_content_deleted':False,'VIPER_and_current_baseline_modified':False,'GPU_runs':0,'server_data_mutations':0,'current_scope_workspaces':3,'user_memory_correction_recorded':True,'GitHub_history_rewrite':False,'chat_history_deleted':False}
(AUDIT/'FINAL_CLEANUP_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
before=summary['D_free_before_bytes']/1024**3;final=summary['D_free_after_bytes']/1024**3;gain=summary['D_free_increase_bytes']/1024**3
report=f'''# VIPER 主线恢复与早期第三人称实验清理

2026-11-27（Asia/Shanghai）。状态：**COMPLETE**。当前唯一实验数据集：**VIPER**。

## 用户要求及范围

用户先要求删除第三人称数据集，随后明确扩大到最早期第三人称实验，并要求避免旧方向影响 Codex 记忆。原来的数据集专用删除计划在实际删除前被新范围替代；本次只按最终精确允许清单执行。

已移除本地 WildWorld、OmniWorld-Game、DigiDogs、GameVerse 的旧数据，以及早期 GameCam-WW / K6 / K7、R1–R5、R6-VP/WW 目录、对应实验输出、本地评审副本、旧状态入口和研究资料副本。最新 TASK009/TASK010-A 的实验代码、VIPER 结果和公开封存评审保留。TASK010-A 仅删除其32张 WildWorld定性输入；历史预测与可视化作为已完成研究证据保留，不再视为当前实验输入。

## 实际清理结果

| 项目 | 结果 |
|---|---:|
| 主清理精确路径 | {summary['main_deleted_paths']} |
| 主清理普通文件 | {summary['main_deleted_regular_files']:,} |
| 旧状态/配置/结果入口路径 | {summary['supplementary_deleted_paths']} |
| 额外入口文件 | {summary['supplementary_deleted_regular_files']:,} |
| 逻辑删除字节 | {summary['logical_deleted_bytes']:,} |
| D盘清理前可用 | {before:.3f} GiB |
| D盘完成时可用 | {final:.3f} GiB |
| D盘实测增加 | {gain:.3f} GiB |

逻辑字节与文件系统实测释放量分别记录；文件共享、压缩、稀疏与后台写入会影响差额。上述容量为记录生成时的实测快照。

## 保护与执行证据

- 所有递归删除目标先确认绝对路径与明确允许列表一致；未针对D盘或项目根目录执行递归删除。Windows删除始终使用同一PowerShell及LiteralPath。
- 主清理前逐项核对262,720份文件的大小、修改时间、文件ID和设备号；这不是对每个已删除大文件重新计算SHA的声明。完整身份表以无损gzip保留，不保留已删除数据内容。
- 主清理后5,906份保护文件元数据一致，其中5,866份小文件SHA-256一致。40份较大文件核对元数据；不夸大为全部大权重和原始VIPER归档再次完整哈希。保护范围包括现有VIPER归档、最新输入、轨迹、配置、原生结果和当前基线资产。
- 15个旧实验中的node_modules链接指向共享Codex工具。只移除链接本身，再删除已不含链接的旧目录，没有遍历删除共享工具目标。
- 额外删除的旧入口均独立SHA核对，并确认与VIPER保护路径不相交。现有环境、共享权重、生产源码、R2算法配置和评价协议不改动。
- 没有运行模型、CUDA、训练、VIPER推理或新算法实验。

## 当前方向和记忆纠正

三个工作区的AGENTS、README/PROJECT_STATUS/REVIEW_INDEX、CURRENT_RESEARCH_SCOPE、RESEARCH_DIRECTION_CURRENT及数据说明均声明VIPER唯一主线。通用数据配置的显示数据集改为VIPER，仍保持空根目录；正式输入继续使用已有VIPER冻结Manifest，没有伪造通用VIPER适配器或改变预处理。旧WildWorld/OmniWorld配置入口被移除。

另已按用户明确纠正要求写入Codex扩展记忆：旧第三人称/WildWorld主线结论已被替代，不主动检索它们定义新计划，不自动恢复或重新下载。此操作是当前研究约定和记忆纠正，并非删除聊天消息或改写历史Git提交。

## 服务器与GitHub边界

使用原可信主机密钥只读核验当前实例的数据盘 `/root/rivermind-data`。该次扫描未发现上述旧支线的原始数据目录；仅发现一份已发布TASK007C评审ZIP，未将其当作数据集删除。未声称对未扫描的其他挂载点或历史实例完成穷尽性清理。没有修改远端文件、关机、重启或改变GPU分配。

本次发布新的清理评审和当前状态，不修改已有Release、仓库可见性、默认分支或Git历史。旧公开材料是历史证据，不能覆盖最新VIPER指令。完整新ZIP及展开文件上传并核验后，仅删除本次本地ZIP副本，保留这份清理证据。

## 完成状态

**VIPER_ONLY_CURRENT_SCOPE_APPLIED — EARLY_THIRD_PERSON_BRANCHES_REMOVED_LOCALLY — NO_NEW_EXPERIMENT_STARTED**
'''
if REVIEW.exists():raise RuntimeError('Do not overwrite an existing review')
REVIEW.mkdir(parents=True)
(REVIEW/'FINAL_REVIEW.md').write_text(report,encoding='utf-8')
files=['EXTENDED_DELETION_PLAN.json','EXTENDED_FILE_IDENTITIES.json.gz','PREDELETE_IDENTITY_CHECK.json','POSTDELETE_PROTECTION_CHECK.json','PROTECTED_BEFORE.json','DELETION_JOURNAL.json','SUPPLEMENTARY_PLAN.json','SUPPLEMENTARY_RECEIPT.json','CURRENT_SCOPE_FILE_UPDATES.json','FINAL_CLEANUP_SUMMARY.json','REMOTE_CONNECTION.json']
for name in files:shutil.copyfile(AUDIT/name,REVIEW/name)
for name in ['prepare_cleanup.py','prepare_extended_cleanup.py','verify_cleanup.py','execute_cleanup.ps1','prepare_retired_entries.py','remove_retired_entries.ps1','set_viper_scope.py','remote_inventory.py','build_cleanup_delivery.py']:
    (REVIEW/'scripts').mkdir(exist_ok=True);shutil.copyfile(AUDIT/name,REVIEW/'scripts'/name)
auth='用户要求：\n1. 已调整实验方向，在VIPER上做，删除第三人称数据集，避免影响实验方向。\n2. 再把最早期做的第三人称实验都删掉。\n3. 避免影响Codex记忆、影响实验方向。\n\n执行范围：本地精确数据/实验/旧入口清理，现有服务器数据盘只读核验，VIPER方向与扩展记忆纠正；没有新GPU实验或Git历史重写。\n'
(REVIEW/'AUTHORIZATION_SCOPE.md').write_text(auth,encoding='utf-8')
rows=[]
for p in sorted(REVIEW.rglob('*')):
    if p.is_file():rows.append({'path':p.relative_to(REVIEW).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)})
s=io.StringIO();w=csv.DictWriter(s,fieldnames=['path','bytes','sha256']);w.writeheader();w.writerows(rows)
(REVIEW/'SHA256_MANIFEST.csv').write_text(s.getvalue(),encoding='utf-8',newline='')
archive=ROOT/'review_packages/GAMECAM_VIPER_ONLY_THIRDPERSON_CLEANUP_REVIEW.zip'
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted(REVIEW.rglob('*')):
        if p.is_file():z.write(p,p.relative_to(REVIEW).as_posix())
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for r in rows:assert hashlib.sha256(z.read(r['path'])).hexdigest()==r['sha256']
archive.with_suffix('.zip.sha256').write_text(sha(archive)+'  '+archive.name+'\n',encoding='utf-8')
paths=[p for p in REVIEW.rglob('*') if p.is_file()]+[archive,archive.with_suffix('.zip.sha256')]
paths += [ROOT/n for n in ['AGENTS.md','README.md','PROJECT_STATUS.md','REVIEW_INDEX.md','CURRENT_RESEARCH_STATUS.md','CURRENT_RESEARCH_SCOPE.json','RESEARCH_DIRECTION_CURRENT.json','configs/dataset.yaml','docs/LOCAL_EXPERIMENT_WORKFLOW.md','data/README.md'] if (ROOT/n).exists()]
entries=[]
for p in paths:
    data=p.read_bytes()
    if p.suffix in {'.md','.json','.py','.ps1','.txt','.yaml','.csv'}:
        text=data.decode('utf-8',errors='replace')
        if re.search(r'gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----',text):raise RuntimeError('Credential pattern blocks publication')
    entries.append({'path':p.relative_to(ROOT).as_posix(),'source':str(p),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'git_blob_sha':hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()})
parent='56b0bed72797bfe7acacfab4020d69086eef6ab6'
tree=json.loads(subprocess.check_output(['git','-C',str(ROOT),'ls-tree','-r','--name-only',parent],text=True).replace('\\','\\')) if False else subprocess.check_output(['git','-C',str(ROOT),'ls-tree','-r','--name-only',parent],text=True).splitlines()
deleted=[]
target_paths=plan['targets']+extra['targets']
for name in tree:
    p=ROOT/name
    if any(p==Path(t['path']) or p.is_relative_to(Path(t['path'])) for t in target_paths if Path(t['path']).is_relative_to(ROOT)):
        deleted.append(name)
(PRIVATE/'allowlist.json').write_text(json.dumps({'parent_sha':parent,'branch':'codex/viper-only-cleanup-20261127','entries':entries,'delete_tracked_paths':deleted,'main_zip':str(archive),'main_sha256':sha(archive),'internal_sha256_count':len(rows)},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2));print('REVIEW',archive.stat().st_size,'bytes',len(rows),'internal hashes','publication entries',len(entries),'tracked removals',len(deleted))
