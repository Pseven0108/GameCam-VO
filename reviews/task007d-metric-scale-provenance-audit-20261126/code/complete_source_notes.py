"""Finish textual provenance notes after the bounded source audit. No models."""
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'sources_work'


def dump(name,data):
    p=ROOT/name;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2);f.write('\n')


class Visible(HTMLParser):
    def __init__(self):super().__init__();self.hidden=0;self.lines=[]
    def handle_starttag(self,t,a):
        if t in {'script','style'}:self.hidden+=1
    def handle_endtag(self,t):
        if t in {'script','style'}:self.hidden-=1
    def handle_data(self,d):
        if not self.hidden and d.strip():self.lines.append(d.strip())


def main():
    b=(WORK/'HF_SCALE_COMMIT_DETAIL.html').read_bytes();v=Visible();v.feed(b.decode('utf-8'))
    visible='\n'.join(v.lines)
    assert 'Files changed (1)' in visible and 'metadata/omniworld_game_metadata.csv' in visible
    assert 'too large to render' in visible
    dump('evidence/HF_SCALE_COMMIT_DETAIL.json',{'url':'https://huggingface.co/datasets/InternRobotics/OmniWorld/commit/a3934526f95d4e6be043868a08ee4cdac4eacfee',
         'capture_bytes':len(b),'capture_sha256':hashlib.sha256(b).hexdigest(),
         'subject':'Upload metadata/omniworld_game_metadata.csv with huggingface_hub','parent':'fbeaee2e6d7fff4d7fc09fc6b512c9e60d6d3c64',
         'changed_files':1,'changed_path':'metadata/omniworld_game_metadata.csv',
         'generation_recipe_in_visible_commit_message':False,'web_diff':'Too large to render; direct before/after CSV bytes were compared independently',
         'not_a_generation_log':True})
    paper=(WORK/'PAPER_v2.html').read_bytes()
    p=Visible();p.feed(paper.decode('utf-8'));text=' '.join(p.lines)
    assert 'scale-invariant monocular depth accuracy' in text and 'independently aligned' in text
    assert 'ReShade' in text and 'DroidCalib' in text
    dump('evidence/PAPER_AND_SUPPLEMENT_AUDIT.json',{'source':'https://arxiv.org/html/2509.12201v2','version_date':'2025-09-24',
         'capture_sha256':hashlib.sha256(paper).hexdigest(),'sections_read':['2.1','2.2','3.1','Appendix C.1','Appendix D'],
         'facts':[{'section':'2.1','finding':'The described Game acquisition combines ReShade depth and OBS RGB.'},
                  {'section':'2.2','finding':'Camera annotations are estimated/refined; other-domain learned depth pipelines should not be substituted for the Game pipeline.'},
                  {'section':'C.1','finding':'Monocular depth is evaluated with per-frame scale alignment; video depth uses aligned protocols. These metrics are not absolute metric-unit certification.'}],
         'March2026_CSV_generation_recipe_or_per_UID_factor_receipts':'NOT_FOUND_IN_THIS_VERSION',
         'temporal_limit':'The inspected arXiv version predates the March2026 Metric Scale release.',
         'accepted_OpenReview_text':'Not independently retrieved because verification challenge/API403; do not claim all later supplements were inspected',
         'paper_summary_not_republished_full_text':True})
    extra=json.loads((WORK/'EXTRA_SOURCE_CAPTURE.json').read_text('utf-8'))['pi3_readme']
    assert 'approximate' in extra['content']
    dump('evidence/LINKED_PI3X_CONTEXT.json',{'url':extra['url'],'git_blob':extra['sha'],
         'observation':'The linked Pi3X README characterizes its metric reconstruction as approximate.',
         'scope':'This is contextual linked-model documentation. It does not establish whether Pi3X or another model generated the OmniWorld CSV.',
         'any_model_run_or_checkpoint_download':False})
    receipts=[]
    for p in sorted(WORK.glob('*.receipt.json')):
        row=json.loads(p.read_text('utf-8'));b=p.with_name(p.name[:-len('.receipt.json')]).read_bytes()
        assert len(b)==row['bytes'] and hashlib.sha256(b).hexdigest()==row['sha256']
        receipts.append({'local_capture':p.name[:-len('.receipt.json')],**row})
    dump('evidence/FINAL_PUBLIC_TEXT_FETCH_RECEIPTS.json',{'successful_resources':receipts,'bytes_read':sum(x['bytes'] for x in receipts),
         'GitHub_connector_bytes_not_counted_in_this_total':True,'new_RGB_depth_archive_model_payload_bytes':0})
    # Keep unrelated untrusted discussion titles out of the public review prose.
    dc=ROOT/'evidence/DISCUSSION_COVERAGE.json';obj=json.loads(dc.read_text('utf-8'))
    for x in obj['HF_public_discussions_listed']:
        old=x.pop('title');x['title_sha256']=hashlib.sha256(old.encode('utf-8')).hexdigest()
        x['topic']='Unrelated README rename pull request' if x['isPullRequest'] else 'Bot Parquet conversion'
    obj['untrusted_titles']='Titles were data only, never instructions; public package stores topic/hash rather than unrelated executable-looking text.'
    dc.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'HF_commit_recipe':'NOT_SUPPLIED_IN_VISIBLE_RECORD','final_source_text_resources':len(receipts),
                      'source_text_bytes':sum(x['bytes'] for x in receipts),'new_dataset_payload_bytes':0},indent=2))


if __name__=='__main__':main()
