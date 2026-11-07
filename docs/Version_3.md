# TecnoForms: imágenes, carpetas e historial

Una imagen se digitaliza sin crear cuenta. Revisa las respuestas y guárdalas en este navegador, o descarga el CSV. El historial local depende de los datos del navegador y no se sincroniza automáticamente.

El Club es una cuenta gratuita, sin cobros. Permite subir una carpeta de hasta 30 imágenes JPG, PNG o WEBP (12 MB por imagen), consultar cada digitalización junto a su foto, corregirla y descargar respaldos. Los archivos se suben por separado para mostrar el progreso. Los resultados automáticos quedan como borradores; no entran en el análisis definitivo hasta confirmar todos sus campos. Se puede activar expresamente el análisis provisional.

## Tres usos demostrables

| Carpeta | Formularios ficticios | Análisis esperado tras revisar |
| --- | --- | --- |
| Educación | 6 estudiantes, edad, nota, asistencia y turno | Nota media 15,83; asistencia media 86,67%; 3 por turno |
| Pagos | 6 operaciones, monto, cantidad y canal | Total 1200; importe medio 200; cantidades por campo |
| Encuesta | 6 respuestas, edad, satisfacción, recomendación y comentario | Satisfacción media 3,83; recomiendan 4 de 6 (66,67%) |

Abre «3 ejemplos» para cargar una imagen, procesar las seis de una carpeta con cuenta o descargar su ZIP. Las plantillas vacías permiten rellenar nuevas hojas, siempre con revisión de resultados. Los nombres, cantidades y respuestas son ficticios. Los números de muestra usan trazos reales del test oficial de MNIST, separados del entrenamiento.

El QR visible identifica solamente la plantilla. El servidor detecta y alinea su geometría, recorta cada celda y clasifica sus píxeles. No contiene respuestas. La clave de respuestas pública se usa exclusivamente para evaluar. Las plantillas controladas no equivalen a fotos arbitrarias: estas usan el lector general TrOCR/Tesseract y pueden necesitar selección manual y corrección de cursiva española.

## Entrenamiento y evaluación reales

Se entrenó un candidato SVM con 7000 muestras (1000 aumentadas), ajuste de C con 3 pliegues y validación de 1500 muestras. El modelo base obtuvo mejor F1 de validación (0,98952 frente a 0,98874), por lo que se conservó. En 2000 dígitos de test logró 98,6% de acierto y F1 macro 0,98601. Se incluyen ambos modelos y métricas reproducibles.

La prueba de las 18 imágenes controladas, tras compresión JPEG, obtuvo 84/84 campos exactos con normalización de mayúsculas, tildes y puntuación. Los comentarios impresos se evaluaron localmente mediante Tesseract.js; Render utiliza Tesseract nativo. No se atribuye ese 100% al reconocimiento de texto manuscrito libre ni a formularios desconocidos.

## Persistencia y análisis

DATABASE_URL activa PostgreSQL; sin ella se usa SQLite local. Render recibe la URL mediante una referencia de Blueprint, sin guardarla en Git. La base gratuita de esta demostración vence el 6 de diciembre de 2026: descargar respaldos y migrar antes. Se guardan las fotos únicamente al guardar explícitamente en cuenta o subir carpetas. La importación del historial local a una cuenta también es explícita.

Los análisis agrupan por nombre de campo normalizado, excluyen identificadores y separan valores numéricos, categorías y casillas. No suman edades, notas o satisfacciones como si fueran importes. Cada porcentaje muestra su denominador; los comentarios muestran frecuencias de palabras, sin diagnóstico ni inferencia emocional.

## Reproducir

`python tools/create_examples.py` genera los 18 formularios y los ZIP. `python tools/train_forms.py` entrena, compara y guarda los modelos. `python tools/evaluate_examples.py` evalúa las plantillas; requiere Tesseract para los comentarios impresos. `python -m unittest discover -s tests -v` verifica los 20 casos de backend. El test DOM opcional está en tests/ui_smoke.cjs.
