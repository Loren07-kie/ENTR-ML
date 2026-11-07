"""One inference entry point shared by single-page and folder processing."""
from vision import extract
from handwriting import available
def read_document(rgb,regions=None,mode='structured',progress=None):
 if regions:
  from form_reader import read_regions
  return read_regions(rgb,regions,progress)
 if mode=='classic':return extract(rgb)
 from form_templates import read_template
 result=read_template(rgb)
 if result is not None:return result
 if available():
  from form_reader import read_form
  return read_form(rgb,progress)
 result=extract(rgb);result['warnings'].insert(0,'El lector manuscrito no está disponible; se usó el lector básico.')
 return result
