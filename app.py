import os, json, sqlite3, secrets, io, csv, re
import threading,time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from functools import wraps
from contextlib import contextmanager
from datetime import datetime, timezone
from flask import Flask, request, jsonify, session, render_template, Response
from werkzeug.security import generate_password_hash, check_password_hash
from vision import decode, extract, ocr_status
from handwriting import available as handwriting_available
ROOT=Path(__file__).parent
app=Flask(__name__)
app.config.update(SECRET_KEY=os.environ.get('SECRET_KEY') or secrets.token_hex(32),MAX_CONTENT_LENGTH=12*1024*1024,SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Lax',SESSION_COOKIE_SECURE=os.environ.get('RENDER')=='true')
DB=Path(os.environ.get('DATA_DIR',str(ROOT/'instance'))); DB.mkdir(parents=True,exist_ok=True)
JOBS={};JOB_LOCK=threading.RLock();EXECUTOR=ThreadPoolExecutor(max_workers=1,thread_name_prefix='form-reader')
@contextmanager
def db():
 c=sqlite3.connect(DB/'tecnoforms.db'); c.row_factory=sqlite3.Row
 try:
  with c:yield c
 finally:c.close()
with db() as c:
 c.executescript('CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,email TEXT UNIQUE,name TEXT,password TEXT,logins INTEGER DEFAULT 0,onboarded INTEGER DEFAULT 0,profile TEXT); CREATE TABLE IF NOT EXISTS forms(id INTEGER PRIMARY KEY,user_id INTEGER,title TEXT,fields TEXT,created TEXT);')
def auth(fn):
 @wraps(fn)
 def wrapper(*a,**k):
  if not session.get('uid'):return jsonify(error='Inicia sesión para continuar.'),401
  if request.method not in ('GET','HEAD') and request.headers.get('X-CSRF-Token')!=session.get('csrf'):return jsonify(error='Sesión vencida. Actualiza la página.'),403
  return fn(*a,**k)
 return wrapper
@app.get('/')
def home():return render_template('index.html')
@app.get('/health')
def health():return {'status':'ok','model':(ROOT/'models/digits.joblib').exists(),'ocr':ocr_status(),'handwriting':handwriting_available(),'reader_version':2}
@app.get('/api/me')
def me():
 with db() as c:u=c.execute('SELECT id,name,email,logins,onboarded FROM users WHERE id=?',(session.get('uid'),)).fetchone()
 return jsonify(user=dict(u) if u else None,csrf=session.get('csrf'))
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
   try:c.execute('INSERT INTO users(email,name,password) VALUES(?,?,?)',(email,name,generate_password_hash(password)))
   except sqlite3.IntegrityError:return jsonify(error='Este correo ya está registrado. Inicia sesión.'),409
  u=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
  if not u or not check_password_hash(u['password'],password):return jsonify(error='Correo o contraseña incorrectos.'),401
  c.execute('UPDATE users SET logins=logins+1 WHERE id=?',(u['id'],))
 session.clear(); session.update(uid=u['id'],csrf=secrets.token_hex(24))
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
@auth
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
  if request.method=='GET':return jsonify([dict(r)|{'fields':json.loads(r['fields'])} for r in c.execute('SELECT * FROM forms WHERE user_id=? ORDER BY id DESC',(session['uid'],))])
  d=request.get_json() or {}; fields=d.get('fields',[])
  if not fields or len(fields)>100 or not all(isinstance(f,dict) and f.get('confirmed') is True and str(f.get('label','')).strip() and len(str(f.get('label','')))<101 and len(str(f.get('value','')))<2000 for f in fields):return jsonify(error='Revisa y confirma los campos antes de guardar.'),400
  # Image snippets exist only during review and must never be persisted.
  fields=[{k:v for k,v in f.items() if k in {'label','value','confirmed','type','options','status','confidence','source'}} for f in fields]
  c.execute('INSERT INTO forms(user_id,title,fields,created) VALUES(?,?,?,?)',(session['uid'],str(d.get('title','Formulario'))[:120],json.dumps(fields,ensure_ascii=False),datetime.now(timezone.utc).isoformat()))
 return {'ok':True}

def run_job(job_id,rgb,regions,mode):
 def progress(message,fraction):
  with JOB_LOCK:
   job=JOBS.get(job_id)
   if not job or job.get('cancel'):raise InterruptedError()
   job.update(state='running',message=message,progress=round(fraction,2))
 try:
  progress('Preparando la lectura',.03)
  if regions:
   from form_reader import read_regions
   result=read_regions(rgb,regions,progress)
  elif mode=='classic':result=extract(rgb)
  elif handwriting_available():
   from form_reader import read_form
   result=read_form(rgb,progress)
  else:
   result=extract(rgb)
   result['warnings'].insert(0,'El lector manuscrito aún no está preparado en este servidor. Se usó el lector básico; revisa sus resultados.')
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
@auth
def create_job():
 with JOB_LOCK:
  now=time.monotonic()
  for key in list(JOBS):
   if now-JOBS[key]['created']>900 and JOBS[key]['state'] not in ('queued','running'):JOBS.pop(key)
  active=[j for j in JOBS.values() if j['state'] in ('queued','running')]
  if any(j['owner']==session['uid'] for j in active):return jsonify(error='Ya tienes una lectura en proceso. Espera o cancélala.'),429
  if len(active)>=3:return jsonify(error='El lector está ocupado. Intenta de nuevo en un momento.'),429
 f=request.files.get('image')
 if not f:return jsonify(error='Selecciona una foto.'),400
 try:
  rgb=decode(f.stream);regions=json.loads(request.form.get('regions','[]'))
  if not isinstance(regions,list):raise ValueError('Regiones inválidas.')
 except Exception:return jsonify(error='La imagen o las regiones no son válidas.'),400
 with JOB_LOCK:
  job_id=secrets.token_urlsafe(18)
  JOBS[job_id]={'owner':session['uid'],'created':time.monotonic(),'state':'queued','message':'En cola de lectura','progress':0}
 EXECUTOR.submit(run_job,job_id,rgb,regions,request.form.get('mode','structured'))
 return jsonify(id=job_id,state='queued'),202

@app.get('/api/jobs/<job_id>')
@auth
def read_job(job_id):
 with JOB_LOCK:
  job=JOBS.get(job_id)
  if not job or job['owner']!=session['uid']:return jsonify(error='Lectura no encontrada o vencida.'),404
  return jsonify({k:v for k,v in job.items() if k not in {'owner','created','cancel'}})

@app.post('/api/jobs/<job_id>/cancel')
@auth
def cancel_job(job_id):
 with JOB_LOCK:
  job=JOBS.get(job_id)
  if not job or job['owner']!=session['uid']:return jsonify(error='Lectura no encontrada.'),404
  job.update(cancel=True,state='cancelled',message='Lectura cancelada');job.pop('result',None)
 return {'ok':True}
@app.get('/api/metrics')
def metrics():
 m=json.loads((ROOT/'models/metrics.json').read_text())
 if (ROOT/'models/photo_metrics.json').exists():m['photo']=json.loads((ROOT/'models/photo_metrics.json').read_text())
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
if __name__=='__main__':app.run(host='0.0.0.0',port=int(os.environ.get('PORT',8000)))
