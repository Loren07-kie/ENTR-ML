"""Free local handwriting recognition using quantized TrOCR ONNX (MIT model)."""
import json, threading
from pathlib import Path
import numpy as np
from PIL import Image

ROOT=Path(__file__).parent/'models/htr'
LOCK=threading.Lock()
_reader=None

class HandwritingReader:
 def __init__(self):
  import onnxruntime as ort
  from tokenizers import Tokenizer
  opts=ort.SessionOptions();opts.intra_op_num_threads=1;opts.inter_op_num_threads=1
  opts.enable_cpu_mem_arena=False
  self.encoder=ort.InferenceSession(str(ROOT/'encoder_model_quantized.onnx'),opts,providers=['CPUExecutionProvider'])
  self.decoder=ort.InferenceSession(str(ROOT/'decoder_model_quantized.onnx'),opts,providers=['CPUExecutionProvider'])
  self.tokenizer=Tokenizer.from_file(str(ROOT/'tokenizer.json'))
 def read(self,image,max_tokens=64):
  if image.size==0:return '',0.
  im=Image.fromarray(image).convert('RGB').resize((384,384),Image.Resampling.BICUBIC)
  pixels=(np.asarray(im,dtype=np.float32)/127.5-1).transpose(2,0,1)[None]
  encoded=self.encoder.run(['last_hidden_state'],{'pixel_values':pixels})[0]
  ids=[2];scores=[]
  for _ in range(max_tokens):
   logits=self.decoder.run(['logits'],{'input_ids':np.array([ids],dtype=np.int64),'encoder_hidden_states':encoded})[0][0,-1]
   token=int(np.argmax(logits));shift=logits-logits.max();score=float(1/np.exp(shift).sum())
   if token==2:break
   ids.append(token);scores.append(score)
   if len(ids)>15 and (len(set(ids[-10:]))<=2 or ids[-6:-3]==ids[-3:]):break
  text=self.tokenizer.decode(ids[1:],skip_special_tokens=True).strip()
  return text,float(np.mean(scores)) if scores else 0.

def available():return all((ROOT/name).exists() for name in ['encoder_model_quantized.onnx','decoder_model_quantized.onnx','tokenizer.json'])
def read_line(image,max_tokens=64):
 global _reader
 with LOCK:
  if _reader is None:_reader=HandwritingReader()
  return _reader.read(image,max_tokens)
