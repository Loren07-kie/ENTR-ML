import os, json, sqlite3, secrets, io, csv, re
import threading,time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from functools import wraps
from datetime import datetime, timezone
from flask import Flask, request, jsonify, session, render_template, Response
from werkzeug.security import generate_password_hash, check_password_hash
from vision import decode, extract, ocr_status
from handwriting import available as handwriting_available
from storage import db,initialize,storage_info
ROOT=Path(__file__).parent
app=Flask(__name__)
app.config.update(SECRET_KEY=os.environ.get('SECRET_KEY') or secrets.token_hex(32),MAX_CONTENT_LENGTH=12*1024*1024,SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Lax',SESSION_COOKIE_SECURE=os.environ.get('RENDER')=='true')
JOBS={};JOB_LOCK=threading.RLock();EXECUTOR=ThreadPoolExecutor(max_workers=1,thread_name_prefix='form-reader')
initialize()
def auth(fn):
 @wraps(fn)
 def wrapper(*a,**k):
  if not session.get('uid'):return jsonify(error='Inicia sesión para continuar.'),401
  if request.method not in ('GET','HEAD') and request.headers.get('X-CSRF-Token')!=session.get('csrf'):return jsonify(error='Sesión vencida. Actualiza la página.'),403
  return fn(*a,**k)
 return wrapper
def actor():return session.get('uid') or 'guest:'+session['visitor']
def owns(job):return job.get('owner') in (session.get('uid'),'guest:'+session.get('visitor',''))
def visitor(fn):
 @wraps(fn)
 def wrapper(*a,**k):
  if not session.get('visitor'):session['visitor']=secrets.token_hex(18)
  if request.method not in ('GET','HEAD') and (not session.get('csrf') or request.headers.get('X-CSRF-Token')!=session.get('csrf')):return jsonify(error='Actualiza la página e intenta de nuevo.'),403
  return fn(*a,**k)
 return wrapper
@app.get('/')
def home():return render_template('index.html')
@app.get('/health')
def health():return {'status':'ok','model':(ROOT/'models/digits.joblib').exists(),'ocr':ocr_status(),'handwriting':handwriting_available(),'reader_version':3,'storage':storage_info()['kind']}
@app.get('/api/me')
def me():
 if not session.get('visitor'):session['visitor']=secrets.token_hex(18)
 if not session.get('csrf'):session['csrf']=secrets.token_hex(24)
 with db() as c:u=c.execute('SELECT id,name,email,logins,onboarded FROM users WHERE id=?',(session.get('uid'),)).fetchone()
 return jsonify(user=dict(u) if u else None,csrf=session.get('csrf'),storage=storage_info(),capabilities={'single_page':True,'folders':bool(u),'account_history':bool(u),'local_history':True,'payment_required':False})
@app.post('/api/auth/<action>')
def login(action):
 if request.headers.get('Sec-Fetch-Site')=='cross-site':return jsonify(error='Origen no permitido'),403
 d=request.get_json() or {}; email=str(d.get('email','')).strip().lower(); password=str(d.get('password',''))
 if action not in ('login','register'):return jsonify(error='Acción inválida'),400
 if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or len(password)<8 or len(password)>200:return jsonify(error='Usa un correo válido y contraseña de 8 a 200 caracteres.'),400
 with db() as c:
  if action=='register':
   name=str(d.get('name','')).strip()[:80]
   if not name:return jsonify(error='Escribe tu nombre.'),400
   inserted=c.execute('INSERT INTO users(email,name,password) VALUES(?,?,?) ON CONFLICT(email) DO NOTHING',(email,name,generate_password_hash(password)))
   if inserted.rowcount==0:return jsonify(error='Este correo ya está registrado. Inicia sesión.'),409
  u=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
  if not u or not check_password_hash(u['password'],password):return jsonify(error='Correo o contraseña incorrectos.'),401
  c.execute('UPDATE users SET logins=logins+1 WHERE id=?',(u['id'],))
 guest=session.get('visitor') or secrets.token_hex(18)
 session.clear(); session.update(uid=u['id'],visitor=guest,csrf=secrets.token_hex(24))
 return jsonify(ok=True,guide=not u['onboarded'] and u['logins']<1)
@app.post('/api/logout')
@auth
def logout():session.clear();return {'ok':True}
@app.post('/api/onboard')
@auth
def onboard():
 with db() as c:c.execute('UPDATE users SET onboarded=1,profile=? WHERE id=?',(json.dumps(request.get_json()),session['uid']))
 return {'ok':True}
@app.post('/api/extract')
@visitor
def process():
 f=request.files.get('image')
 if not f:return jsonify(error='Selecciona una imagen PNG, JPG o WEBP.'),400
 try:
  rgb=decode(f.stream); regions=json.loads(request.form.get('regions','[]'))
  if not isinstance(regions,list):raise ValueError('Regiones inválidas.')
  return jsonify(extract(rgb,regions))
 except (ValueError,KeyError,TypeError) as e:return jsonify(error=str(e)),400
 except Exception:app.logger.exception('Extraction failed');return jsonify(error='No se pudo leer la foto. Prueba una imagen clara, JPG o PNG.'),422
@app.route('/api/forms',methods=['GET','POST'])
@auth
def forms():
 with db() as c:
  if request.method=='GET':return jsonify([form_json(r) for r in c.execute('SELECT id,user_id,title,fields,created,status,batch_id,filename,error,(image IS NOT NULL) AS has_image FROM forms WHERE user_id=? ORDER BY id DESC',(session['uid'],))])
  d=(request.get_json(silent=True) or {}) if not request.files else {'title':request.form.get('title'),'fields':json.loads(request.form.get('fields','[]'))}
  fields=d.get('fields',[])
  if not fields or len(fields)>100 or not all(isinstance(f,dict) and f.get('confirmed') is True and str(f.get('label','')).strip() and len(str(f.get('label','')))<101 and len(str(f.get('value','')))<2000 for f in fields):return jsonify(error='Revisa y confirma los campos antes de guardar.'),400
  # Image snippets exist only during review and must never be persisted.
  fields=safe_fields(fields);image=None
  if request.files.get('image'):image=encode_image(request.files['image'].stream)
  fid=c.execute('INSERT INTO forms(user_id,title,fields,created,status,image,filename) VALUES(?,?,?,?,?,?,?) RETURNING id',(session['uid'],str(d.get('title') or 'Formulario')[:120],json.dumps(fields,ensure_ascii=False),datetime.now(timezone.utc).isoformat(),'reviewed',image,str(request.files['image'].filename)[:180] if image else None)).fetchone()['id']
 return {'ok':True,'id':fid}

def safe_fields(fields):return [{k:v for k,v in f.items() if k in {'label','value','confirmed','type','options','status','confidence','source'}} for f in fields]
def form_json(row):
 result=dict(row);result['fields']=json.loads(result['fields'] or '[]');return result
def encode_image(stream):
 from PIL import Image
 image=Image.fromarray(decode(stream));image.thumbnail((1600,2000));out=io.BytesIO();image.save(out,'JPEG',quality=88);return out.getvalue()

@app.route('/api/forms/<int:fid>',methods=['GET','PUT'])
@auth
def form_detail(fid):
 with db() as c:
  row=c.execute('SELECT id,user_id,title,fields,created,status,batch_id,filename,error,(image IS NOT NULL) AS has_image FROM forms WHERE id=? AND user_id=?',(fid,session['uid'])).fetchone()
  if not row:return {'error':'Formulario no encontrado.'},404
  if request.method=='GET':return jsonify(form_json(row))
  data=request.get_json() or {};fields=data.get('fields',[])
  if not fields or len(fields)>100 or not all(isinstance(f,dict) and f.get('confirmed') is True and str(f.get('label','')).strip() and len(str(f.get('value','')))<2000 for f in fields):return {'error':'Confirma todos los campos antes de guardar.'},400
  c.execute('UPDATE forms SET fields=?,title=?,status=?,updated=? WHERE id=? AND user_id=?',(json.dumps(safe_fields(fields),ensure_ascii=False),str(data.get('title') or row['title'])[:120],'reviewed',datetime.now(timezone.utc).isoformat(),fid,session['uid']))
 return {'ok':True,'id':fid}

@app.get('/api/forms/<int:fid>/image')
@auth
def form_image(fid):
 with db() as c:row=c.execute('SELECT image FROM forms WHERE id=? AND user_id=?',(fid,session['uid'])).fetchone()
 if not row or not row['image']:return {'error':'Imagen no disponible.'},404
 return Response(bytes(row['image']),mimetype='image/jpeg',headers={'Cache-Control':'private, max-age=300'})

def run_job(job_id,rgb,regions,mode):
 def progress(message,fraction):
  with JOB_LOCK:
   job=JOBS.get(job_id)
   if not job or job.get('cancel'):raise InterruptedError()
   job.update(state='running',message=message,progress=round(fraction,2))
 try:
  progress('Preparando la lectura',.03)
  from reader import read_document
  result=read_document(rgb,regions,mode,progress)
  with JOB_LOCK:
   job=JOBS.get(job_id)
   if job and not job.get('cancel'):job.update(state='done',message='Lectura lista para revisar',progress=1,result=result)
 except InterruptedError:
  with JOB_LOCK:
   if job_id in JOBS:JOBS[job_id].update(state='cancelled',message='Lectura cancelada')
 except Exception as error:
  app.logger.error('Form job failed: %s',type(error).__name__)
  with JOB_LOCK:
   if job_id in JOBS:JOBS[job_id].update(state='error',message='No se pudo completar esta lectura. Prueba una foto más clara o marca los campos numéricos.')

@app.post('/api/jobs')
@visitor
def create_job():
 with JOB_LOCK:
  now=time.monotonic()
  for key in list(JOBS):
   if now-JOBS[key]['created']>900 and JOBS[key]['state'] not in ('queued','running'):JOBS.pop(key)
  active=[j for j in JOBS.values() if j['state'] in ('queued','running')]
  if any(owns(j) for j in active):return jsonify(error='Ya tienes una lectura en proceso. Espera o cancélala.'),429
  if len(active)>=3:return jsonify(error='El lector está ocupado. Intenta de nuevo en un momento.'),429
 f=request.files.get('image')
 if not f:return jsonify(error='Selecciona una foto.'),400
 try:
  rgb=decode(f.stream);regions=json.loads(request.form.get('regions','[]'))
  if not isinstance(regions,list):raise ValueError('Regiones inválidas.')
 except Exception:return jsonify(error='La imagen o las regiones no son válidas.'),400
 with JOB_LOCK:
  job_id=secrets.token_urlsafe(18)
  JOBS[job_id]={'owner':actor(),'created':time.monotonic(),'state':'queued','message':'En cola de lectura','progress':0}
 EXECUTOR.submit(run_job,job_id,rgb,regions,request.form.get('mode','structured'))
 return jsonify(id=job_id,state='queued'),202

@app.get('/api/jobs/<job_id>')
@visitor
def read_job(job_id):
 with JOB_LOCK:
  job=JOBS.get(job_id)
  if not job or not owns(job):return jsonify(error='Lectura no encontrada o vencida.'),404
  return jsonify({k:v for k,v in job.items() if k not in {'owner','created','cancel'}})

@app.post('/api/jobs/<job_id>/cancel')
@visitor
def cancel_job(job_id):
 with JOB_LOCK:
  job=JOBS.get(job_id)
  if not job or not owns(job):return jsonify(error='Lectura no encontrada.'),404
  job.update(cancel=True,state='cancelled',message='Lectura cancelada');job.pop('result',None)
 return {'ok':True}
@app.get('/api/metrics')
def metrics():
 m=json.loads((ROOT/'models/metrics.json').read_text())
 if (ROOT/'models/photo_metrics.json').exists():m['photo']=json.loads((ROOT/'models/photo_metrics.json').read_text())
 if (ROOT/'models/forms_training_metrics.json').exists():m['forms_training']=json.loads((ROOT/'models/forms_training_metrics.json').read_text())
 return m
@app.get('/api/export/<int:fid>')
@auth
def export(fid):
 with db() as c:r=c.execute('SELECT fields FROM forms WHERE id=? AND user_id=?',(fid,session['uid'])).fetchone()
 if not r:return {'error':'No encontrado'},404
 out=io.StringIO(); w=csv.writer(out); w.writerow(['Campo','Respuesta','Revisado'])
 for f in json.loads(r['fields']):
  safe=lambda v: "'"+str(v) if str(v).startswith(('=','+','-','@')) else str(v)
  w.writerow([safe(f.get('label','')),safe(f.get('value','')),bool(f.get('confirmed'))])
 return Response('\ufeff'+out.getvalue(),mimetype='text/csv',headers={'Content-Disposition':f'attachment; filename=formulario-{fid}.csv'})
@app.errorhandler(413)
def too_big(e):return jsonify(error='La foto debe pesar menos de 12 MB.'),413
from bulk import make_blueprint
app.register_blueprint(make_blueprint(auth,EXECUTOR))
if __name__=='__main__':app.run(host='0.0.0.0',port=int(os.environ.get('PORT',8000)))
