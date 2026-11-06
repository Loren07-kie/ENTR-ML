# TecnoForms: mejoras del lector, versión 2

Fecha: 6 de noviembre de 2026.

## Implementación

- Motor gratuito TrOCR ONNX cuantizado para líneas manuscritas, ejecutado en el mismo servidor.
- Localización de rótulos en una pasada separada de la lectura de respuestas.
- Separación de campos que comparten fila; reconocimiento de párrafos por regiones y líneas.
- Corrección de perspectiva cuando se detectan las cuatro esquinas de una hoja y enderezado de inclinaciones leves.
- Separación de tinta azul, extracción de tinta negra dentro de regiones y supresión de reglas impresas.
- Detección visual de casillas y opciones editables; una opción no marcada no se convierte automáticamente en respuesta.
- Lecturas alternativas de TrOCR y OCR español cuando discrepan. Validación de formato de correo, DNI y fechas sin inventar dígitos para corregirlos.
- Marcado explícito de respuestas vacías e inciertas. Propuestas de muy baja confianza no se rellenan automáticamente.
- Recorte de la respuesta al lado de cada campo para revisión visual. Los recortes no se guardan al persistir formularios.
- Lectura por trabajos asíncronos con progreso, cola limitada, cancelación y resultados accesibles únicamente al usuario propietario.
- Selección manual de regiones de texto o de dígitos para releer respuestas que no se hayan localizado bien.

## Evaluación y límites

Se usaron las cuatro imágenes de prueba proporcionadas por la usuaria para detectar fallos del lector anterior y ajustar la integración. Son ejemplos de desarrollo, no un test independiente ni prueba de exactitud comercial. Las imágenes y las salidas con datos personales se mantienen fuera del repositorio y del ZIP.

Las pruebas de integración y regresión verifican campos vacíos, separación de rótulos, casillas, división de líneas, aislamiento de trabajos y exclusión de recortes al guardar, además de autenticación, CSV y clasificación numérica existentes.

El modelo de TrOCR fue entrenado con líneas IAM en inglés. El español cursivo, los nombres propios, los símbolos y las decoraciones aún pueden producir errores. No se garantiza transcripción perfecta ni se reemplaza la revisión humana. Las métricas UCI/MNIST del cuaderno siguen midiendo dígitos aislados y no deben usarse como exactitud del lector de formularios.

## Uso

Subir una foto y pulsar Digitalizar. El progreso indica la etapa actual. Revisar los campos con advertencia, abrir el recorte y comparar las alternativas. Las opciones de casillas se pueden corregir. Si falta un campo, marcar su región y elegir Texto manuscrito o Dígitos. Confirmar las respuestas antes de guardar o analizar.

Instalación: `pip install -r requirements.txt` y `python tools/download_htr.py`. Docker instala también Tesseract y sus idiomas. Para reproducir pruebas locales con el helper opcional `tools/evaluate_forms.py`, preparar Tesseract.js en `.tools/ocr/`; no se necesita ese helper en Render.
