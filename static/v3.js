/* Single-page access, private account folders, and an on-device guest archive. */
let editingForm=null,batchFiles=[],batches=[],batchTimer=null,selectedBatch='',historyRows=[],examples=[];
const safeFields=items=>items.map(f=>Object.fromEntries(Object.entries(f).filter(([k])=>['label','value','confirmed','type','options','status','confidence','source'].includes(k))));
const statusText={reviewed:'Revisado',draft:'Por revisar',queued:'En cola',processing:'Leyendo',error:'Revisar manualmente',cancelled:'Cancelado',uploading:'Subiendo',ready:'Preparado',running:'Procesando',done:'Terminado',partial:'Terminado con incidencias'};
function club(){if(user)return true;$('#auth-title').textContent='Activa tu Club gratuito.';$('#auth-error').textContent='Las carpetas y el historial en cuenta requieren registro. Una imagen no requiere iniciar sesión.';$('#auth-dialog').showModal();return false}
function deviceDB(){return new Promise((resolve,reject)=>{const r=indexedDB.open('tecnoforms-archive',1);r.onupgradeneeded=()=>r.result.createObjectStore('forms',{keyPath:'id'});r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(Error('Este navegador no permite guardar el historial local.'))})}
async function deviceAction(mode,action){const db=await deviceDB();return new Promise((resolve,reject)=>{const tx=db.transaction('forms',mode),store=tx.objectStore('forms');let value;try{const r=action(store);r.onsuccess=()=>{value=r.result};r.onerror=()=>reject(r.error)}catch(e){reject(e)}tx.oncomplete=()=>{db.close();resolve(value)};tx.onerror=()=>{db.close();reject(Error('No se pudo guardar. Puede faltar espacio en este navegador.'))}})}
const deviceAll=()=>deviceAction('readonly',s=>s.getAll());
const deviceGet=id=>deviceAction('readonly',s=>s.get(id));
const devicePut=row=>deviceAction('readwrite',s=>s.put(row));
function downloadBlob(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),10000)}
function responseCSV(items){const safe=v=>{let text=String(v??'');if(/^[=+\-@]/.test(text))text="'"+text;return '"'+text.replaceAll('"','""')+'"'};return '\ufeff'+[['Campo','Respuesta','Revisado'],...items.map(f=>[f.label,f.value,f.confirmed?'Sí':'No'])].map(row=>row.map(safe).join(',')).join('\r\n')}
function resetEditing(){editingForm=null;$('#editing-meta').textContent='';$('#save').textContent=user?'Guardar en mi cuenta ↗':'Guardar en este navegador ↗'}
const originalSetFile=setFile;
setFile=function(f,preset=[]){if(currentJob)return originalSetFile(f,preset);resetEditing();return originalSetFile(f,preset)};
const originalRefreshMe=refreshMe;
refreshMe=async function(){await originalRefreshMe();refreshPlan();return user};
function refreshPlan(){
 $('#folder-gate').hidden=!!user;$('#account span').textContent=user?`${user.name} · Club · Salir`:'Entrar / crear cuenta';
 $('#import-local').hidden=!user;$('#backup-link').hidden=!user;
 if(!editingForm)$('#save').textContent=user?'Guardar en mi cuenta ↗':'Guardar en este navegador ↗';
 $('#history-storage').textContent=user?(window.accountInfo?.storage?.notice||'Historial privado de tu cuenta.'):'Guardado solo en este navegador. No se envía al historial de una cuenta. Descarga copias antes de borrar los datos del navegador.';
 $('#analysis-csv').hidden=!user;
}
const originalPage=page;
page=function(id){if(batchTimer){clearTimeout(batchTimer);batchTimer=null}originalPage(id);if(id==='folders')loadBatches();if(id==='examples')loadExamples()};
$('#join-club').onclick=()=>club();
$('#demo').onclick=()=>page('examples');
$('#download-current').onclick=()=>{if(!fields.length){toast('Primero digitaliza un formulario.');return}downloadBlob(new Blob([responseCSV(fields)],{type:'text/csv;charset=utf-8'}),'tecnoforms-respuestas.csv')};
$('#save').onclick=async()=>{
 if(!fields.length||fields.some(f=>!f.confirmed||!f.label.trim())){toast('Revisa y confirma todos los campos antes de guardar.');return}
 const title=$('#form-title').value.trim()||'Mi formulario';$('#save').disabled=true;
 try{
  if(editingForm?.storage==='device'||!user){
   const previous=editingForm?await deviceGet(editingForm.id):null;
   const id=previous?.id||'local-'+crypto.randomUUID();await devicePut({id,title,fields:safeFields(fields),created:previous?.created||new Date().toISOString(),updated:new Date().toISOString(),status:'reviewed',image:file||previous?.image||null,filename:file?.name||previous?.filename||'',storage:'device'});
   editingForm={id,storage:'device'};toast('Guardado en este navegador. Ya puedes abrirlo en Mis formularios.');
  }else if(editingForm?.storage==='account'){
   await api('/api/forms/'+editingForm.id,{method:'PUT',body:{title,fields:safeFields(fields)}});toast('Formulario revisado y actualizado.');
  }else{
   const fd=new FormData();fd.append('title',title);fd.append('fields',JSON.stringify(safeFields(fields)));if(file)fd.append('image',file);
   const saved=await api('/api/forms',{method:'POST',body:fd});editingForm={id:saved.id,storage:'account'};toast('Formulario e imagen guardados en tu cuenta.');
  }
  page('history');
 }catch(e){toast(e.message)}finally{$('#save').disabled=false}
};

async function openSaved(id,storage){
 if(currentJob){toast('Espera o cancela la lectura actual antes de abrir otro formulario.');return}
 try{
  const row=storage==='device'?await deviceGet(id):await api('/api/forms/'+id);
  if(!row)throw Error('No se encontró este formulario.');
  let blob=row.image||null;
  if(storage==='account'&&row.has_image){const r=await fetch('/api/forms/'+id+'/image');if(r.ok)blob=await r.blob()}
  if(blob)setFile(new File([blob],row.filename||'formulario-guardado.jpg',{type:blob.type||'image/jpeg'}));
  else{file=null;$('#preview-wrap').hidden=true;$('#extract').disabled=true;resetEditing()}
  fields=(row.fields||[]).map(f=>({...f,confirmed:row.status==='reviewed'?true:!!f.confirmed}));editingForm={id:row.id,storage};
  $('#form-title').value=row.title;$('#warnings').textContent=row.status==='reviewed'?'Formulario guardado. Puedes consultar o corregir sus respuestas.':'Borrador digitalizado: compara las respuestas con la imagen y confirma los campos antes de usar el análisis definitivo.';
  $('#editor').hidden=false;$('#empty-results').hidden=true;renderFields();$('#editing-meta').textContent=`${storage==='account'?'En tu cuenta':'En este navegador'} · ${statusText[row.status]||row.status}`;$('#save').textContent='Guardar cambios revisados ↗';page('studio');
 }catch(e){toast(e.message)}
}
async function fetchBatches(){if(!user){batches=[];return[]}batches=await api('/api/batches');return batches}
function updateScopeOptions(){
 for(const id of ['history-scope','analysis-scope']){const el=$('#'+id),selected=el.value;el.innerHTML='<option value="">'+(id==='history-scope'?'Todas las carpetas':'Todos mis formularios')+'</option>'+batches.map(b=>`<option value="${esc(b.id)}">${esc(b.title)}</option>`).join('');if([...el.options].some(o=>o.value===selected))el.value=selected}
}
loadForms=async function(){
 try{forms=user?await api('/api/forms'):(await deviceAll()).sort((a,b)=>b.created.localeCompare(a.created));historyRows=forms;await fetchBatches();updateScopeOptions();refreshPlan();drawHistory();await renderAnalytics()}catch(e){toast(e.message)}
};
function drawHistory(){
 const search=$('#history-search').value.toLocaleLowerCase('es'),scope=$('#history-scope').value,status=$('#history-status').value;
 const rows=historyRows.filter(f=>(!scope||f.batch_id===scope)&&(!status||f.status===status)&&(!search||[f.title,f.filename,...(f.fields||[]).map(r=>r.label+' '+r.value)].join(' ').toLocaleLowerCase('es').includes(search)));
 $('#history-list').innerHTML=rows.length?rows.map(f=>`<article class="card saved-form"><div class="card-heading"><span class="tag ${f.status==='reviewed'?'':'pink'}">${esc(statusText[f.status]||f.status)}</span><span class="hint">${f.storage==='device'?'En este navegador':'En tu cuenta'}</span></div>${f.has_image||f.image?`<div class="saved-image" data-preview="${esc(f.id)}" data-storage="${f.storage==='device'?'device':'account'}"></div>`:''}<h2>${esc(f.title)}</h2><p class="hint">${(f.fields||[]).length} campos · ${new Date(f.created).toLocaleDateString('es-PE')}<br>${esc(f.filename||'')}</p><div class="saved-summary">${(f.fields||[]).slice(0,3).map(r=>`<p><span>${esc(r.label)}</span><b>${esc(r.value)||'Sin respuesta'}</b></p>`).join('')}</div><button class="primary" data-open-form="${esc(f.id)}" data-storage="${f.storage==='device'?'device':'account'}" ${['queued','processing'].includes(f.status)?'disabled':''}>${f.status==='reviewed'?'Ver formulario completo':'Abrir y revisar'} ↗</button>${f.storage==='device'?`<button class="ghost" data-device-csv="${esc(f.id)}">Descargar CSV</button>`:`<a class="csv-link" href="/api/export/${f.id}">Descargar CSV ↗</a>`}</article>`).join(''):'<div class="card"><h2>Tu archivo está por comenzar ✦</h2><p>Guarda una digitalización o procesa una carpeta. Aquí podrás abrir la imagen y todas sus respuestas.</p></div>';
 $$('[data-open-form]').forEach(b=>b.onclick=()=>openSaved(b.dataset.openForm,b.dataset.storage));
 $$('[data-device-csv]').forEach(b=>b.onclick=async()=>{const f=await deviceGet(b.dataset.deviceCsv);downloadBlob(new Blob([responseCSV(f.fields)],{type:'text/csv'}),f.title+'.csv')});
 $$('[data-preview]').forEach(async div=>{try{let url;if(div.dataset.storage==='device'){const f=await deviceGet(div.dataset.preview);url=URL.createObjectURL(f.image)}else url='/api/forms/'+div.dataset.preview+'/image';const img=document.createElement('img');img.alt='Imagen del formulario guardado';img.loading='lazy';img.src=url;div.append(img);if(div.dataset.storage==='device')img.onload=()=>URL.revokeObjectURL(url)}catch{}});
}
$('#history-search').oninput=drawHistory;$('#history-scope').onchange=drawHistory;$('#history-status').onchange=drawHistory;
$('#import-local').onclick=async()=>{
 if(!club())return;const records=await deviceAll();let n=0;$('#import-local').disabled=true;
 try{for(const record of records){if(record.synced?.[user.email])continue;const fd=new FormData();fd.append('title',record.title);fd.append('fields',JSON.stringify(record.fields));if(record.image)fd.append('image',record.image,record.filename||'formulario.jpg');const r=await api('/api/forms',{method:'POST',body:fd});record.synced={...record.synced,[user.email]:r.id};await devicePut(record);n++}toast(`${n} formularios importados a tu cuenta.`);await loadForms()}catch(e){toast(e.message)}finally{$('#import-local').disabled=false}
};

function selectBatchFiles(list){
 const all=[...list],supported=all.filter(f=>['image/jpeg','image/png','image/webp'].includes(f.type));
 if(supported.length>30){toast('Elige una subcarpeta con hasta 30 imágenes por lote.');return}
 if(supported.some(f=>f.size>12*1024*1024)){toast('Cada imagen debe pesar menos de 12 MB.');return}
 batchFiles=supported;$('#batch-title').value=supported[0]?.webkitRelativePath?.split('/')[0]||'Mi carpeta';
 $('#batch-files').innerHTML=supported.map(f=>`<div><span>▧ ${esc(f.webkitRelativePath||f.name)}</span><small>${(f.size/1024).toFixed(0)} KB</small></div>`).join('')||'<p>No se encontraron imágenes compatibles.</p>';
 $('#start-batch').disabled=!supported.length;if(supported.length!==all.length)toast(`${all.length-supported.length} archivos no son JPG, PNG o WEBP y se omitieron.`)
}
$('#choose-folder').onclick=()=>{if(club())$('#folder-input').click()};$('#choose-many').onclick=()=>{if(club())$('#many-input').click()};
$('#folder-input').onchange=e=>selectBatchFiles(e.target.files);$('#many-input').onchange=e=>selectBatchFiles(e.target.files);
$('#start-batch').onclick=async()=>{
 if(!club()||!batchFiles.length)return;$('#start-batch').disabled=true;$('#upload-progress').hidden=false;
 try{const batch=await api('/api/batches',{method:'POST',body:{title:$('#batch-title').value}});let done=0;const failures=[];
 for(const item of batchFiles){$('#upload-progress').textContent=`Guardando imagen ${done+1} de ${batchFiles.length}: ${item.name}`;const fd=new FormData();fd.append('image',item);fd.append('path',item.webkitRelativePath||item.name);try{await api('/api/batches/'+batch.id+'/items',{method:'POST',body:fd});done++}catch(e){failures.push(item.name+': '+e.message)}}
 if(!done)throw Error('No se pudo subir ninguna imagen. '+failures.join(' '));
 await api('/api/batches/'+batch.id+'/start',{method:'POST'});$('#upload-progress').textContent=`${done} imágenes guardadas. La lectura continuará por páginas.${failures.length?' No se subieron '+failures.length+' imágenes.':''}`;batchFiles=[];$('#batch-files').replaceChildren();toast('Carpeta en proceso. Puedes volver al historial cuando quieras.');await loadBatches();await showBatch(batch.id);
 }catch(e){$('#upload-progress').textContent=e.message;toast(e.message)}finally{$('#start-batch').disabled=!batchFiles.length}
};
async function loadBatches(){
 refreshPlan();if(!user){$('#batch-list').innerHTML='<div class="card">Las carpetas se asocian a tu cuenta. Puedes probar imágenes individuales sin registro.</div>';return}
 try{await fetchBatches();updateScopeOptions();$('#batch-list').innerHTML=batches.length?batches.map(b=>`<article class="card"><span class="tag">${esc(statusText[b.status]||b.status)}</span><h2 style="margin-top:15px">${esc(b.title)}</h2><p>${b.completed} de ${b.total} lecturas terminadas · ${b.counts.reviewed||0} revisadas</p><progress max="${Math.max(1,b.total)}" value="${b.completed}"></progress><button class="primary" data-batch="${esc(b.id)}">Abrir carpeta ↗</button></article>`).join(''):'<div class="card">Aún no tienes carpetas. Sube una o prueba uno de los tres lotes de ejemplo.</div>';$$('[data-batch]').forEach(b=>b.onclick=()=>showBatch(b.dataset.batch))}catch(e){toast(e.message)}
}
async function showBatch(id){
 if(batchTimer)clearTimeout(batchTimer);selectedBatch=id;
 try{const b=await api('/api/batches/'+id);$('#batch-detail').innerHTML=`<article class="card"><div class="card-heading"><h2>${esc(b.title)}</h2><span class="tag">${esc(statusText[b.status]||b.status)}</span></div><p class="notice">${esc(b.message||'')}</p><progress max="${Math.max(1,b.total)}" value="${b.completed}"></progress><p>${b.completed}/${b.total} terminadas · ${b.counts.draft||0} por revisar · ${b.counts.reviewed||0} revisadas · ${b.counts.error||0} con incidencias</p><div class="toolbar"><button class="secondary" id="batch-analyze">Analizar esta carpeta ↗</button><a class="ghost" href="/api/export/all.csv?batch_id=${encodeURIComponent(id)}">CSV de todas las respuestas</a><a class="ghost" href="/api/backup.zip?batch_id=${encodeURIComponent(id)}">Respaldo con imágenes</a><button class="ghost" id="batch-action">${b.status==='running'?'Cancelar lectura':'Reanudar / reintentar incidencias'}</button></div><div class="batch-rows">${b.forms.map(f=>`<div><span>▧ ${esc(f.filename||f.title)}<small>${esc(f.error||statusText[f.status]||f.status)}</small></span><button class="secondary" data-review-form="${f.id}" ${['queued','processing'].includes(f.status)?'disabled':''}>${f.status==='reviewed'?'Ver':'Revisar'}</button></div>`).join('')}</div><p class="hint">Los resultados nuevos son borradores. El análisis definitivo utiliza las respuestas que hayas revisado.</p></article>`;
 $('#batch-analyze').onclick=async()=>{await loadForms();$('#analysis-scope').value=id;page('analytics');renderAnalytics()};
 $('#batch-action').onclick=async()=>{try{await api('/api/batches/'+id+(b.status==='running'?'/cancel':'/start'),{method:'POST'});showBatch(id)}catch(e){toast(e.message)}};
 $$('[data-review-form]').forEach(button=>button.onclick=()=>openSaved(button.dataset.reviewForm,'account'));
 await loadBatches();
 if(b.status==='running'&&$('#folders').classList.contains('active'))batchTimer=setTimeout(()=>showBatch(id),3000);
 }catch(e){toast(e.message)}
}

function guestSummary(rows){
 const groups={};for(const row of rows)for(const f of row.fields||[]){const label=f.label.toLocaleLowerCase('es').trim();if(/dni|participante|código|codigo|teléfono|telefono|nombre|apellido|correo|email|dirección|direccion|fecha|cuenta/.test(label))continue;const g=groups[label]??={label:f.label,values:[],present:0,missing:0,options:{}};g.present++;if(!String(f.value).trim()){g.missing++;continue}g.values.push(String(f.value));if(f.type==='checkbox')for(const o of f.options||[])if(o.checked)g.options[o.label]=(g.options[o.label]||0)+1}
 const fields=Object.values(groups).map(g=>{const nums=g.values.map(v=>Number(v.replace(',','.'))),numeric=g.values.length&&g.values.every(v=>/^-?\d+(\.\d+)?$/.test(v.replace(',','.')));const counts=Object.keys(g.options).length?g.options:g.values.reduce((a,v)=>(a[v]=(a[v]||0)+1,a),{});return {label:g.label,present:g.present,missing:g.missing,answered:g.values.length,kind:numeric?'numeric':'categorical',...(numeric?{mean:nums.reduce((a,b)=>a+b,0)/nums.length,minimum:Math.min(...nums),maximum:Math.max(...nums)}:{}),frequencies:Object.entries(counts).sort((a,b)=>b[1]-a[1]).slice(0,12).map(([value,count])=>({value,count,percent:count/g.present*100}))}});
 return {forms_total:rows.length,forms_reviewed:rows.length,forms_pending:0,forms_analyzed:rows.length,participants_identified:0,provisional:false,fields}
}
renderAnalytics=async function(){
 try{const scope=$('#analysis-scope').value,provisional=$('#include-provisional').checked;const summary=user?await api('/api/analysis?provisional='+(provisional?'1':'0')+(scope?'&batch_id='+encodeURIComponent(scope):'')):guestSummary(await deviceAll());
 $('#analysis-warning').hidden=!summary.provisional;$('#analysis-warning').textContent='Análisis provisional: incluye lecturas de IA sin revisar. No lo uses como resultado definitivo hasta confirmar los formularios.';
 $('#provisional-shortcut').hidden=!user||!summary.forms_pending||provisional;$('#analysis-csv').href='/api/export/all.csv'+(scope?'?batch_id='+encodeURIComponent(scope):'');
 $('#stats').innerHTML=[['Formularios guardados',summary.forms_total],['Revisados',summary.forms_reviewed],['Por revisar',summary.forms_pending],['En este análisis',summary.forms_analyzed]].map(([label,n])=>`<article class="card"><span class="eyebrow">${label}</span><div class="metric">${n}</div></article>`).join('');
 const fmt=n=>Number(n).toLocaleString('es-PE',{maximumFractionDigits:2});
 $('#bars').innerHTML=summary.fields.length?summary.fields.map(f=>`<article class="analysis-field"><div class="card-heading"><h2>${esc(f.label)}</h2><span class="tag">${f.answered}/${f.present} RESPUESTAS</span></div>${f.kind==='numeric'?`<div class="numeric-summary"><span>Media <b>${fmt(f.mean)}</b></span><span>Mínimo <b>${fmt(f.minimum)}</b></span><span>Máximo <b>${fmt(f.maximum)}</b></span>${f.sum!==undefined?`<span>Total <b>${fmt(f.sum)}</b></span>`:''}</div>`:''}${f.frequencies.map(r=>`<div class="bar"><div class="bar-label"><span>${esc(r.value)}</span><b>${r.count} · ${fmt(r.percent)}%</b></div><div class="bar-track"><div class="bar-fill" style="width:${Math.max(1,Math.min(100,r.percent))}%"></div></div></div>`).join('')}${f.missing?`<p class="hint">${f.missing} sin respuesta</p>`:''}${f.keywords?.length?`<p class="hint">Palabras frecuentes: ${f.keywords.map(w=>esc(w.word)+' ('+w.count+')').join(' · ')}</p>`:''}</article>`).join(''):'<p>Aún no hay respuestas para este análisis. Revisa formularios guardados o activa explícitamente el análisis provisional de una carpeta.</p>';
 }catch(e){toast(e.message)}
};
$('#analysis-scope').onchange=renderAnalytics;$('#include-provisional').onchange=renderAnalytics;$('#provisional-shortcut').onclick=()=>{$('#include-provisional').checked=true;renderAnalytics()};

async function loadExamples(){
 try{examples=await api('/api/examples');$('#example-gallery').innerHTML=examples.map(e=>`<article class="card example-card"><img src="${esc(e.preview)}" alt="Formulario ficticio: ${esc(e.title)}" loading="lazy"><span class="tag">${e.count} FORMULARIOS</span><h2>${esc(e.title)}</h2><p>${esc(e.description)}</p><button class="primary" data-example-one="${esc(e.id)}">Probar una imagen sin cuenta ↗</button><button class="secondary" data-example-batch="${esc(e.id)}">Procesar carpeta con mi cuenta</button><div class="example-links"><a href="${esc(e.folder_zip)}" download>Descargar carpeta ZIP</a><a href="${esc(e.blank)}" download>Plantilla vacía</a></div></article>`).join('');
 $$('[data-example-one]').forEach(button=>button.onclick=async()=>{try{const e=examples.find(e=>e.id===button.dataset.exampleOne),r=await fetch(e.files[0].url);setFile(new File([await r.blob()],e.files[0].filename,{type:'image/png'}));$('#form-title').value=e.title;page('studio');toast('Imagen cargada. Pulsa Digitalizar; no necesitas iniciar sesión.')}catch(e){toast(e.message)}});
 $$('[data-example-batch]').forEach(button=>button.onclick=async()=>{if(!club())return;button.disabled=true;try{const b=await api('/api/examples/'+button.dataset.exampleBatch+'/batch',{method:'POST'});page('folders');await showBatch(b.id);toast('Carpeta ficticia preparada. Los resultados se guardan para revisar.')}catch(e){toast(e.message)}finally{button.disabled=false}});
 }catch(e){toast(e.message)}
}
const originalLoadMetrics=loadMetrics;
loadMetrics=async function(){await originalLoadMetrics();try{const m=await api('/api/metrics');if(m.forms_training){const r=m.forms_training;$('#model-cards').insertAdjacentHTML('beforeend',`<article class="card"><span class="tag">ENTRENAMIENTO PARA FORMULARIOS</span><h2 style="margin-top:15px">Dígitos en celdas</h2><div class="metric">${(r.accuracy*100).toFixed(2)}%</div><p>Test de ${r.test} dígitos · ${r.train} muestras de entrenamiento · ${r.validation} de validación.</p><p>Modelo seleccionado: ${esc(r.selected)}. Se entrenó y comparó un candidato; se conserva el de mejor validación. Esta cifra no mide texto libre ni formularios completos.</p></article>`)}}catch(e){toast(e.message)}};
(async()=>{await window.initialSession;refreshPlan();resetEditing();await loadExamples()})().catch(e=>toast(e.message));
