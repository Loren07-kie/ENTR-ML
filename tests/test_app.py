import unittest, tempfile, os, io, json
from pathlib import Path
test_root=Path(__file__).resolve().parents[1]/'instance'
test_root.mkdir(exist_ok=True)
os.environ['DATA_DIR']=tempfile.mkdtemp(prefix='test-',dir=test_root)
from app import app
from PIL import Image
class Integration(unittest.TestCase):
 def setUp(self):self.c=app.test_client()
 def login(self,email):
  r=self.c.post('/api/auth/register',json={'name':'Prueba','email':email,'password':'test-only-123'});self.assertEqual(r.status_code,200)
  return self.c.get('/api/me').json['csrf']
 def test_full_flow_and_isolation(self):
  self.assertEqual(self.c.get('/api/forms').status_code,401)
  token=self.login('primero@example.test');headers={'X-CSRF-Token':token}
  self.assertEqual(self.c.post('/api/forms',json={'fields':[]}).status_code,403)
  self.assertTrue(self.c.post('/api/onboard',json={'use':'Educación'},headers=headers).json['ok'])
  fields=[{'label':'Nota','value':'18','confirmed':True},{'label':'CSV','value':'=1+1','confirmed':True}]
  self.assertEqual(self.c.post('/api/forms',json={'title':'Prueba','fields':fields},headers=headers).status_code,200)
  forms=self.c.get('/api/forms').json;fid=forms[0]['id'];self.assertEqual(forms[0]['fields'][0]['value'],'18')
  self.assertIn("'=1+1",self.c.get(f'/api/export/{fid}').data.decode('utf-8-sig'))
  self.c.post('/api/logout',headers=headers)
  token=self.login('segundo@example.test');self.assertEqual(self.c.get('/api/forms').json,[]);self.assertEqual(self.c.get(f'/api/export/{fid}').status_code,404)
 def test_guide_only_first_login(self):
  email='guia@example.test';self.login(email);token=self.c.get('/api/me').json['csrf'];self.c.post('/api/logout',headers={'X-CSRF-Token':token})
  r=self.c.post('/api/auth/login',json={'email':email,'password':'test-only-123'});self.assertFalse(r.json['guide'])
 def test_image_and_regions(self):
  token=self.login('foto@example.test');buf=io.BytesIO();Image.new('RGB',(300,200),'white').save(buf,format='PNG');buf.seek(0)
  r=self.c.post('/api/extract',data={'image':(buf,'blank.png'),'regions':json.dumps([{'x':.1,'y':.1,'w':.6,'h':.5,'label':'Nota'}])},headers={'X-CSRF-Token':token})
  self.assertEqual(r.status_code,200);self.assertEqual(r.json['fields'][0]['value'],'');self.assertTrue(r.json['requires_review'])
 def test_invalid_upload(self):
  token=self.login('bad@example.test');r=self.c.post('/api/extract',data={'image':(io.BytesIO(b'not an image'),'bad.png')},headers={'X-CSRF-Token':token});self.assertEqual(r.status_code,422)
if __name__=='__main__':unittest.main()
