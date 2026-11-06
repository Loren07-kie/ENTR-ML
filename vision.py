"""Image preprocessing, conservative digit segmentation and optional OCR."""
from pathlib import Path
import os, logging, re
from functools import lru_cache
import cv2, numpy as np, joblib
from PIL import Image, ImageOps
MODEL=None
PHOTO=None
os.environ.setdefault('OMP_THREAD_LIMIT','1')
logger=logging.getLogger(__name__)

@lru_cache(maxsize=1)
def ocr_status():
 try:
  import pytesseract
  languages=pytesseract.get_languages(config='')
  available=[lang for lang in ('spa','eng') if lang in languages]
  return {'available':bool(available),'languages':available}
 except Exception:
  return {'available':False,'languages':[]}

def prepare_page(rgb):
 """Bound OCR workload and straighten prominent form rules without saving the photo."""
 h,w=rgb.shape[:2]
 scale=min(1,1300/max(h,w))
 page=cv2.resize(rgb,(max(1,round(w*scale)),max(1,round(h*scale))),interpolation=cv2.INTER_AREA) if scale<1 else rgb.copy()
 gray=cv2.cvtColor(page,cv2.COLOR_RGB2GRAY)
 edges=cv2.Canny(gray,60,160)
 lines=cv2.HoughLinesP(edges,1,np.pi/180,threshold=70,minLineLength=max(80,page.shape[1]//4),maxLineGap=20)
 angles=[]
 if lines is not None:
  for x1,y1,x2,y2 in lines[:,0]:
   angle=np.degrees(np.arctan2(float(y2-y1),float(x2-x1)))
   if abs(angle)<18:angles.append(angle)
 if len(angles)>=3:
  angle=float(np.median(angles))
  if .5<abs(angle)<18:
   ph,pw=page.shape[:2];matrix=cv2.getRotationMatrix2D((pw/2,ph/2),angle,1)
   cos,sin=abs(matrix[0,0]),abs(matrix[0,1]);nw=int(ph*sin+pw*cos);nh=int(ph*cos+pw*sin)
   matrix[0,2]+=(nw-pw)/2;matrix[1,2]+=(nh-ph)/2
   page=cv2.warpAffine(page,matrix,(nw,nh),borderValue=(255,255,255))
 gray=cv2.cvtColor(page,cv2.COLOR_RGB2GRAY)
 # Flatten slow illumination variation; preserve the original RGB for digit crops.
 background=cv2.GaussianBlur(gray,(0,0),21)
 normalized=cv2.divide(gray,background,scale=255)
 return page,normalized

def ocr_rows(data,page):
 """Map OCR lines to editable fields and use the digit model for simple numeric answers."""
 lines={}
 for i,t in enumerate(data['text']):
  if t.strip():lines.setdefault((data['block_num'][i],data['par_num'][i],data['line_num'][i]),[]).append(i)
 rows=[]
 for indices in lines.values():
  text=' '.join(data['text'][i] for i in indices)
  if ':' in text:label,value=text.split(':',1)
  else:label,value=f'Línea {len(rows)+1}',text
  conf=max(0,min(float(data['conf'][i]) for i in indices)/100)
  source='OCR de formulario'
  numeric=bool(re.search(r'\b(edad|nota|importe|monto|pago|cantidad|puntaje)\b',label,re.I))
  if numeric and text.count(':')==1:
   colon=next((j for j,i in enumerate(indices) if ':' in data['text'][i]),None)
   answer=indices[colon+1:] if colon is not None else []
   if answer:
    x=min(data['left'][i] for i in answer);y=min(data['top'][i] for i in answer)
    right=max(data['left'][i]+data['width'][i] for i in answer);bottom=max(data['top'][i]+data['height'][i] for i in answer)
    H,W=page.shape[:2];pad=5
    crop=page[max(0,y-pad):min(H,bottom+pad),max(0,x-pad):min(W,right+pad)]
    predicted,scores,_=classify_crop(crop)
    if predicted:
     value=predicted;conf=min(scores);source='OCR + modelo de dígitos'
  rows.append({'label':label.strip()[:100],'value':value.strip(),'confidence':conf,'source':source,'review':True})
 return rows
def model():
 global MODEL
 if MODEL is None: MODEL=joblib.load(Path(__file__).parent/'models/digits.joblib')
 return MODEL
def decode(file):
 im=Image.open(file)
 if im.width*im.height>24000000: raise ValueError('La foto supera 24 megapíxeles. Reduce su tamaño.')
 im=ImageOps.exif_transpose(im).convert('RGB')
 im.thumbnail((1800,2400)); return np.array(im)
def classify_crop(rgb):
 gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
 mask=cv2.threshold(gray,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)[1]
 # Remove long form rules before connected-component segmentation.
 for kernel in [(max(60,int(mask.shape[1]*.9)),1),(1,max(60,int(mask.shape[0]*.9)))]:
  lines=cv2.morphologyEx(mask,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,kernel))
  # Only remove rules near crop boundaries; retain long strokes of 1 and 7.
  edge=np.zeros_like(mask);margin=max(2,int(min(mask.shape)*.06))
  edge[:margin,:]=255;edge[-margin:,:]=255;edge[:,:margin]=255;edge[:,-margin:]=255
  mask=cv2.subtract(mask,cv2.bitwise_and(lines,edge))
 count,labels,stats,_=cv2.connectedComponentsWithStats(mask)
 boxes=[]
 for x,y,w,h,area in stats[1:]:
  if area>=8 and h>=max(5,mask.shape[0]*.12) and w<mask.shape[1]*.96: boxes.append((int(x),int(y),int(w),int(h)))
 if not boxes:return '',[],[]
 boxes.sort(key=lambda z:z[0]); digits=[]; scores=[]
 for x,y,w,h in boxes[:24]:
  cut=mask[y:y+h,x:x+w]; size=max(w,h)+max(4,int(h*.25)); padded=np.zeros((size,size),np.uint8)
  padded[(size-h)//2:(size-h)//2+h,(size-w)//2:(size-w)//2+w]=cut
  global PHOTO
  if (Path(__file__).parent/'models/photo.joblib').exists():
   if PHOTO is None:PHOTO=joblib.load(Path(__file__).parent/'models/photo.joblib')
   # MNIST uses a roughly 20px ink box centered in a 28px canvas.
   scale=20/max(w,h); sw=max(1,round(w*scale));sh=max(1,round(h*scale))
   ink=cv2.resize(cut,(sw,sh),interpolation=cv2.INTER_AREA); canvas=np.zeros((28,28),np.uint8)
   canvas[(28-sh)//2:(28-sh)//2+sh,(28-sw)//2:(28-sw)//2+sw]=ink
   moments=cv2.moments(canvas)
   if moments['m00']:
    shift=np.float32([[1,0,13.5-moments['m10']/moments['m00']],[0,1,13.5-moments['m01']/moments['m00']]])
    canvas=cv2.warpAffine(canvas,shift,(28,28))
   sample=cv2.HOGDescriptor((28,28),(14,14),(7,7),(7,7),9).compute(canvas).reshape(1,-1); estimator=PHOTO
  else:sample=cv2.resize(padded,(8,8),interpolation=cv2.INTER_AREA).reshape(1,-1)/255;estimator=model()
  proba=estimator.predict_proba(sample)[0]; idx=int(np.argmax(proba)); digits.append(str(estimator.classes_[idx])); scores.append(round(float(proba[idx]),3))
 return ''.join(digits),scores,boxes
def extract(rgb,regions=None):
 rows=[]; warnings=[]
 if regions:
  H,W=rgb.shape[:2]
  for i,r in enumerate(regions[:40]):
   x=max(0,min(W-1,int(float(r['x'])*W))); y=max(0,min(H-1,int(float(r['y'])*H)))
   w=max(1,min(W-x,int(float(r['w'])*W))); h=max(1,min(H-y,int(float(r['h'])*H)))
   value,scores,_=classify_crop(rgb[y:y+h,x:x+w]); conf=min(scores) if scores else 0
   rows.append({'label':str(r.get('label',f'Campo {i+1}'))[:100],'value':value,'confidence':conf,'source':'Modelo de dígitos','review':True})
 else:
  try:
   import pytesseract
   from pytesseract import Output
   status=ocr_status()
   if not status['available']:raise pytesseract.TesseractNotFoundError()
   page,prepared=prepare_page(rgb)
   data=pytesseract.image_to_data(prepared,lang='+'.join(status['languages']),config='--psm 6',output_type=Output.DICT,timeout=75)
   rows=ocr_rows(data,page)
   warnings.append('El OCR funciona mejor con rótulos impresos. Para números manuscritos selecciona sus regiones y usa el modelo. Confirma cada respuesta.')
  except ImportError:
   logger.error('OCR Python dependency unavailable')
   warnings.append('Falta un componente del motor de lectura. Puedes marcar los campos numéricos mientras se corrige el servicio.')
  except pytesseract.TesseractNotFoundError:
   logger.error('OCR engine or language data unavailable')
   warnings.append('El motor de lectura automática no está instalado o no tiene los idiomas necesarios. Puedes marcar los campos numéricos mientras se corrige el servicio.')
  except RuntimeError as error:
   if 'timeout' in str(error).lower():
    logger.warning('OCR timed out after the bounded processing interval')
    warnings.append('La lectura de esta foto superó el tiempo disponible. Recorta solo la hoja o procesa una sección. También puedes marcar las respuestas numéricas.')
   else:
    logger.error('OCR runtime failure: %s',type(error).__name__)
    warnings.append('No se pudo completar la lectura automática de esta imagen. Prueba recortando y enderezando la hoja o marca los campos numéricos.')
  except Exception as error:
   logger.error('OCR processing failure: %s',type(error).__name__)
   warnings.append('Ocurrió un error al procesar esta foto. Prueba una imagen de la hoja completa, con buena luz, o marca los campos numéricos.')
 if not rows: warnings.append('No se reconocieron campos. Usa «Marcar campos» y dibuja alrededor de cada respuesta numérica.')
 return {'fields':rows,'warnings':warnings,'requires_review':True}
