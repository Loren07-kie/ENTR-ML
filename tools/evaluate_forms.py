"""Private local evaluation helper; outputs go to ignored instance/, never the repository."""
import sys, csv,io,json,subprocess,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image
import form_reader
ROOT=Path(__file__).resolve().parents[1]
def local_ocr(image,psm=11):
 path=ROOT/'instance'/f'ocr-{uuid.uuid4().hex}.png';Image.fromarray(image).save(path)
 try:
  result=subprocess.run(['node',str(ROOT/'tools/ocr_bridge.cjs'),str(path),str(psm)],capture_output=True,text=True,encoding='utf-8',check=True)
  text=result.stdout
  if not text.startswith('level'):
   text='level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n'+text
  records=list(csv.DictReader(io.StringIO(text),delimiter='\t',quoting=csv.QUOTE_NONE))
  records=[r for r in records if r['level']=='5']
  data={k:[] for k in ['text','conf','block_num','par_num','line_num','left','top','width','height']}
  for r in records:
   for key in data:data[key].append(r[key] if key=='text' else float(r[key]) if key=='conf' else int(r[key]))
  return data
 finally:path.unlink(missing_ok=True)
if __name__=='__main__':
 form_reader.read_printed=local_ocr
 results=[]
 for i,path in enumerate(sys.argv[1:]):
  print('Reading',i+1,flush=True)
  result=form_reader.read_form(np.array(Image.open(path).convert('RGB')),lambda text,p:print(text,flush=True))
  results.append(result)
  print(json.dumps({'summary':result['summary'],'fields':[{k:v for k,v in f.items() if k!='snippet'} for f in result['fields']]},ensure_ascii=True),flush=True)
  (ROOT/'instance/layout-evaluation-private.json').write_text(json.dumps(results,ensure_ascii=False),encoding='utf-8')
