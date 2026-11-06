"""Layout-aware form reader. Labels, handwriting, blanks and checkboxes stay separate."""
import base64, io, re, time, unicodedata
import cv2, numpy as np
from difflib import get_close_matches
from PIL import Image
from handwriting import available,read_line
from vision import prepare_page,classify_crop,ocr_status

def norm(text):return ''.join(c for c in unicodedata.normalize('NFD',text.lower()) if unicodedata.category(c)!='Mn')
def read_printed(image,psm=11):
 import pytesseract
 from pytesseract import Output
 languages=ocr_status()['languages']
 return pytesseract.image_to_data(image,lang='+'.join(languages) or 'spa',config=f'--psm {psm}',output_type=Output.DICT,timeout=55)

def rectify(image):
 """Rectify a visible four-corner sheet; otherwise retain the deskewed whole photo."""
 h,w=image.shape[:2];scale=min(1,900/max(h,w));small=cv2.resize(image,(round(w*scale),round(h*scale)))
 hsv=cv2.cvtColor(small,cv2.COLOR_RGB2HSV)
 paper=cv2.inRange(hsv,np.array([0,0,115]),np.array([179,80,255]))
 paper=cv2.morphologyEx(paper,cv2.MORPH_CLOSE,np.ones((15,15),np.uint8))
 contours=cv2.findContours(paper,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[0]
 for c in sorted(contours,key=cv2.contourArea,reverse=True)[:5]:
  if cv2.contourArea(c)<small.shape[0]*small.shape[1]*.35:continue
  poly=cv2.approxPolyDP(c,.025*cv2.arcLength(c,True),True)
  if len(poly)!=4 or not cv2.isContourConvex(poly):continue
  pts=poly[:,0].astype(np.float32)/scale
  sums=pts.sum(1);diff=np.diff(pts,axis=1).ravel()
  ordered=np.array([pts[np.argmin(sums)],pts[np.argmin(diff)],pts[np.argmax(sums)],pts[np.argmax(diff)]],np.float32)
  width=int(max(np.linalg.norm(ordered[1]-ordered[0]),np.linalg.norm(ordered[2]-ordered[3])))
  height=int(max(np.linalg.norm(ordered[3]-ordered[0]),np.linalg.norm(ordered[2]-ordered[1])))
  if min(width,height)<200:continue
  matrix=cv2.getPerspectiveTransform(ordered,np.array([[0,0],[width-1,0],[width-1,height-1],[0,height-1]],np.float32))
  image=cv2.warpPerspective(image,matrix,(width,height),borderValue=(255,255,255));break
 return prepare_page(image)[0]

def ink_mask(page):
 hsv=cv2.cvtColor(page,cv2.COLOR_RGB2HSV)
 mask=cv2.inRange(hsv,np.array([98,55,25]),np.array([137,255,245]))
 rgb=page.astype(np.int16)
 mask[(rgb[:,:,2]-rgb[:,:,0]<45)|(rgb[:,:,2]-rgb[:,:,1]<42)]=0
 # Separate long printed form rules from blue handwriting.
 for kernel in [(max(70,page.shape[1]//8),1),(1,max(70,page.shape[0]//8))]:
  lines=cv2.morphologyEx(mask,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,kernel))
  mask=cv2.subtract(mask,lines)
 rules=cv2.HoughLinesP(mask,1,np.pi/180,threshold=70,minLineLength=max(80,page.shape[1]//7),maxLineGap=15)
 if rules is not None:
  for x1,y1,x2,y2 in rules[:,0]:
   if abs(y2-y1)<abs(x2-x1)*.12:
    path=np.zeros_like(mask);cv2.line(path,(x1,y1),(x2,y2),255,1)
    coverage=np.count_nonzero(cv2.bitwise_and(path,mask))/max(1,np.count_nonzero(path))
    if coverage>.92:cv2.line(mask,(x1,y1),(x2,y2),0,2)
 n,lab,stats,_=cv2.connectedComponentsWithStats(mask)
 clean=np.zeros_like(mask)
 for i,(x,y,w,h,area) in enumerate(stats[1:],1):
  if area>=3 and h>=3:clean[lab==i]=255
 return clean

KNOWN=re.compile(r'^(nombres?|apellidos?|nombre y apellidos|fecha(?: de (?:nacimiento|registro))?|direccion|telefono|numero de telefono|sexo|codigo postal|correo electronico|email|seguro proveniente|numero de poliza|carrera|periodo|institucion de procedencia|nivel alcanzado|ciclo|departamento|provincia|distrito|edad|dni|importe|nota|monto|cantidad|mi meta emocional|mis emociones frecuentes|motivo de la visita|otro)$')
CANONICAL=['Nombres','Apellidos','Nombre y Apellidos','Fecha de Nacimiento','Fecha de Registro','Dirección','Teléfono','Sexo','Código Postal','Correo Electrónico','Email','Carrera','Periodo','Institución de Procedencia','Nivel Alcanzado','Ciclo','Departamento','Provincia','Distrito','Edad','DNI','Mi meta emocional','Mis emociones frecuentes','Motivo de la visita']
def labels_from_data(data):
 groups={}
 for i,text in enumerate(data['text']):
  if text.strip() and float(data['conf'][i])>=20:groups.setdefault((data['block_num'][i],data['par_num'][i],data['line_num'][i]),[]).append(i)
 labels=[];expanded=[]
 for indices in groups.values():
  indices.sort(key=lambda i:data['left'][i]);part=[]
  spacing=max(35,float(np.median([data['height'][i] for i in indices]))*2.5)
  for i in indices:
   if part and data['left'][i]-(data['left'][part[-1]]+data['width'][part[-1]])>spacing:
    expanded.append(part);part=[]
   part.append(i)
  if part:expanded.append(part)
 for indices in expanded:
  indices.sort(key=lambda i:data['left'][i]);segments=[];current=[]
  for i in indices:
   current.append(i)
   if ':' in data['text'][i]:segments.append(current);current=[]
  if current:segments.append(current)
  for seg in segments:
   while seg and not re.search(r'[A-Za-zÀ-ÿ]',data['text'][seg[0]]):seg=seg[1:]
   while seg and not re.search(r'[A-Za-zÀ-ÿ]',data['text'][seg[-1]]) and ':' not in data['text'][seg[-1]]:seg=seg[:-1]
   if not seg:continue
   text=' '.join(data['text'][i] for i in seg)
   label=re.sub(r'^[^\w¿]+','',text).strip().rstrip(':').strip()
   plain=norm(label)
   if re.search(r'^[ivxl1n]{1,4}\s+semestre',plain):continue
   question='?' in label and ('¿' in label or plain.startswith(('como ','que ','por que ')))
   colon=':' in text
   if not KNOWN.fullmatch(plain) and not question:
    names={norm(s):s for s in CANONICAL};matches=get_close_matches(plain,names,n=1,cutoff=.86)
    if matches:label=names[matches[0]];plain=matches[0]
   if plain=='otro' and not colon:continue
   if not label or len(label)>85 or any(t in plain for t in ['www.','logo','@','firma del','recuerda','recordatorio']):continue
   if len(label)<2:continue
   if not (question or KNOWN.fullmatch(plain) or colon):continue
   if colon and len(label.split())>12:continue
   if not question and not KNOWN.fullmatch(plain) and np.mean([float(data['conf'][i]) for i in seg])<70:continue
   x=min(data['left'][i] for i in seg);y=int(np.median([data['top'][i] for i in seg]))
   right=max(data['left'][i]+data['width'][i] for i in seg);bottom=y+int(np.median([data['height'][i] for i in seg]))
   labels.append({'label':label,'box':(x,y,right,bottom),'question':question,'colon':colon})
 return sorted(labels,key=lambda l:(l['box'][1],l['box'][0]))

def heading_blocks(data):
 groups={}
 for i,t in enumerate(data['text']):
  if t.strip():groups.setdefault((data['block_num'][i],data['par_num'][i],data['line_num'][i]),[]).append(i)
 out=[]
 for indices in groups.values():
  text=' '.join(data['text'][i] for i in indices)
  if len(text)>12 and text.isupper() and ':' not in text:
   x=min(data['left'][i] for i in indices);y=int(np.median([data['top'][i] for i in indices]));r=max(data['left'][i]+data['width'][i] for i in indices);b=y+int(np.median([data['height'][i] for i in indices]))
   out.append({'label':text,'box':(x,y,r,b),'question':False,'colon':False})
 return out

def checkbox_boxes(page):
 gray=cv2.cvtColor(page,cv2.COLOR_RGB2GRAY);binary=cv2.threshold(gray,140,255,cv2.THRESH_BINARY_INV)[1]
 hsv=cv2.cvtColor(page,cv2.COLOR_RGB2HSV);colored=cv2.inRange(hsv,np.array([0,22,150]),np.array([179,255,255]))
 contours=list(cv2.findContours(binary,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)[0])+list(cv2.findContours(colored,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)[0]);boxes=[]
 limit=max(40,int(page.shape[1]*.06));minimum=max(14,int(page.shape[1]*.018))
 for contour in sorted(contours,key=cv2.contourArea,reverse=True):
  x,y,w,h=cv2.boundingRect(contour)
  if not (minimum<=w<=limit and minimum<=h<=limit and .65<w/h<1.5):continue
  poly=cv2.approxPolyDP(contour,.035*cv2.arcLength(contour,True),True)
  if not 4<=len(poly)<=8 or cv2.contourArea(contour)<w*h*.5:continue
  if any(abs(x-a)<w*.5 and abs(y-b)<h*.5 for a,b,_,_ in boxes):continue
  boxes.append((x,y,w,h))
 return sorted(boxes,key=lambda b:(b[1],b[0]))

def panels(page):
 gray=cv2.cvtColor(page,cv2.COLOR_RGB2GRAY);mask=cv2.threshold(gray,170,255,cv2.THRESH_BINARY_INV)[1]
 contours=cv2.findContours(mask,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)[0];out=[];H,W=gray.shape
 for c in contours:
  x,y,w,h=cv2.boundingRect(c)
  if w>W*.2 and h>H*.045 and w*h<W*H*.6 and cv2.contourArea(c)>w*h*.55:out.append((x,y,x+w,y+h))
 return out

def bound(box,W,H):
 x,y,r,b=box;return (max(0,int(x)),max(0,int(y)),min(W,int(r)),min(H,int(b)))

def value_box(label,labels,boxes,W,H):
 x,y,r,b=label['box'];height=max(12,b-y)
 next_on_line=[a['box'][0] for a in labels if a is not label and a['box'][0]>r and abs(a['box'][1]-y)<height*1.6]
 right=min(next_on_line)-8 if next_on_line else W-15
 paragraph=norm(label['label']) in ('mi meta emocional','mis emociones frecuentes','motivo de la visita')
 if not label['question'] and not paragraph:
  return bound((r+5,y-height*.8,right,b+height*.65),W,H)
 candidates=[p for p in boxes if p[0]<=x+15 and p[1]<=b+15 and p[2]>=r-15 and p[3]>b+height*1.5 and p[3]-p[1]<H*.35]
 if candidates:
  p=min(candidates,key=lambda p:(p[2]-p[0])*(p[3]-p[1]));return bound((p[0]+8,b+3,p[2]-8,p[3]-8),W,H)
 below=[a['box'][1] for a in labels if a is not label and a['box'][1]>b+8 and abs(a['box'][0]-x)<W*.25]
 bottom=min(below)-8 if below else min(H-10,b+H*.13)
 other_column=[a['box'][0] for a in labels if a is not label and a['box'][0]>r and abs(a['box'][1]-y)<H*.08]
 return bound((x,b+4,min(other_column)-12 if other_column else right,bottom),W,H)

def snippet(page,box):
 x,y,r,b=box
 if r<=x or b<=y:return None
 im=Image.fromarray(page[y:b,x:r]);im.thumbnail((600,150));out=io.BytesIO();im.save(out,'JPEG',quality=75)
 return 'data:image/jpeg;base64,'+base64.b64encode(out.getvalue()).decode()

def handwriting_lines(mask):
 mask=mask.copy()
 if mask.size==0:return []
 # Border remnants must not become extra digits or underscore tokens.
 count,components,stats,_=cv2.connectedComponentsWithStats(mask)
 for i,(x,y,w,h,area) in enumerate(stats[1:],1):
  if (w>max(30,h*8) and h<7) or (w<5 and h>mask.shape[0]*.6 and x>mask.shape[1]*.85):mask[components==i]=0
 counts=np.count_nonzero(mask,axis=1)
 active=counts>max(3,float(counts.max())*.13)
 rows=np.flatnonzero(active)
 if not len(rows):return []
 chunks=[];start=previous=int(rows[0])
 for y in rows[1:]:
  if y-previous>max(5,mask.shape[0]*.025):chunks.append((start,previous+1));start=int(y)
  previous=int(y)
 chunks.append((start,previous+1));result=[]
 tallest=max(b-a for a,b in chunks)
 for a,b in chunks:
  if b-a<max(5,tallest*.4):continue
  a=max(0,a-3);b=min(mask.shape[0],b+3)
  part=mask[a:b];ys,xs=np.where(part>0)
  if len(xs)<15 or b-a<5:continue
  cut=part[:,max(0,int(xs.min())-3):int(xs.max())+4]
  occupied=np.flatnonzero(np.count_nonzero(cut,axis=0)>0)
  if len(occupied):
   gaps=np.flatnonzero(np.diff(occupied)>max(35,(b-a)*2.5))
   if len(gaps):cut=cut[:,:int(occupied[gaps[0]])+2]
  cut=cv2.copyMakeBorder(cut,5,5,7,7,cv2.BORDER_CONSTANT,value=0)
  result.append(cv2.cvtColor(255-cut,cv2.COLOR_GRAY2RGB))
 return result

def response_ink(page,ink,box):
 x,y,r,b=box;mask=ink[y:b,x:r].copy()
 if mask.size:
  vertical=cv2.morphologyEx(mask,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,(1,max(35,int(mask.shape[0]*.65)))))
  if mask.shape[0]<=70:
   vertical[:,8:-8]=0
  mask=cv2.subtract(mask,vertical)
 if mask.size and np.count_nonzero(mask)<18:
  # A black-ink answer can be read too; labels were excluded geometrically.
  gray=cv2.cvtColor(page[y:b,x:r],cv2.COLOR_RGB2GRAY)
  dark=cv2.inRange(gray,0,100)
  for kernel in [(max(35,dark.shape[1]//3),1),(1,max(35,int(dark.shape[0]*.8)))]:
   rules=cv2.morphologyEx(dark,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,kernel));dark=cv2.subtract(dark,rules)
  mask=dark
 return mask

def recognize(mask,label):
 if np.count_nonzero(mask)<18:return '',0.,'empty',[]
 lines=handwriting_lines(mask)
 if not lines:return '',0.,'empty',[]
 text=[];scores=[];alternatives=[];plain=norm(label)
 numeric=bool(re.fullmatch(r'(dni|edad|telefono|numero de telefono|codigo postal|nota|importe|monto|cantidad)',plain))
 native_scores=[];native_text=[]
 for line in lines[:5]:
  try:
   data=read_printed(cv2.cvtColor(line,cv2.COLOR_RGB2GRAY),7)
   tokens=[(t,float(c)) for t,c in zip(data['text'],data['conf']) if t.strip() and float(c)>=0]
   native=' '.join(t for t,c in tokens);native_score=float(np.mean([c for t,c in tokens]))/100 if tokens else 0.
  except Exception:native='';native_score=0.
  native_text.append(native);native_scores.append(native_score)
  if numeric:
   value,probs,_=classify_crop(line);score=min(probs) if probs else 0
   digits=re.sub(r'\D','',native)
   if native_score>.65 and re.fullmatch(r'[\d\s]+',native.strip()) and digits:value=digits;score=native_score
   if value:text.append(value);scores.append(score)
  else:
   value,score=read_line(line,max_tokens=80)
   if value:text.append(value);scores.append(score)
 value=' '.join(text).strip();score=float(np.mean(scores)) if scores else 0.
 native=' '.join(native_text).strip();native_score=float(np.mean(native_scores)) if native_scores else 0.
 if native and norm(native)!=norm(value):
  alternatives=[{'value':native,'source':'OCR español del recorte','score':round(native_score,3)}]
  if (native_score>.82 and score<.9) or (plain in ('correo electronico','email') and re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+',re.sub(r'\s+','',native))):
   alternatives=[{'value':value,'source':'TrOCR manuscrito','score':round(score,3)}];value=native;score=native_score
 value=re.sub(r'\s+[_|]+\s*$','',value).strip()
 if plain=='edad':
  m=re.match(r'\s*(\d{1,3})\b',value)
  if m:value=m.group(1)
 if plain in ('correo electronico','email'):
  value=re.sub(r'\s+','',value)
  if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+',value):score=min(score,.3)
 if plain=='dni' and not re.fullmatch(r'\d{8}',value):score=min(score,.3)
 if 'fecha' in plain:
  from datetime import date
  for proposal in [native,value]:
   match=re.search(r'(\d{1,2})\D+(\d{1,2})\D+(\d{4})',proposal)
   if match:
    day,month,year=map(int,match.groups())
    try:date(year,month,day)
    except ValueError:continue
    value=f'{day:02}/{month:02}/{year}';break
 if value and sum(c.isalnum() for c in value)<len(value)*.4:value='';score=0.
 if score<.45 and value:
  alternatives.insert(0,{'value':value,'source':'Propuesta de baja confianza: verificar en el recorte','score':round(score,3)})
  value=''
 return value,score,'uncertain' if score<.85 or alternatives else 'read',alternatives

def read_form(rgb,progress=None):
 started=time.monotonic()
 if progress:progress('Enderezando la hoja y separando la tinta',.08)
 page=rectify(rgb);H,W=page.shape[:2];ink=ink_mask(page)
 # The blue channel keeps dark printed text and suppresses blue handwriting.
 gray=page[:,:,2].copy();gray=cv2.divide(gray,cv2.GaussianBlur(gray,(0,0),21),scale=255)
 # Suppress pale watermarks and colored page backgrounds in the printed-label pass.
 gray=cv2.threshold(gray,165,255,cv2.THRESH_BINARY)[1]
 if progress:progress('Localizando rótulos, columnas y opciones',.18)
 data=read_printed(gray);labels=labels_from_data(data);blockers=heading_blocks(data);panel_boxes=panels(page);checks=checkbox_boxes(page)
 fields=[];handled=set()
 for i,label in enumerate(labels[:45]):
  if progress:progress(f'Leyendo campo {i+1} de {min(45,len(labels))}',.25+.65*i/max(1,len(labels)))
  x,y,r,b=label['box'];plain=norm(label['label'])
  group=bool(re.search(r'^(sexo|periodo|mis emociones frecuentes|opciones|seleccion)',plain))
  field={'label':label['label'],'value':'','confidence':0.,'source':'TrOCR gratuito + detección de campos','review':True,'type':'text','status':'empty'}
  if group:
   lower=[a['box'][1] for a in labels if a is not label and a['box'][1]>b+15 and abs(a['box'][0]-x)<W*.3]
   bottom=min(lower) if lower else b+H*.2
   choices=[(k,c) for k,c in enumerate(checks) if c[0]>=x-15 and y-8<=c[1]<bottom and (abs(c[1]-y)<(b-y)*2.5 or 'emociones' in plain)]
   options=[]
   for k,(cx,cy,cw,ch) in choices:
    handled.add(k);pad=max(3,int(cw*.22));inside=ink[cy+pad:cy+ch-pad,cx+pad:cx+cw-pad]
    selected=np.count_nonzero(inside)>max(4,inside.size*.07)
    next_boxes=[c[0] for _,c in choices if c[0]>cx+cw and abs(c[1]-cy)<ch]
    right=int(min(next_boxes)-8 if next_boxes else min(W-8,cx+cw+W*.25))
    words=[j for j,t in enumerate(data['text']) if t.strip() and data['left'][j]>cx+cw and data['left'][j]<right and abs(data['top'][j]-cy)<ch*.9]
    option=' '.join(data['text'][j] for j in sorted(words,key=lambda j:data['left'][j])).strip()
    option=re.sub(r'^[^\wÀ-ÿ]+','',option).strip().rstrip(':')
    if not option:
     crop=ink[max(0,cy-ch//2):min(H,cy+ch+ch//2),cx+cw+3:right]
     option,_,_,_=recognize(crop,'opción')
    options.append({'label':option or f'Opción {len(options)+1}','checked':bool(selected)})
   field.update(type='checkbox',options=options,value='; '.join(o['label'] for o in options if o['checked']),confidence=0.,status='uncertain' if any(o['checked'] for o in options) else 'empty',source='Detección visual de casillas')
   field['snippet']=snippet(page,(x,y,W-10,min(H,bottom)))
  else:
   box=value_box(label,labels+blockers,panel_boxes,W,H)
   # Questions can have an inline response rather than a paragraph below.
   next_fields=[a['box'][0] for a in labels if a is not label and a['box'][0]>r and abs(a['box'][1]-y)<(b-y)*1.2]
   inline=bound((r+5,y-(b-y)*.8,min(next_fields)-8 if next_fields else W-10,b+(b-y)*.6),W,H)
   ix,iy,ir,ib=inline
   if label['question'] and ir-ix>W*.18 and np.count_nonzero(ink[iy:ib,ix:ir])>35:box=inline
   vx,vy,vr,vb=box
   value,score,status,alternatives=recognize(response_ink(page,ink,box),label['label'])
   field.update(value=value,confidence=round(score,3),status=status,alternatives=alternatives,snippet=snippet(page,box),bbox=[vx/W,vy/H,(vr-vx)/W,(vb-vy)/H])
  fields.append(field)
 if progress:progress('Preparando el formulario revisable',.96)
 return {'fields':fields,'requires_review':True,'warnings':['Lectura gratuita de texto manuscrito: revisa cada propuesta con su recorte. Los scores no garantizan exactitud. Los espacios sin tinta quedan vacíos; las casillas se leen por separado.'],'summary':{'fields':len(fields),'blank':sum(f['status']=='empty' for f in fields),'uncertain':sum(f['status']=='uncertain' for f in fields),'checkbox_groups':sum(f['type']=='checkbox' for f in fields),'seconds':round(time.monotonic()-started,2),'engine':'TrOCR ONNX + Tesseract + OpenCV'}}

def read_regions(rgb,regions,progress=None):
 from vision import extract
 H,W=rgb.shape[:2];fields=[]
 for i,r in enumerate(regions[:40]):
  if progress:progress(f'Leyendo selección {i+1} de {len(regions)}',.1+.8*i/max(1,len(regions)))
  if r.get('type','digits')!='text':
   field=extract(rgb,[r])['fields'][0];field['status']='uncertain' if field['value'] else 'empty';fields.append(field);continue
  x,y,right,bottom=bound((float(r['x'])*W,float(r['y'])*H,(float(r['x'])+float(r['w']))*W,(float(r['y'])+float(r['h']))*H),W,H)
  crop=rgb[y:bottom,x:right]
  if crop.size==0:continue
  value,score,status,alternatives=recognize(response_ink(crop,ink_mask(crop),(0,0,crop.shape[1],crop.shape[0])),str(r.get('label','Texto')))
  fields.append({'label':str(r.get('label',f'Campo {i+1}'))[:100],'value':value,'confidence':round(score,3),'status':status,'source':'Selección manual + TrOCR gratuito','review':True,'type':'text','alternatives':alternatives,'snippet':snippet(rgb,(x,y,right,bottom))})
 return {'fields':fields,'warnings':['Revisa cada selección con su imagen. Puedes cambiar la lectura alternativa o corregir el texto.'],'requires_review':True}
