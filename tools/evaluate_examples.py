"""Independent example evaluation. This script alone reads the fictitious answer key."""
from pathlib import Path
import sys,json,unicodedata,io
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image
import form_templates
ROOT=Path(__file__).resolve().parents[1]
def normalized(text):return ''.join(c for c in unicodedata.normalize('NFD',str(text).lower()) if c.isalnum())
def evaluate():
 truth=json.loads((ROOT/'static/examples/respuestas-ficticias.json').read_text(encoding='utf-8'));groups={};total=correct=0
 for item in truth:
  image=Image.open(ROOT/'static/examples'/item['file']).convert('RGB')
  # Match uploaded folder storage: JPEG re-encoding before inference.
  buf=io.BytesIO();image.save(buf,'JPEG',quality=90);buf.seek(0);result=form_templates.read_template(np.array(Image.open(buf).convert('RGB')))
  if not result:raise RuntimeError('No se reconoció el QR de '+item['file'])
  found={f['label']:f['value'] for f in result['fields']};g=groups.setdefault(item['template'],{'forms':0,'fields':0,'correct_fields':0});g['forms']+=1
  for label,value in item['answers'].items():
   ok=normalized(found.get(label,''))==normalized(value);total+=1;correct+=int(ok);g['fields']+=1;g['correct_fields']+=int(ok)
 out={'forms':len(truth),'fields':total,'correct_fields':correct,'exact_field_accuracy':correct/total,'by_use_case':groups,'evaluation':'public fictitious demonstration images using MNIST official test glyphs; no fitting/selection on these answers','normalization':'case/diacritics/punctuation ignored; numeric/content errors remain errors','input':'JPEG quality 90, as stored in folder uploads'}
 (ROOT/'models/form_demo_evaluation.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out,indent=2),flush=True);return out
if __name__=='__main__':
 if '--wasm-local' in sys.argv:
  import pytesseract
  from tools.evaluate_forms import local_ocr
  def text(image,**kwargs):return ' '.join(local_ocr(image,7)['text'])
  pytesseract.image_to_string=text
 evaluate()
