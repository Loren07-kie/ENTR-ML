"""Account-only folder processing, persistent drafts and aggregate analysis."""
import io,json,secrets,threading,tempfile,zipfile,csv
from pathlib import Path,PurePosixPath
from datetime import datetime,timezone
from flask import Blueprint,request,session,jsonify,Response,send_file
from PIL import Image
import numpy as np
from storage import db
from vision import decode
from analysis_engine import summarize,key
ROOT=Path(__file__).parent
LOCK=threading.RLock();ACTIVE=set();MAX_FILES=30
META='id,title,created,status,batch_id,filename,error,(image IS NOT NULL) AS has_image'
def now():return datetime.now(timezone.utc).isoformat()
def clean_fields(fields):return [{k:v for k,v in f.items() if k in {'label','value','confirmed','type','options','status','confidence','source'}} for f in fields]
def image_bytes(stream):
 image=Image.fromarray(decode(stream));image.thumbnail((1600,2000));out=io.BytesIO();image.save(out,'JPEG',quality=90);return out.getvalue()
def counts(c,bid):return {r['status']:r['n'] for r in c.execute('SELECT status,COUNT(*) AS n FROM forms WHERE batch_id=? GROUP BY status',(bid,))}
def batch_json(c,row):
 result=dict(row);result['counts']=counts(c,row['id']);result['total']=sum(result['counts'].values());result['completed']=sum(result['counts'].get(k,0) for k in ('draft','reviewed','error','cancelled'));return result
def form_rows(owner,bid=None):
 with db() as c:
  sql='SELECT '+META+',fields FROM forms WHERE user_id=?';params=[owner]
  if bid:sql+=' AND batch_id=?';params.append(bid)
  return [dict(r)|{'fields':json.loads(r['fields'] or '[]')} for r in c.execute(sql+' ORDER BY id',tuple(params))]
def csv_bytes(rows):
 columns={};flat=[]
 for row in rows:
  data={'Formulario':row['id'],'Título':row['title'],'Estado':row['status']};occurrences={}
  for f in row['fields']:
   label=key(f.get('label',''));occurrences[label]=occurrences.get(label,0)+1;canonical=label+(f' [{occurrences[label]}]' if occurrences[label]>1 else '')
   columns.setdefault(canonical,f['label']+(f' [{occurrences[label]}]' if occurrences[label]>1 else ''));data[canonical]=f.get('value','')
  flat.append(data)
 output=io.StringIO();writer=csv.writer(output);writer.writerow(['Formulario','Título','Estado',*columns.values()])
 def safe(value):
  text=str(value);return "'"+text if text.startswith(('=','+','-','@')) else text
 for row in flat:writer.writerow([safe(row.get(k,'')) for k in ['Formulario','Título','Estado',*columns]])
 return ('\ufeff'+output.getvalue()).encode('utf-8')

def make_blueprint(auth,executor):
 bp=Blueprint('folders',__name__)
 def owned(c,bid):return c.execute('SELECT * FROM batches WHERE id=? AND user_id=?',(bid,session['uid'])).fetchone()
 def finish_or_continue(bid):
  with db() as c:
   row=c.execute('SELECT status FROM batches WHERE id=?',(bid,)).fetchone()
   if not row or row['status']=='cancelled':
    with LOCK:ACTIVE.discard(bid)
    return
   pending=c.execute("SELECT COUNT(*) AS n FROM forms WHERE batch_id=? AND status='queued'",(bid,)).fetchone()['n']
   if not pending:
    failed=c.execute("SELECT COUNT(*) AS n FROM forms WHERE batch_id=? AND status='error'",(bid,)).fetchone()['n']
    c.execute('UPDATE batches SET status=?,updated=?,message=? WHERE id=?',('partial' if failed else 'done',now(),'Lectura terminada. Revisa las propuestas antes del análisis definitivo.',bid))
    with LOCK:ACTIVE.discard(bid)
    return
  executor.submit(process_next,bid)
 def process_next(bid):
  fid=None
  try:
   with db() as c:
    batch=c.execute('SELECT * FROM batches WHERE id=?',(bid,)).fetchone()
    if not batch or batch['status']=='cancelled':
     with LOCK:ACTIVE.discard(bid)
     return
    row=c.execute("SELECT id,image,filename FROM forms WHERE batch_id=? AND status='queued' ORDER BY id LIMIT 1",(bid,)).fetchone()
    if not row:finish_or_continue(bid);return
    fid=row['id'];data=bytes(row['image']);filename=row['filename'] or f'Formulario {fid}'
    c.execute("UPDATE forms SET status='processing',updated=? WHERE id=?",(now(),fid));c.execute('UPDATE batches SET status=?,message=?,updated=? WHERE id=?',('running','Leyendo '+filename,now(),bid))
   def progress(message,fraction):
    with db() as c:
     state=c.execute('SELECT status FROM batches WHERE id=?',(bid,)).fetchone()
     if not state or state['status']=='cancelled':raise InterruptedError()
     c.execute('UPDATE batches SET message=?,updated=? WHERE id=?',(filename+' · '+message,now(),bid))
   from reader import read_document
   result=read_document(decode(io.BytesIO(data)),progress=progress)
   fields=clean_fields(result['fields'])
   for f in fields:f['confirmed']=False
   with db() as c:c.execute('UPDATE forms SET fields=?,status=?,error=?,updated=? WHERE id=?',(json.dumps(fields,ensure_ascii=False),'draft' if fields else 'error',None if fields else 'No se detectaron campos; abre la imagen para añadirlos.',now(),fid))
  except InterruptedError:
   if fid:
    with db() as c:c.execute('UPDATE forms SET status=?,updated=? WHERE id=?',('cancelled',now(),fid))
  except Exception as error:
   if fid:
    with db() as c:c.execute('UPDATE forms SET status=?,error=?,updated=? WHERE id=?',('error','No se pudo leer esta imagen ('+type(error).__name__+'). Puedes revisarla manualmente.',now(),fid))
  finally:finish_or_continue(bid)
 def schedule(bid):
  with LOCK:
   if bid in ACTIVE:return
   ACTIVE.add(bid)
  with db() as c:
   c.execute("UPDATE forms SET status='queued' WHERE batch_id=? AND status='processing'",(bid,));c.execute("UPDATE batches SET status='running',updated=? WHERE id=?",(now(),bid))
  executor.submit(process_next,bid)

 @bp.route('/api/batches',methods=['GET','POST'])
 @auth
 def batches():
  with db() as c:
   if request.method=='GET':
    rows=[batch_json(c,r) for r in c.execute('SELECT * FROM batches WHERE user_id=? ORDER BY created DESC',(session['uid'],))]
   else:
    data=request.get_json() or {};bid=secrets.token_urlsafe(15);timestamp=now()
    c.execute('INSERT INTO batches(id,user_id,title,status,created,updated,message) VALUES(?,?,?,?,?,?,?)',(bid,session['uid'],str(data.get('title') or 'Mi carpeta')[:120],'uploading',timestamp,timestamp,'Subiendo imágenes'))
    return {'id':bid,'max_files':MAX_FILES},201
  for row in rows:
   if row['status']=='running':schedule(row['id'])
  return jsonify(rows)

 @bp.route('/api/batches/<bid>',methods=['GET'])
 @auth
 def batch_detail(bid):
  with db() as c:
   row=owned(c,bid)
   if not row:return {'error':'Carpeta no encontrada.'},404
   result=batch_json(c,row);result['forms']=[dict(r) for r in c.execute('SELECT '+META+' FROM forms WHERE batch_id=? AND user_id=? ORDER BY id',(bid,session['uid']))]
  if result['status']=='running':schedule(bid)
  return jsonify(result)

 @bp.post('/api/batches/<bid>/items')
 @auth
 def upload(bid):
  f=request.files.get('image')
  if not f:return {'error':'Selecciona una imagen JPG, PNG o WEBP.'},400
  try:data=image_bytes(f.stream)
  except Exception:return {'error':'No se pudo abrir esta imagen.'},400
  filename=str(PurePosixPath(str(request.form.get('path') or f.filename).replace('\\','/')))[-200:]
  with LOCK,db() as c:
   batch=owned(c,bid)
   if not batch:return {'error':'Carpeta no encontrada.'},404
   if batch['status'] not in ('uploading','ready'):return {'error':'La carpeta ya se está procesando.'},409
   total=c.execute('SELECT COUNT(*) AS n FROM forms WHERE batch_id=?',(bid,)).fetchone()['n']
   if total>=MAX_FILES:return {'error':f'El límite por carpeta es {MAX_FILES} imágenes.'},400
   fid=c.execute('INSERT INTO forms(user_id,title,fields,created,status,batch_id,filename,image) VALUES(?,?,?,?,?,?,?,?) RETURNING id',(session['uid'],PurePosixPath(filename).stem[:120],'[]',now(),'queued',bid,filename,data)).fetchone()['id']
  return {'ok':True,'id':fid},201

 @bp.post('/api/batches/<bid>/start')
 @auth
 def start(bid):
  with db() as c:
   row=owned(c,bid)
   if not row:return {'error':'Carpeta no encontrada.'},404
   if not sum(counts(c,bid).values()):return {'error':'La carpeta está vacía.'},400
   c.execute("UPDATE forms SET status='queued',error=NULL WHERE batch_id=? AND status IN ('cancelled','error')",(bid,))
  schedule(bid);return {'ok':True},202

 @bp.post('/api/batches/<bid>/cancel')
 @auth
 def cancel(bid):
  with db() as c:
   if not owned(c,bid):return {'error':'Carpeta no encontrada.'},404
   c.execute('UPDATE batches SET status=?,message=?,updated=? WHERE id=?',('cancelled','Lectura cancelada; los resultados terminados se conservan.',now(),bid));c.execute("UPDATE forms SET status='cancelled' WHERE batch_id=? AND status='queued'",(bid,))
  return {'ok':True}

 @bp.get('/api/analysis')
 @auth
 def analysis():return jsonify(summarize(form_rows(session['uid'],request.args.get('batch_id') or None),request.args.get('provisional')=='1'))

 @bp.get('/api/export/all.csv')
 @auth
 def export_all():return Response(csv_bytes(form_rows(session['uid'],request.args.get('batch_id') or None)),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=tecnoforms-respuestas.csv'})

 @bp.get('/api/backup.zip')
 @auth
 def backup():
  rows=form_rows(session['uid'],request.args.get('batch_id') or None);out=tempfile.TemporaryFile()
  with zipfile.ZipFile(out,'w',zipfile.ZIP_STORED) as z:
   z.writestr('formularios.json',json.dumps(rows,ensure_ascii=False,indent=2,default=str));z.writestr('respuestas.csv',csv_bytes(rows))
   for row in rows:
    with db() as c:image=c.execute('SELECT image FROM forms WHERE id=? AND user_id=?',(row['id'],session['uid'])).fetchone()
    if image and image['image']:z.writestr(f'imagenes/formulario-{row["id"]}.jpg',bytes(image['image']))
  out.seek(0);response=send_file(out,mimetype='application/zip',as_attachment=True,download_name='tecnoforms-respaldo.zip');response.call_on_close(out.close);return response

 @bp.get('/api/examples')
 def examples():return json.loads((ROOT/'static/examples/manifest.json').read_text(encoding='utf-8'))

 @bp.post('/api/examples/<kind>/batch')
 @auth
 def example_batch(kind):
  manifest=json.loads((ROOT/'static/examples/manifest.json').read_text(encoding='utf-8'));entry=next((e for e in manifest if e['id']==kind),None)
  if not entry:return {'error':'Ejemplo no encontrado.'},404
  bid=secrets.token_urlsafe(15);timestamp=now()
  with db() as c:
   c.execute('INSERT INTO batches(id,user_id,title,status,created,updated,message) VALUES(?,?,?,?,?,?,?)',(bid,session['uid'],entry['title']+' · ejemplo ficticio','ready',timestamp,timestamp,'Ejemplos preparados'))
   for item in entry['files']:
    with (ROOT/'static/examples'/kind/item['filename']).open('rb') as stream:data=image_bytes(stream)
    c.execute('INSERT INTO forms(user_id,title,fields,created,status,batch_id,filename,image) VALUES(?,?,?,?,?,?,?,?)',(session['uid'],Path(item['filename']).stem,'[]',timestamp,'queued',bid,item['filename'],data))
  schedule(bid);return {'id':bid},202
 return bp
