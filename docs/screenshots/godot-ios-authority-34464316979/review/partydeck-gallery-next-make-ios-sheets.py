import json,math,textwrap,sys
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
run=sys.argv[1]
audit_path=Path('/tmp/partydeck-gallery-next-ios-'+run+'-source-audit.json')
audit=json.loads(audit_path.read_text())
out=Path('/tmp/partydeck-gallery-next-review-sheets')/run
out.mkdir(parents=True,exist_ok=False)
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',14)
records=[]
for suite in audit['suites']:
 for case_no,case in enumerate(suite['cases'],1):
  captures=[c for c in suite['captures'] if c['test_identifier']==case['identifier']]
  for start in range(0,len(captures),4):
   group=captures[start:start+4]
   canvas=Image.new('RGB',(len(group)*414+12,1004),'#eeeeee')
   draw=ImageDraw.Draw(canvas)
   for i,c in enumerate(group):
    x=12+i*414
    draw.text((x,8),suite['suite']+' / case '+str(case_no)+' / '+str(start+i+1),font=font,fill='#111111')
    for line_no,line in enumerate(textwrap.wrap(c['scenario'],46)[:3]):
     draw.text((x,27+line_no*17),line,font=font,fill='#111111')
    draw.text((x,82),Path(c['source_original']).name[:22],font=font,fill='#444444')
    im=Image.open(c['source_original']).convert('RGB');im.thumbnail((402,874),Image.Resampling.LANCZOS)
    canvas.paste(im,(x,113))
   path=out/(suite['suite']+'-case-'+str(case_no)+'-page-'+str(start//4+1)+'.png')
   canvas.save(path)
   records.append({'path':str(path),'suite':suite['suite'],'case':case['identifier'],'files':[c['source_original'] for c in group]})
(out/'index.json').write_text(json.dumps(records,indent=2)+'\n')
print(json.dumps({'run':run,'sheets':len(records),'captures':sum(len(x['files']) for x in records),'index':str(out/'index.json')}))
