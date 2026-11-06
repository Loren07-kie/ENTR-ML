import unittest,io,time,uuid
from unittest.mock import patch
from PIL import Image
from app import app

class JobTests(unittest.TestCase):
 def test_async_reading_and_private_result(self):
  c=app.test_client();email='job-'+uuid.uuid4().hex+'@example.test'
  self.assertEqual(c.post('/api/auth/register',json={'name':'Job test','email':email,'password':'test-only-123'}).status_code,200)
  csrf=c.get('/api/me').json['csrf'];headers={'X-CSRF-Token':csrf}
  buffer=io.BytesIO();Image.new('RGB',(300,200),'white').save(buffer,'PNG');buffer.seek(0)
  expected={'fields':[{'label':'Nombre','value':'','confirmed':False,'status':'empty'}],'warnings':[],'requires_review':True}
  with patch('app.handwriting_available',return_value=True),patch('form_reader.read_form',return_value=expected):
   r=c.post('/api/jobs',data={'image':(buffer,'blank.png')},headers=headers)
   self.assertEqual(r.status_code,202);path='/api/jobs/'+r.json['id']
   for _ in range(100):
    result=c.get(path)
    if result.json['state'] in ('done','error'):break
    time.sleep(.01)
   self.assertEqual(result.json['state'],'done');self.assertEqual(result.json['result'],expected)
  other=app.test_client();other.post('/api/auth/register',json={'name':'Other','email':'other-'+email,'password':'test-only-123'})
  self.assertEqual(other.get(path).status_code,404)
 def test_snippet_never_persists_in_saved_form(self):
  c=app.test_client();c.post('/api/auth/register',json={'name':'Photo test','email':uuid.uuid4().hex+'@example.test','password':'test-only-123'});csrf=c.get('/api/me').json['csrf']
  fields=[{'label':'Nota','value':'18','confirmed':True,'snippet':'data:image/jpeg;base64,PRIVATE','bbox':[0,0,1,1]}]
  self.assertEqual(c.post('/api/forms',json={'fields':fields},headers={'X-CSRF-Token':csrf}).status_code,200)
  saved=c.get('/api/forms').json[0]['fields'][0];self.assertNotIn('snippet',saved);self.assertNotIn('bbox',saved)
if __name__=='__main__':unittest.main()
