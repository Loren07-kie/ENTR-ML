"""Load reproducible model artifacts stored in small, checksummed parts."""
from pathlib import Path
import io,json,hashlib,joblib

def split_model(path,size=700_000):
 path=Path(path);data=path.read_bytes();folder=path.with_suffix('.parts');folder.mkdir(exist_ok=True)
 names=[]
 for index,start in enumerate(range(0,len(data),size)):
  name=f'part-{index:03d}.bin';(folder/name).write_bytes(data[start:start+size]);names.append(name)
 (folder/'manifest.json').write_text(json.dumps({'parts':names,'sha256':hashlib.sha256(data).hexdigest()},indent=2))

def load_model(path):
 path=Path(path);folder=path.with_suffix('.parts')
 if folder.exists():
  manifest=json.loads((folder/'manifest.json').read_text());data=b''.join((folder/name).read_bytes() for name in manifest['parts'])
  if hashlib.sha256(data).hexdigest()!=manifest['sha256']:raise ValueError('Model artifact checksum mismatch')
  return joblib.load(io.BytesIO(data))
 return joblib.load(path)
