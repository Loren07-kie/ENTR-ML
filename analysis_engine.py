"""Aggregate reviewed or explicitly provisional responses without mixing fields/units."""
import re,unicodedata,statistics,collections
IDENTIFIERS=re.compile(r'\b(dni|id|identificador|participante|persona|codigo|telefono|correo|email|nombre|apellido|direccion|fecha|cuenta)\b')
STOP={'el','la','los','las','de','del','y','en','con','un','una','por','para','que','me','mi','a','al','es','lo','se','si','no'}
def key(text):return ' '.join(''.join(c for c in unicodedata.normalize('NFD',str(text).lower()) if unicodedata.category(c)!='Mn').split())
def summarize(forms,provisional=False):
 groups={};total=0;reviewed=0;people=set()
 for form in forms:
  if form['status']=='reviewed':reviewed+=1
  if form['status'] in ('queued','processing','error','cancelled'):continue
  if not provisional and form['status']!='reviewed':continue
  total+=1
  for field in form['fields']:
   label=key(field.get('label',''));value=str(field.get('value','')).strip()
   if re.fullmatch(r'(participante|id participante|codigo de persona|identificador)',label) and value:people.add(value)
   if not label or IDENTIFIERS.search(label):continue
   group=groups.setdefault(label,{'label':field['label'],'present':0,'missing':0,'values':[],'options':collections.Counter(),'multiselect':False})
   group['present']+=1
   if not value:group['missing']+=1;continue
   group['values'].append(value)
   if field.get('type')=='checkbox':
    group['multiselect']=True
    for option in field.get('options',[]):
     if option.get('checked'):group['options'][str(option['label']).strip()]+=1
 outputs=[]
 for label,g in groups.items():
  values=g.pop('values');counts=collections.Counter(values);numbers=[]
  for value in values:
   normalized=value.replace(',','.')
   if re.fullmatch(r'-?\d+(?:\.\d+)?',normalized):numbers.append(float(normalized))
  numeric=len(numbers)==len(values) and bool(values)
  out={k:v for k,v in g.items() if k!='options'};out.update(answered=len(values),kind='numeric' if numeric else 'checkbox' if g['multiselect'] else 'categorical')
  if numeric:
   out.update(mean=round(statistics.mean(numbers),3),median=round(statistics.median(numbers),3),minimum=min(numbers),maximum=max(numbers))
   if re.search(r'\b(importe|monto|pago|cantidad|total|ingreso|gasto)\b',label):out['sum']=round(sum(numbers),3)
  frequency=g['options'] if g['multiselect'] else counts
  out['frequencies']=[{'value':v,'count':n,'percent':round(n/max(1,g['present'])*100,1)} for v,n in frequency.most_common(12)]
  if not numeric and not g['multiselect'] and any(len(v)>50 for v in values):
   words=collections.Counter(w for v in values for w in re.findall(r'[a-záéíóúñ]{3,}',v.lower()) if key(w) not in STOP)
   out['keywords']=[{'word':w,'count':n} for w,n in words.most_common(10)]
  outputs.append(out)
 return {'forms_total':len(forms),'forms_reviewed':reviewed,'forms_pending':sum(f['status'] in ('draft','queued','processing') for f in forms),'forms_failed':sum(f['status']=='error' for f in forms),'forms_analyzed':total,'participants_identified':len(people),'provisional':bool(provisional),'fields':outputs}
