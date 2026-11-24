"""Static SVG figures generated from the sealed 24-run numeric results."""
import json,math,pathlib,html
from analyze_repeated import ROOT,OUT,ARMS,c
R=ROOT/'reports';R.mkdir(exist_ok=True)
def txt(x,y,s,size=16,fill='#17283a',anchor='start'):
 return f'<text x="{x:.2f}" y="{y:.2f}" font-family="Arial, sans-serif" font-size="{size}" fill="{fill}" text-anchor="{anchor}">{html.escape(str(s))}</text>'
def line(x,y,xx,yy,color='#d4dce6',width=1,dash=''):
 return f'<line x1="{x:.2f}" y1="{y:.2f}" x2="{xx:.2f}" y2="{yy:.2f}" stroke="{color}" stroke-width="{width}"'+(f' stroke-dasharray="{dash}"' if dash else '')+'/>'
def circle(x,y,r,col):return f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{r}" fill="{col}" stroke="white" stroke-width="1"/>'
def main():
 d=json.loads((OUT/'TASK004B_RESULTS.json').read_text());rows=d['runs'];assert len(rows)==24
 width,height=1500,1040
 svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}"><rect width="1500" height="1040" fill="white"/>',txt(30,35,'Task004B | Three observed run blocks per arm',25),txt(30,63,'val_007 | 487 frames | stride=1 | dots: seeds 43 / 44 / 45; black line: mean; whisker: sample SD',16)]
 colors={43:'#2f65b3',44:'#c9821c',45:'#a94970'}
 panels=[('ate_sim3_game_units','Global Sim3 ATE (game units)',None),('absolute_gap_from_100_pct_points','Fixed endpoint absolute gap from 100% (pp)',None),('displacement_ratio_pct','RGB 312 to 328 displacement ratio (%)',100),('keyframes','Final retained keyframes',None)]
 for idx,(metric,title,ref) in enumerate(panels):
  ox=35+(idx%2)*740;oy=110+(idx//2)*430;left=ox+66;top=oy+35;pw=620;ph=305
  values=[r[metric] for r in rows];hi=max(values)*1.12;lo=0
  def xx(a):return left+(ARMS.index(a)+.5)*pw/8
  def yy(v):return top+ph-ph*(v-lo)/(hi-lo)
  svg.append(txt(ox,oy+10,title,19))
  for k in range(6):
   v=hi*k/5;y=yy(v);svg.extend([line(left,y,left+pw,y),txt(left-8,y+5,f'{v:.1f}',13,anchor='end')])
  if ref is not None:svg.extend([line(left,yy(ref),left+pw,yy(ref),'#52606e',1.5,'7 4'),txt(left+pw-5,yy(ref)-6,'100%',12,anchor='end')])
  for a in ARMS:
   rs=[r for r in rows if r['arm']==a];vals=[r[metric] for r in rs];mean=sum(vals)/3;sd=math.sqrt(sum((x-mean)**2 for x in vals)/2);x=xx(a)
   svg.extend([line(x,yy(max(0,mean-sd)),x,yy(mean+sd),'#1b2e40',1.5),line(x-8,yy(max(0,mean-sd)),x+8,yy(max(0,mean-sd)),'#1b2e40',1.5),line(x-8,yy(mean+sd),x+8,yy(mean+sd),'#1b2e40',1.5),line(x-17,yy(mean),x+17,yy(mean),'#1b2e40',3)])
   for r,jitter in zip(rs,(-11,0,11)):svg.append(circle(x+jitter,yy(r[metric]),5,colors[r['seed']]))
   svg.extend([txt(x,top+ph+23,a,15,anchor='middle'),txt(x,top+ph+42,''.join(map(str,c.BITS[a])),12,'#65778a','middle')])
  svg.append(txt(left+pw/2,top+ph+64,'Arm / D W U',13,anchor='middle'))
 for idx,(seed,col) in enumerate(colors.items()):svg.extend([circle(45+idx*180,995,5,col),txt(58+idx*180,1000,'Seed '+str(seed),14)])
 svg.append(txt(610,1000,'One sequence; main seeded, spawned tracker not fully reseeded. No cross-environment claim.',13))
 svg.append('</svg>')
 with (R/'TASK004B_THREE_BLOCK_RESULTS.svg').open('x',encoding='utf-8') as f:f.write(''.join(svg))
 # D contrast CI figure: separate axes per outcome to preserve their physical units.
 metrics=[('ate_sim3_game_units','D on minus off: Sim3 ATE (game units)'),('absolute_gap_from_100_pct_points','D on minus off: endpoint gap (pp)'),('displacement_ratio_pct','D on minus off: signed ratio (pp)'),('keyframes','D on minus off: keyframes')]
 fig=['<svg xmlns="http://www.w3.org/2000/svg" width="1300" height="800" viewBox="0 0 1300 800"><rect width="1300" height="800" fill="white"/>',txt(25,32,'Task004B | Seed-wise D contrasts and small-n 95% CI',23),txt(25,60,'Each contrast averages over all W/U conditions within a run block; CI uses three contrasts, t(df=2).',15)]
 for i,(metric,title) in enumerate(metrics):
  q=next(x for x in d['effects'] if x['metric']==metric and x['factor']=='D');values=[q['ci95_low'],q['ci95_high'],q['seed43_effect'],q['seed44_effect'],q['seed45_effect'],0];lo=min(values);hi=max(values);margin=(hi-lo)*.1 or 1;lo-=margin;hi+=margin;oy=120+i*158;left=470;pw=740
  fx=lambda v:left+pw*(v-lo)/(hi-lo)
  fig.extend([txt(25,oy,title,17),txt(25,oy+25,f"Mean {q['mean']:.3f}; CI [{q['ci95_low']:.3f}, {q['ci95_high']:.3f}]",14),line(fx(0),oy-18,fx(0),oy+72,'#8695a4',1,'5 4'),line(fx(q['ci95_low']),oy,fx(q['ci95_high']),oy,'#172c40',3),circle(fx(q['mean']),oy,6,'#172c40')])
  for j,seed in enumerate((43,44,45)):fig.append(circle(fx(q['seed'+str(seed)+'_effect']),oy+25+j*15,4,colors[seed]))
  for k in range(5):
   v=lo+(hi-lo)*k/4;x=fx(v);fig.extend([line(x,oy+76,x,oy+80,'#7e8e9e'),txt(x,oy+96,f'{v:.2f}',12,anchor='middle')])
 fig.extend([txt(25,778,'Descriptive unadjusted CI; uncertainty includes observed run variability. Not a fixed-state direct-effect experiment.',14),'</svg>'])
 with (R/'TASK004B_D_EFFECTS_CI.svg').open('x',encoding='utf-8') as f:f.write(''.join(fig))
 print('TASK004B_NUMERIC_FIGURES_COMPLETE',flush=True)
if __name__=='__main__':main()
