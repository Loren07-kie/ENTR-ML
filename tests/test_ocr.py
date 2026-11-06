import unittest
from unittest.mock import patch
from pathlib import Path
import numpy as np
from PIL import Image
from vision import extract,prepare_page,ocr_rows

class OCRRegression(unittest.TestCase):
 def test_timeout_is_not_reported_as_missing_installation(self):
  with patch('vision.ocr_status',return_value={'available':True,'languages':['spa']}),patch('pytesseract.image_to_data',side_effect=RuntimeError('Tesseract process timeout')):
   r=extract(np.full((200,300,3),255,dtype=np.uint8))
  message=' '.join(r['warnings'])
  self.assertIn('superó el tiempo',message);self.assertNotIn('no está instalado',message)
 def test_missing_engine_has_specific_message(self):
  with patch('vision.ocr_status',return_value={'available':False,'languages':[]}):
   r=extract(np.full((200,300,3),255,dtype=np.uint8))
  self.assertIn('no está instalado',' '.join(r['warnings']))
 def test_large_photo_is_bounded(self):
  page,prepared=prepare_page(np.full((2400,1800,3),240,dtype=np.uint8))
  self.assertLessEqual(max(page.shape),1300);self.assertEqual(page.shape[:2],prepared.shape)
 def test_numeric_ocr_field_uses_handwriting_model(self):
  root=Path(__file__).resolve().parents[1]
  page=np.array(Image.open(root/'static/formulario-ejemplo.png').convert('RGB'))
  d={'text':['Edad:','ya','4'],'conf':[95,30,70],'block_num':[1,1,1],'par_num':[1,1,1],'line_num':[1,1,1],'left':[80,350,440],'top':[235,225,225],'width':[120,84,84],'height':[28,84,84]}
  rows=ocr_rows(d,page)
  self.assertEqual(rows[0]['label'],'Edad');self.assertEqual(rows[0]['value'],'24');self.assertEqual(rows[0]['source'],'OCR + modelo de dígitos');self.assertTrue(rows[0]['review'])
if __name__=='__main__':unittest.main()
