"""Download publicly licensed quantized TrOCR; user photos are never sent here."""
from pathlib import Path
import urllib.request
ROOT=Path(__file__).resolve().parents[1]/'models/htr'
FILES=['config.json','preprocessor_config.json','tokenizer.json','tokenizer_config.json','special_tokens_map.json','onnx/encoder_model_quantized.onnx','onnx/decoder_model_quantized.onnx']
def download():
 ROOT.mkdir(parents=True,exist_ok=True)
 for name in FILES:
  target=ROOT/Path(name).name
  if not target.exists():
   temporary=target.with_suffix(target.suffix+'.partial')
   urllib.request.urlretrieve('https://huggingface.co/Xenova/trocr-small-handwritten/resolve/02bea33ca09a70e2e2d91140a7e6e1a729606a5b/'+name,temporary)
   temporary.replace(target)
  print(target.name,flush=True)
if __name__=='__main__':download()
