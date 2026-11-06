# TecnoForms · Del papel al dato

Proyecto del caso práctico **Clasificación de Dígitos Manuscritos**. Aplicación Python/Flask con registro, sesiones, OCR de formularios, selección de regiones manuscritas, revisión humana, exportación CSV y análisis por campo. Diseño original SVG/CSS, tipografía graffiti, efectos de escaneo, paneles flotantes y stickers.

## Ejecutar

Python 3.12 recomendado. En una terminal dentro del proyecto:

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python tools/train.py
python tools/train_photo.py
python app.py
```

Abre http://localhost:8000. Para OCR automático instala **Tesseract OCR** con los idiomas español e inglés y agrégalo al PATH. El contenedor Docker ya lo incluye. Sin Tesseract siguen funcionando las regiones numéricas y la edición manual.

```sh
docker build -t tecnoforms .
docker run --rm -p 8000:8000 -e SECRET_KEY=una-clave-larga-aleatoria tecnoforms
python -m unittest discover -s tests -v
```

## Usar

1. Crea una cuenta con correo y contraseña de al menos 8 caracteres. El cuestionario y guía aparecen una sola vez, en el primer ingreso; se conservan por cuenta.
2. Sube PNG/JPG/WEBP de hasta 12 MB y 24 megapíxeles. La foto no se almacena. Rótulos impresos y texto legible se intentan leer con Tesseract.
3. Para respuestas numéricas manuscritas, pulsa **Marcar campos** y dibuja una región por respuesta, sin incluir el rótulo. Nombra cada campo; gira la foto si es necesario. Pulsa Digitalizar.
4. Corrige los valores, añade respuestas de texto manualmente y marca Revisado. Guarda el formulario.
5. Consulta estadísticas agrupadas por nombre de campo y exporta CSV desde Mis formularios. No se agregan campos de identificadores comunes.

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

Render: servicio Docker, rama main, plan gratuito. El Dockerfile instala Tesseract y entrena ambos modelos. `PORT` es provisto por Render. Configurar `SECRET_KEY` como variable secreta persistente. `DATA_DIR` define la ruta de SQLite (por defecto `instance/`). Un worker con 4 threads.

**Persistencia:** SQLite en el plan gratuito es temporal y se pierde en reinicios/despliegues. Para uso permanente, montar un disco en DATA_DIR o migrar a PostgreSQL. La aplicación lo comunica al usuario. Exportar CSV durante las pruebas. No contiene recuperación de contraseña, verificación de correo ni límites distribuidos de autenticación; es un prototipo académico, no una solución lista para datos sensibles.

## Fuentes

- UCI / sklearn: https://scikit-learn.org/stable/modules/generated/sklearn.datasets.load_digits.html
- MLP: https://scikit-learn.org/stable/modules/neural_networks_supervised.html
- MNIST: https://www.tensorflow.org/datasets/catalog/mnist ; distribución pública https://storage.googleapis.com/tensorflow/tf-keras-datasets/mnist.npz
- Tesseract: https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html
- OpenCV: https://docs.opencv.org/4.x/d7/d4d/tutorial_py_thresholding.html
- Material de referencia del usuario: semanas 9 a 12 y PIAD-427_TRABAJOFINAL.pdf. No se redistribuyen esos archivos ni datos privados en GitHub.

## Licencia

Código y gráficos originales del proyecto bajo MIT. Los conjuntos UCI y MNIST conservan sus propios términos y atribuciones. Fuentes tipográficas Google Fonts con respaldo local del navegador; si no hay internet se usan fuentes del sistema.
