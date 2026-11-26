"""Normalize the generated, unsealed report indentation before packaging."""
from common import *
def main():
    cpu_only()
    files=[ROOT/'FINAL_REVIEW.md',ROOT/'README_请先读.md',ROOT/'EXECUTION_LOG.md',*sorted((ROOT/'05_reports').glob('*.md'))]
    for p in files:
        t=p.read_text('utf-8')
        t='\n'.join(line[4:] if line.startswith('    ') else line for line in t.splitlines())+'\n'
        with p.open('w',encoding='utf-8',newline='\n') as f:f.write(t)
    print(json.dumps({'reports_formatted':len(files),'scientific_values_changed':False}))
if __name__=='__main__':main()
