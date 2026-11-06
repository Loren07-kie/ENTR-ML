import unittest
from unittest.mock import patch
import cv2,numpy as np
from form_reader import read_form,checkbox_boxes,handwriting_lines

class StructuredReaderTests(unittest.TestCase):
 def test_blank_form_does_not_invent_a_response(self):
  page=np.full((600,450,3),255,np.uint8)
  data={'text':['Nombre:'],'conf':[98],'block_num':[1],'par_num':[1],'line_num':[1],'left':[25],'top':[100],'width':[90],'height':[20]}
  with patch('form_reader.read_printed',return_value=data),patch('form_reader.read_line') as htr:
   result=read_form(page)
  self.assertEqual(len(result['fields']),1);self.assertEqual(result['fields'][0]['value'],'');self.assertEqual(result['summary']['blank'],1);htr.assert_not_called()
 def test_multiple_labels_on_one_row_have_separate_regions(self):
  from form_reader import labels_from_data,value_box
  d={'text':['DNI:','Fecha','de','Nacimiento:'],'conf':[95]*4,'block_num':[1]*4,'par_num':[1]*4,'line_num':[1]*4,'left':[20,230,300,330],'top':[100]*4,'width':[45,60,20,120],'height':[20]*4}
  labels=labels_from_data(d);self.assertEqual(len(labels),2)
  a=value_box(labels[0],labels,[],600,400);b=value_box(labels[1],labels,[],600,400)
  self.assertLess(a[2],230);self.assertGreater(b[0],440)
 def test_checked_and_unchecked_square_are_detected(self):
  page=np.full((600,450,3),255,np.uint8)
  cv2.rectangle(page,(80,150),(106,176),(35,35,35),2);cv2.rectangle(page,(80,210),(106,236),(35,35,35),2)
  cv2.line(page,(85,155),(102,172),(30,40,180),3);cv2.line(page,(102,155),(85,172),(30,40,180),3)
  boxes=checkbox_boxes(page)
  self.assertTrue(any(abs(x-80)<5 and abs(y-150)<5 for x,y,w,h in boxes));self.assertTrue(any(abs(x-80)<5 and abs(y-210)<5 for x,y,w,h in boxes))
 def test_ink_regions_do_not_merge_two_paragraph_lines(self):
  mask=np.zeros((100,300),np.uint8)
  cv2.putText(mask,'Hola',(5,30),cv2.FONT_HERSHEY_SIMPLEX,.7,255,2);cv2.putText(mask,'mundo',(5,80),cv2.FONT_HERSHEY_SIMPLEX,.7,255,2)
  self.assertEqual(len(handwriting_lines(mask)),2)
if __name__=='__main__':unittest.main()
