"""Image preprocessing, conservative digit segmentation and optional OCR."""
from pathlib import Path
import cv2, numpy as np, joblib
from PIL import Image, ImageOps
MODEL=None
PHOTO=None
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
   data=pytesseract.image_to_data(rgb,lang='spa+eng',config='--psm 6',output_type=Output.DICT,timeout=30)
   lines={}
   for i,t in enumerate(data['text']):
    if t.strip():lines.setdefault((data['block_num'][i],data['par_num'][i],data['line_num'][i]),[]).append((t,float(data['conf'][i])))
   for i,tokens in enumerate(lines.values()):
    text=' '.join(t[0] for t in tokens); label,value=(text.split(':',1) if ':' in text else (f'Línea {i+1}',text))
    rows.append({'label':label.strip(),'value':value.strip(),'confidence':max(0,min(t[1] for t in tokens)/100),'source':'OCR de formulario','review':True})
   warnings.append('El OCR funciona mejor con rótulos impresos. Para números manuscritos selecciona sus regiones y usa el modelo. Confirma cada respuesta.')
  except Exception:
   warnings.append('OCR no disponible en esta instalación. Selecciona los campos numéricos sobre la foto o crea campos manuales.')
 if not rows: warnings.append('No se reconocieron campos. Usa «Marcar campos» y dibuja alrededor de cada respuesta numérica.')
 return {'fields':rows,'warnings':warnings,'requires_review':True}
