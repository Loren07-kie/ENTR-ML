# TecnoForms · Del papel al dato

Proyecto del caso práctico **Clasificación de Dígitos Manuscritos**. Aplicación Python/Flask con registro, sesiones, OCR de formularios, selección de regiones manuscritas, revisión humana, exportación CSV y análisis por campo. Diseño original SVG/CSS, tipografía graffiti, efectos de escaneo, paneles flotantes y stickers.

## Ejecutar

Python 3.12 recomendado. En una terminal dentro del proyecto:

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Abre http://localhost:8000. Los modelos ya están incluidos. Para reentrenar, ejecuta `python tools/train.py` y `python tools/train_photo.py` (este último descarga MNIST). Para OCR automático instala **Tesseract OCR** con los idiomas español e inglés y agrégalo al PATH. El contenedor Docker ya lo incluye. Sin Tesseract siguen funcionando las regiones numéricas y la edición manual.

```sh
docker build -t tecnoforms .
docker run --rm -p 8000:8000 -e SECRET_KEY=una-clave-larga-aleatoria tecnoforms
python -m unittest discover -s tests -v
```

## Usar

1. Sube una imagen y pulsa Digitalizar, sin iniciar sesión. Revisa, corrige y confirma los campos.
2. Guarda sin cuenta en este navegador o descarga CSV. En «Mis formularios» puedes abrir la imagen y todas las respuestas guardadas.
3. Crea una cuenta gratuita para guardar en PostgreSQL y subir carpetas de hasta 30 imágenes. El Club no tiene cobros.
4. En «3 ejemplos» prueba educación, pagos o encuestas: seis formularios ficticios por carpeta, plantillas vacías y ZIP descargables.
5. Revisa cada borrador de una carpeta; el análisis definitivo incluye solo los revisados. Puedes activar un análisis provisional explícito, filtrar por carpeta y exportar CSV o respaldo ZIP.

La base gratuita de Render vence el **6 de diciembre de 2026**. Descarga copias antes de esa fecha. DATABASE_URL se enlaza mediante render.yaml sin publicar credenciales. Sin esa variable se usa SQLite para desarrollo.

Consulta [la guía V3](docs/Version_3.md) para entrenamiento real, resultados, límites y uso de carpetas. Las fotos se guardan al guardar en cuenta o subir una carpeta; los recortes temporales de reconocimiento no se guardan. Una lectura automática requiere confirmación humana.

## Evidencias

- `notebooks/TecnoForms_Proyecto.ipynb`: cuaderno ejecutado, EDA, comparación KNN/SVM/MLP, validación, matriz, predicciones, arquitectura, regresión y K-Means sintéticos, diagrama y preguntas guía.
- `docs/Informe_TecnoForms.md`: propuesta fundamentada y matriz de cumplimiento.
- `models/metrics.json` y `models/photo_metrics.json`: resultados medidos, no inventados.
- `docs/`: gráficos, diagrama y protocolo de validación con fotos nuevas.
- `tools/train.py`, `tools/train_photo.py`, `vision.py`: entrenamiento y visión reproducibles.

## Alcance y límites

El modelo de fotos usa HOG + SVM, entrenado con 15 000 dígitos MNIST; el benchmark usa 1 797 dígitos UCI (8×8), separado 80/20 y CV estratificada en entrenamiento. Sus métricas **no miden extracción de formularios completos**. No se ha validado todavía un conjunto independiente de fotos reales de TecnoForms. Texto manuscrito libre, dígitos unidos, sombras, trazos partidos, perspectiva y formularios complejos pueden fallar. No se promete OCR universal. Se requiere revisión humana antes de usar datos.

MLP: 64 → 64 ReLU → 32 ReLU → 10 softmax; Adam y entropía cruzada. La CNN no es obligatoria si se emplea MLP; se propone como ampliación después de reunir fotos etiquetadas.

## Despliegue

Render: servicio Docker, rama main, plan gratuito. El Dockerfile instala Tesseract y verifica los modelos ya entrenados; los experimentos se reproducen con tools/train*.py. `PORT` es provisto por Render. Configurar `SECRET_KEY` como variable secreta persistente. `DATA_DIR` define la ruta de SQLite (por defecto `instance/`). Un worker con 4 threads.

**Persistencia:** la versión publicada usa PostgreSQL mediante DATABASE_URL y conserva formularios, imágenes y cuentas frente a reinicios del servicio. La base gratuita vence el 6 de diciembre de 2026; exportar respaldos antes. Sin DATABASE_URL, SQLite local es temporal en Render. No contiene recuperación de contraseña, verificación de correo ni límites distribuidos de autenticación; es un prototipo académico, no una solución lista para datos sensibles.

## Fuentes

- UCI / sklearn: https://scikit-learn.org/stable/modules/generated/sklearn.datasets.load_digits.html
- MLP: https://scikit-learn.org/stable/modules/neural_networks_supervised.html
- MNIST: https://www.tensorflow.org/datasets/catalog/mnist ; distribución pública https://storage.googleapis.com/tensorflow/tf-keras-datasets/mnist.npz
- Tesseract: https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html
- OpenCV: https://docs.opencv.org/4.x/d7/d4d/tutorial_py_thresholding.html
- Material de referencia del usuario: semanas 9 a 12 y PIAD-427_TRABAJOFINAL.pdf. No se redistribuyen esos archivos ni datos privados en GitHub.

## Licencia

Código y gráficos originales del proyecto bajo MIT. Los conjuntos UCI y MNIST conservan sus propios términos y atribuciones. Fuentes tipográficas Google Fonts con respaldo local del navegador; si no hay internet se usan fuentes del sistema.

## Corrección de lectura de fotos grandes (6 de noviembre)

El OCR limita la imagen a 1300 píxeles en su lado mayor, corrige inclinaciones leves de las líneas y normaliza iluminación. Tesseract usa un hilo y un límite de 75 segundos. Los errores de tiempo, instalación y procesamiento se distinguen. `/health` verifica también los idiomas del OCR. Los campos numéricos sencillos detectados automáticamente se envían al modelo de dígitos. Ver `docs/Correccion_OCR.md`.

## Lector versión 2: gratuito y sin API

Ejecutar `python tools/download_htr.py` para activar TrOCR ONNX. La aplicación procesa por trabajos con progreso, separa campos, muestra recortes y alternativas, admite casillas editables y permite marcar regiones de texto o dígitos. El modelo se ejecuta en Render; no se envían fotos a proveedores de IA externos. Sus pesos públicos se descargan durante el build. Ver `docs/Mejoras_Lector_V2.md` y `models/htr/README.md`. Los nombres propios y la escritura cursiva en español todavía pueden fallar: siempre revisar. Los recortes solo se usan para revisar y no se guardan en SQLite.


## Verificación en Render

La versión 3 se probó con 18 formularios ficticios (tres carpetas). Se recuperaron imágenes y respuestas desde PostgreSQL, se verificaron 84/84 campos controlados y se descargaron CSV y ZIP con imágenes. Ver [evidencia pública](docs/Verificacion_V3.json). No es una medición de precisión para formularios desconocidos o cursiva libre. Los modelos de formularios se guardan en partes con SHA-256 y se cargan con model_io.py.
