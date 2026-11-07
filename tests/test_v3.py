import unittest,io,json,time,uuid
from unittest.mock import patch
from pathlib import Path
from PIL import Image
from app import app
from analysis_engine import summarize
ROOT=Path(__file__).resolve().parents[1]
def png():
 f=io.BytesIO();Image.new('RGB',(300,200),'white').save(f,'PNG');f.seek(0);return f
class V3Tests(unittest.TestCase):
 def account(self):
  c=app.test_client();c.post('/api/auth/register',json={'name':'Test','email':uuid.uuid4().hex+'@example.test','password':'test-only-123'});return c,{'X-CSRF-Token':c.get('/api/me').json['csrf']}
 def test_one_page_is_available_without_login_and_private(self):
  c=app.test_client();me=c.get('/api/me').json;self.assertIsNone(me['user']);self.assertTrue(me['capabilities']['single_page'])
  expected={'fields':[{'label':'Edad','value':'20','review':True}],'warnings':[]}
  with patch('reader.read_document',return_value=expected):
   r=c.post('/api/jobs',data={'image':(png(),'page.png')},headers={'X-CSRF-Token':me['csrf']});self.assertEqual(r.status_code,202);path='/api/jobs/'+r.json['id']
   for _ in range(100):
    state=c.get(path).json
    if state['state']=='done':break
    time.sleep(.01)
   self.assertEqual(state['result'],expected)
  self.assertEqual(app.test_client().get(path).status_code,404)
 def test_folder_routes_require_account(self):
  c=app.test_client();csrf=c.get('/api/me').json['csrf']
  self.assertEqual(c.post('/api/batches',json={'title':'x'},headers={'X-CSRF-Token':csrf}).status_code,401)
 def test_saved_form_reopens_with_full_fields_and_private_image(self):
  c,h=self.account();data={'title':'Guardado','fields':json.dumps([{'label':'Edad','value':'20','confirmed':True},{'label':'Nota','value':'18','confirmed':True}]),'image':(png(),'original.png')}
  r=c.post('/api/forms',data=data,headers=h);self.assertEqual(r.status_code,200);fid=r.json['id']
  detail=c.get('/api/forms/'+str(fid));self.assertEqual(len(detail.json['fields']),2);self.assertTrue(detail.json['has_image']);self.assertEqual(c.get(f'/api/forms/{fid}/image').status_code,200)
  other,_=self.account();self.assertEqual(other.get(f'/api/forms/{fid}').status_code,404);self.assertEqual(other.get(f'/api/forms/{fid}/image').status_code,404)
 def test_batch_stores_drafts_and_review_enables_final_analysis(self):
  c,h=self.account();bid=c.post('/api/batches',json={'title':'Mi carpeta'},headers=h).json['id']
  uploaded=c.post(f'/api/batches/{bid}/items',data={'image':(png(),'one.png'),'path':'carpeta/one.png'},headers=h);self.assertEqual(uploaded.status_code,201);fid=uploaded.json['id']
  result={'fields':[{'label':'Nota','value':'18','confirmed':False}],'warnings':[]}
  with patch('reader.read_document',return_value=result):
   self.assertEqual(c.post(f'/api/batches/{bid}/start',headers=h).status_code,202)
   for _ in range(200):
    state=c.get(f'/api/batches/{bid}').json
    if state['status'] in ('done','partial'):break
    time.sleep(.01)
   self.assertEqual(state['counts'].get('draft'),1)
  final=c.get('/api/analysis?batch_id='+bid).json;provisional=c.get('/api/analysis?batch_id='+bid+'&provisional=1').json
  self.assertEqual(final['forms_analyzed'],0);self.assertEqual(provisional['forms_analyzed'],1)
  self.assertEqual(c.put('/api/forms/'+str(fid),json={'fields':[{'label':'Nota','value':'17','confirmed':True}]},headers=h).status_code,200)
  self.assertEqual(c.get('/api/analysis?batch_id='+bid).json['fields'][0]['mean'],17)
  self.assertEqual(c.get('/api/export/all.csv?batch_id='+bid).status_code,200)
  other,oh=self.account();self.assertEqual(other.get('/api/batches/'+bid).status_code,404)
 def test_aggregate_keeps_fields_units_and_identifiers_separate(self):
  rows=[{'status':'reviewed','fields':[{'label':'DNI','value':'99999999'},{'label':'Nota','value':'10'},{'label':'Importe','value':'100'},{'label':'Turno','value':'Mañana'}]},{'status':'reviewed','fields':[{'label':'Nota','value':'20'},{'label':'Importe','value':'200'},{'label':'Turno','value':'Mañana'}]}]
  stats=summarize(rows);fields={f['label']:f for f in stats['fields']};self.assertNotIn('DNI',fields);self.assertEqual(fields['Nota']['mean'],15);self.assertNotIn('sum',fields['Nota']);self.assertEqual(fields['Importe']['sum'],300);self.assertEqual(fields['Turno']['frequencies'][0]['percent'],100)
 def test_template_response_changes_with_image_not_filename(self):
  from form_templates import read_template
  import numpy as np
  a=read_template(np.array(Image.open(ROOT/'static/examples/educacion/educacion-01.png').convert('RGB')))
  b=read_template(np.array(Image.open(ROOT/'static/examples/educacion/educacion-02.png').convert('RGB')))
  self.assertEqual(a['template_id'],'educacion');self.assertEqual(b['template_id'],'educacion')
  va={f['label']:f['value'] for f in a['fields']};vb={f['label']:f['value'] for f in b['fields']};self.assertNotEqual(va['Participante'],vb['Participante'])
if __name__=='__main__':unittest.main()
