// Optional local evaluation adapter; production uses native Tesseract.
const {createWorker}=require('../.tools/ocr/node_modules/tesseract.js');
(async()=>{const path=require('node:path');const worker=await createWorker('spa+eng',1,{cachePath:path.resolve(__dirname,'../.tools/ocr')});await worker.setParameters({tessedit_pageseg_mode:process.argv[3]||'11'});const r=await worker.recognize(process.argv[2],{},{tsv:true});process.stdout.write(r.data.tsv);await worker.terminate()})().catch(e=>{console.error(e.message);process.exit(1)});
