# Corrección del lector de fotos grandes

Fecha: 6 de noviembre de 2026.

## Problema observado

Una foto de formulario mostraba «OCR no disponible» y no generaba campos. El código anterior atrapaba cualquier excepción y emitía ese mismo mensaje, ocultando la diferencia entre motor ausente, tiempo agotado y error de procesamiento.

Se verificó que el motor de Render sí ejecutaba OCR con el ejemplo ficticio: produjo líneas en 17,7 segundos. Por tanto, no se confirmó una instalación ausente. La causa específica del fallo de la foto de la usuaria no quedó registrada en la versión anterior; el límite de 30 segundos para imágenes de hasta 1800×2400 era una causa posible, no demostrada para esa foto.

## Cambios

- Limitar a 1300 píxeles el lado mayor de la imagen enviada al OCR.
- Estimar inclinaciones leves con líneas Hough y enderezar sin guardar la foto.
- Normalizar iluminación en escala de grises.
- Usar OMP_THREAD_LIMIT=1 y hasta 75 segundos para Tesseract.
- Instalar y verificar explícitamente los idiomas español e inglés en Docker.
- Separar mensajes de tiempo agotado, instalación y otros errores; registrar solo el tipo de fallo, sin contenido de fotos.
- Incluir estado del OCR en `/health`.
- Enviar respuestas numéricas sencillas de edad, nota e importe al modelo de dígitos después de localizar el campo con OCR.
- Mostrar segundos transcurridos mientras se procesa.

## Verificación

Ocho pruebas locales pasaron: cuatro pruebas de integración existentes y cuatro nuevas para tiempo agotado, motor ausente, tamaño de foto grande y clasificación de una respuesta numérica localizada con OCR. La prueba del campo Edad corrige una propuesta textual incorrecta y devuelve 24 usando el modelo de manuscritos.

Las pruebas nuevas simulan el resultado del OCR cuando corresponde; no sustituyen una prueba del binario Tesseract en Render. La actualización debe verificarse allí con el ejemplo ficticio, tanto en tamaño original como ampliado e inclinado.

La captura privada de la usuaria no se incorpora al repositorio ni al ZIP. No se afirma que nombres, apellidos y texto manuscrito libre queden reconocidos perfectamente. Cada respuesta sigue requiriendo revisión humana. La corrección de inclinación no equivale a rectificación completa de perspectiva.
