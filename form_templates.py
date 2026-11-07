"""Read our public QR templates by geometry. QR carries no responses or person data."""
from pathlib import Path
import json,cv2,numpy as np,joblib
from model_io import load_model
from digit_features import normalize,features
ROOT=Path(__file__).parent
MODEL=None
def read_template(rgb):
 global MODEL
 registry=json.loads((ROOT/'models/form_templates.json').read_text(encoding='utf-8'))
 message,points,_=cv2.QRCodeDetector().detectAndDecode(rgb)
 if not message.startswith('TecnoForms:v3:') or points is None:return None
 key=message.split(':')[-1]
 if key not in registry:return None
 template=registry[key];matrix=cv2.getPerspectiveTransform(points[0].astype(np.float32),np.array(template['qr_quad'],np.float32))
 page=cv2.warpPerspective(rgb,matrix,(template['width'],template['height']),borderValue=(255,255,255))
 if MODEL is None:MODEL=load_model(ROOT/'models/forms_digits.joblib')
 fields=[]
 for entry in template['fields']:
  field={'label':entry['label'],'type':'text','value':'','confidence':0.,'status':'empty','source':'Plantilla QR + modelo de dígitos','review':True}
  if entry['type'] in ('id','number'):
   digits=[];scores=[]
   for x,y,r,b in entry['cells']:
    gray=cv2.cvtColor(page[y:b,x:r],cv2.COLOR_RGB2GRAY);mask=cv2.threshold(gray,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)[1]
    canvas=normalize(mask)
    if canvas is None:digits.append('?');continue
    probs=MODEL.predict_proba(features(canvas).reshape(1,-1))[0];idx=int(np.argmax(probs));digits.append(str(MODEL.classes_[idx]));scores.append(float(probs[idx]))
   raw=''.join(digits)
   if raw and set(raw)!={'?'}:
    field['value']=str(int(raw)) if entry['type']=='number' and '?' not in raw else raw
    field['confidence']=round(min(scores),3) if scores else 0.;field['status']='uncertain' if '?' in raw or field['confidence']<.9 else 'read'
  elif entry['type']=='checkbox':
   options=[]
   for option in entry['options']:
    x,y,r,b=option['box'];cut=page[y+7:b-7,x+7:r-7];gray=cv2.cvtColor(cut,cv2.COLOR_RGB2GRAY)
    checked=float(np.mean(gray<145))>.08;options.append({'label':option['label'],'checked':bool(checked)})
   field.update(type='checkbox',options=options,value='; '.join(o['label'] for o in options if o['checked']),status='uncertain',source='Plantilla QR + casillas')
  else:
   import pytesseract
   x,y,r,b=entry['box'];value=pytesseract.image_to_string(page[y+5:b-5,x+5:r-5],lang='spa+eng',config='--psm 7',timeout=20).strip()
   field.update(value=value,status='uncertain' if value else 'empty',source='Plantilla QR + OCR de texto impreso')
  fields.append(field)
 return {'fields':fields,'requires_review':True,'template_id':key,'warnings':['Plantilla TecnoForms reconocida. El QR solo identifica posiciones; las respuestas se leyeron de la imagen. Confirma los valores antes del análisis.'],'summary':{'fields':len(fields),'blank':sum(not f['value'] for f in fields),'uncertain':sum(f['status']=='uncertain' for f in fields),'checkbox_groups':sum(f['type']=='checkbox' for f in fields),'engine':'QR + SVM entrenado para celdas + OCR'}}
