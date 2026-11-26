"""Public text pages and HTTP HEAD only. Never download dataset payloads."""
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import urllib.request
import urllib.parse

ROOT = Path(__file__).resolve().parents[1]
CAP = 1024 * 1024


class Links(HTMLParser):
    def __init__(self): super().__init__(); self.links = []; self.forms = []; self.titles = []; self.in_title = False
    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "a" and "href" in d: self.links.append(d["href"])
        if tag == "form": self.forms.append({k: d.get(k) for k in ["action", "method"]})
        if tag == "title": self.in_title = True
    def handle_endtag(self, tag):
        if tag == "title": self.in_title = False
    def handle_data(self, text):
        if self.in_title: self.titles.append(text)


pages = {
    "VIPER_download_current": "https://playing-for-benchmarks.org/download/",
    "VIPER_monodepth_current": "https://playing-for-benchmarks.org/leaderboards/monodepth/",
    "Virtual_KITTI_2_official": "https://europe.naverlabs.com/proxy-virtual-worlds-vkitti-2/",
    "NYUv2_official": "https://cs.nyu.edu/~fergus/datasets/nyu_depth_v2.html",
    "TartanAir_official": "https://theairlab.org/tartanair-dataset/",
}
records = []; vk_links = []
for name, url in pages.items():
    row = {"source": name, "url": url, "method": "GET public text", "raw_dataset_payload_bytes": 0}
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "GameCam-VO-TASK007B-Metadata-Audit"})
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read(CAP + 1)
            if len(body) > CAP: raise RuntimeError("Public text exceeds metadata cap")
            row.update(status=response.status, final_url=response.url, bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
        parsed = Links(); parsed.feed(body.decode("utf-8", "replace"))
        row.update(title="".join(parsed.titles).strip(), form_endpoints=parsed.forms,
                   raw_forms_or_CSRF_values_saved=False,
                   relevant_links=[urllib.parse.urljoin(url, h) for h in parsed.links if any(s in h.lower() for s in ["depth", "download", "md5", "checksum", "textgt", "intrinsic"])])
        if name == "Virtual_KITTI_2_official":
            vk_links = [urllib.parse.urljoin(url, h) for h in parsed.links if "download.europe.naverlabs.com" in h and any(s in h.lower() for s in ["rgb.tar", "depth.tar", "textgt.tar", "md5"]) ]
    except Exception as e:
        row.update(status="FETCH_FAILED", exception_type=type(e).__name__)
    records.append(row)
heads = []
for url in vk_links:
    row = {"url": url, "method": "HEAD", "raw_dataset_payload_bytes": 0}
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "GameCam-VO-TASK007B-Metadata-Audit"})
        with urllib.request.urlopen(req, timeout=20) as r:
            row.update(status=r.status, final_url=r.url, Content_Length=r.headers.get("Content-Length"),
                       Accept_Ranges=r.headers.get("Accept-Ranges"), ETag=r.headers.get("ETag"), Last_Modified=r.headers.get("Last-Modified"))
    except Exception as e:
        row.update(status="HEAD_FAILED", exception_type=type(e).__name__)
    heads.append(row)
result = {"pages": records, "Virtual_KITTI_archive_HEAD": heads,
          "raw_dataset_payload_downloaded": False, "license_form_submitted": False,
          "no_contacts_or_submissions": True, "no_claim_sample_integrity_from_HEAD": True}
p = ROOT / "sources/PUBLIC_METADATA_ACCESS.json"; p.parent.mkdir(exist_ok=True)
with p.open("x", encoding="utf-8") as f: json.dump(result, f, indent=2); f.write("\n")
print(json.dumps({"pages": [{"source": r["source"], "status": r["status"]} for r in records], "HEAD": heads}, indent=2))
