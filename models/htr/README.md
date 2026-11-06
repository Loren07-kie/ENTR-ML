# Motor manuscrito gratuito

Modelo original: Microsoft TrOCR small handwritten, preentrenado y ajustado con IAM (líneas manuscritas en inglés). Exportación ONNX cuantizada: Xenova/trocr-small-handwritten, licencia MIT según su ficha pública.

Fuentes: https://huggingface.co/microsoft/trocr-small-handwritten ; https://huggingface.co/Xenova/trocr-small-handwritten

Los pesos y el tokenizador se descargan con `python tools/download_htr.py`, fijando la revisión `02bea33ca09a70e2e2d91140a7e6e1a729606a5b`. No se envían fotografías a Hugging Face ni a otros proveedores: la inferencia se ejecuta dentro del servidor de la aplicación. No hay clave API ni suscripción al motor.

El modelo trabaja por línea, no por formulario completo. Se combina con OpenCV para campos/casillas, Tesseract en español y HOG/SVM para números. No está especializado en español: puede cambiar acentos, nombres o palabras cursivas; todas las propuestas requieren revisión. Los scores no están calibrados como probabilidad de exactitud.

Los archivos originales de configuración, tokenización y ONNX son artefactos públicos de terceros; los datos privados de formularios no se incluyen aquí.
