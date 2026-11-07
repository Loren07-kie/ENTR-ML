"""Package public project files and optional offline HTR weights; never private data."""
from pathlib import Path
import subprocess,zipfile
ROOT=Path(__file__).resolve().parents[1]
files=[ROOT/p for p in subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0') if p]
files.extend(p for p in (ROOT/'models/htr').glob('*') if p.suffix in {'.onnx','.json'})
out=ROOT/'TecnoForms_Proyecto_Completo.zip'
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
 for p in sorted(set(files)):
  relative=p.relative_to(ROOT)
  if p.is_file() and not any(part in {'instance','.git','.tools','__pycache__'} for part in relative.parts):archive.write(p,str(relative))
print(out)
print(f'{out.stat().st_size/1024**2:.1f} MB')
