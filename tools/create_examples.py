"""Generate three public fictitious uses and 18 held-out forms. QR contains template ID only."""
from pathlib import Path
import sys,json,zipfile,csv,io,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np,cv2,qrcode
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'static/examples';OUT.mkdir(parents=True,exist_ok=True)
def font(size,bold=False):
 for file in ([f'C:/Windows/Fonts/arial{"bd" if bold else ""}.ttf',f'/usr/share/fonts/truetype/dejavu/DejaVuSans{"-Bold" if bold else ""}.ttf']):
  if Path(file).exists():return ImageFont.truetype(file,size)
 return ImageFont.load_default(size=size)
SPECS={
 'educacion':{'title':'Educación · progreso del aula','color':'#7046bf','fields':[('Participante','id',4),('Edad','number',2),('Nota','number',2),('Asistencia','number',3),('Turno','checkbox',['Mañana','Tarde'])]},
 'pagos':{'title':'Pagos · control de ingresos','color':'#126d8c','fields':[('Participante','id',4),('Importe','number',4),('Cantidad','number',2),('Canal','checkbox',['Efectivo','Transferencia'])]},
 'encuesta':{'title':'Encuesta · experiencia del servicio','color':'#b64278','fields':[('Participante','id',4),('Edad','number',2),('Satisfacción','number',1),('Recomendaría','checkbox',['Sí','No']),('Comentario','printed',None)]}}

def make_layout(kind):
 spec=SPECS[kind];im=Image.new('RGB',(1000,1300),'#f2f1f7');d=ImageDraw.Draw(im)
 d.rounded_rectangle((30,30,970,1270),radius=28,fill='white');d.rounded_rectangle((55,55,945,225),radius=18,fill=spec['color'])
 d.text((80,76),'TECNOFORMS',font=font(32,True),fill='white');d.text((80,128),spec['title'],font=font(27,True),fill='white');d.text((80,180),'Datos ficticios · ejemplo reproducible',font=font(18),fill='white')
 qr=qrcode.make('TecnoForms:v3:'+kind).convert('RGB').resize((150,150),Image.Resampling.NEAREST);im.paste(qr,(780,66))
 registry={'width':1000,'height':1300,'title':spec['title'],'fields':[]}
 for i,(label,typ,argument) in enumerate(spec['fields']):
  y=280+i*160;d.text((80,y),label,font=font(25,True),fill='#27283b');field={'label':label,'type':typ}
  if typ in ('id','number'):
   field['cells']=[]
   for n in range(argument):
    x=360+n*100;d.rounded_rectangle((x,y-8,x+86,y+90),radius=9,outline='#b5b2c8',width=2);field['cells'].append([x+10,y+3,x+76,y+79])
  elif typ=='checkbox':
   field['options']=[]
   for n,choice in enumerate(argument):
    x=360+n*260;d.rectangle((x,y+7,x+35,y+42),outline='#555366',width=2);d.text((x+48,y+5),choice,font=font(22),fill='#363449');field['options'].append({'label':choice,'box':[x,y+7,x+35,y+42]})
  else:
   field['box']=[80,y+45,920,y+105];d.rounded_rectangle(tuple(field['box']),radius=8,outline='#b5b2c8',width=2)
  registry['fields'].append(field)
 d.text((80,1175),'1. Completa  2. Fotografía  3. Digitaliza  4. Revisa',font=font(21),fill=spec['color']);d.text((80,1210),'El QR identifica el diseño; no contiene respuestas.',font=font(17),fill='#686477')
 detector=cv2.QRCodeDetector();text,points,_=detector.detectAndDecode(np.array(im))
 if text!='TecnoForms:v3:'+kind:raise RuntimeError('QR de plantilla no detectable')
 registry['qr_quad']=points[0].tolist();return im,registry

def main():
 data=np.load(ROOT/'data/mnist.npz');digits=data['x_test'];labels=data['y_test'];rng=np.random.default_rng(427)
 registry={};manifest=[];truth=[]
 values={
 'educacion':[[1001,18,12,70,'Mañana'],[1002,20,15,85,'Tarde'],[1003,19,18,95,'Mañana'],[1004,22,16,90,'Tarde'],[1005,18,20,100,'Mañana'],[1006,21,14,80,'Tarde']],
 'pagos':[[2001,150,2,'Efectivo'],[2002,220,3,'Transferencia'],[2003,100,1,'Efectivo'],[2004,350,5,'Transferencia'],[2005,180,2,'Transferencia'],[2006,200,4,'Efectivo']],
 'encuesta':[[3001,24,5,'Sí','El servicio fue rápido y claro'],[3002,30,4,'Sí','Me gustó la atención'],[3003,22,3,'No','Podrían reducir la espera'],[3004,28,5,'Sí','Buena atención y rapidez'],[3005,35,2,'No','Necesito instrucciones más claras'],[3006,26,4,'Sí','Fue fácil completar el trámite']]}
 for kind in SPECS:
  folder=OUT/kind;folder.mkdir(exist_ok=True);blank,layout=make_layout(kind);registry[kind]=layout;blank.save(folder/'plantilla-vacia.png')
  items=[]
  for i,row in enumerate(values[kind]):
   im=blank.copy();draw=ImageDraw.Draw(im);answers={}
   for field,value in zip(layout['fields'],row):
    answers[field['label']]=str(value)
    if field['type'] in ('id','number'):
     text=str(value).zfill(len(field['cells']))
     for box,char in zip(field['cells'],text):
      candidates=np.flatnonzero(labels==int(char));index=int(rng.choice(candidates));x,y,right,bottom=box
      ink=Image.fromarray(255-digits[index]).resize((right-x,bottom-y),Image.Resampling.BICUBIC);im.paste(ink,(x,y))
    elif field['type']=='checkbox':
     box=next(o['box'] for o in field['options'] if o['label']==value);x,y,r,b=box;draw.line((x+7,y+7,r-7,b-7),fill='#28448c',width=4);draw.line((r-7,y+7,x+7,b-7),fill='#28448c',width=4)
    else:draw.text((field['box'][0]+15,field['box'][1]+16),str(value),font=font(23),fill='#242332')
   name=f'{kind}-{i+1:02}.png';im.save(folder/name);items.append({'filename':name,'url':f'/static/examples/{kind}/{name}'})
   truth.append({'file':kind+'/'+name,'template':kind,'answers':answers,'split':'MNIST official test / demo evaluation only'})
  archive=OUT/(kind+'.zip')
  with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
   for item in items:z.write(folder/item['filename'],kind+'/'+item['filename'])
  manifest.append({'id':kind,'title':SPECS[kind]['title'],'description':{'educacion':'Notas, asistencia, edades y turnos de seis estudiantes ficticios.','pagos':'Importes, cantidades y medios de pago de seis registros ficticios.','encuesta':'Satisfacción, recomendación y comentarios de seis participantes ficticios.'}[kind],'preview':items[0]['url'],'blank':f'/static/examples/{kind}/plantilla-vacia.png','folder_zip':f'/static/examples/{kind}.zip','files':items,'count':len(items)})
 (ROOT/'models/form_templates.json').write_text(json.dumps(registry,ensure_ascii=False,indent=2),encoding='utf-8')
 (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8');(OUT/'respuestas-ficticias.json').write_text(json.dumps(truth,ensure_ascii=False,indent=2),encoding='utf-8')
 with zipfile.ZipFile(OUT/'tres-carpetas.zip','w',zipfile.ZIP_DEFLATED) as z:
  for row in truth:z.write(OUT/row['file'],row['file'])
  z.write(OUT/'respuestas-ficticias.json','respuestas-ficticias.json')
 print('Generados 18 formularios, 3 plantillas vacías y 4 ZIP de carpetas.')
if __name__=='__main__':main()
