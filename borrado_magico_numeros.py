import os
import re
import glob
from PIL import Image, ImageDraw, ImageFont
import pytesseract

# --- Configuración ---
carpeta_entrada = "imagenes_originales"
carpeta_salida = "imagenes_numeradas"

# Si estás en Windows y Tesseract no se detecta automáticamente, descomenta
# la siguiente línea y ajusta la ruta a donde lo instalaste:
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Porcentaje inferior de la imagen donde se buscan números impresos
# (0.25 = el 25% inferior de la imagen). Ajusta si el número original
# está más arriba o más abajo en tus escaneos.
FRACCION_INFERIOR = 0.25

# Margen de seguridad (en píxeles) que se agrega alrededor de cada
# número detectado antes de pintarlo de blanco, para taparlo por completo.
MARGEN_BORRADO = 12

if not os.path.exists(carpeta_salida):
    os.makedirs(carpeta_salida)

extensiones = ('*.png', '*.jpg', '*.jpeg')
imagenes = []
for ext in extensiones:
    imagenes.extend(glob.glob(os.path.join(carpeta_entrada, ext)))

if not imagenes:
    print(f"No se encontraron imágenes en la carpeta '{carpeta_entrada}'.")
else:
    for ruta_imagen in imagenes:
        nombre_archivo = os.path.basename(ruta_imagen)
        nombre_sin_ext = os.path.splitext(nombre_archivo)[0]

        try:
            img = Image.open(ruta_imagen).convert("RGB")
            draw = ImageDraw.Draw(img)
            ancho_img, alto_img = img.size

            # Si el archivo se llama "0", lo copiamos sin modificar
            if nombre_sin_ext == "0":
                ruta_salida = os.path.join(carpeta_salida, nombre_archivo)
                img.save(ruta_salida)
                print(f"⏩ Omitida para {nombre_archivo} (Copiada intacta)")
                continue

            # --- Recortar solo la franja inferior para acelerar el OCR ---
            y_inicio_franja = int(alto_img * (1 - FRACCION_INFERIOR))
            franja = img.crop((0, y_inicio_franja, ancho_img, alto_img))

            # --- OCR: obtener cada palabra detectada con su posición ---
            datos = pytesseract.image_to_data(
                franja, output_type=pytesseract.Output.DICT,
                config="--psm 6 -c tessedit_char_whitelist=0123456789"
            )

            borrados = 0
            n_detecciones = len(datos["text"])
            for i in range(n_detecciones):
                texto_detectado = datos["text"][i].strip()
                confianza = int(datos["conf"][i]) if datos["conf"][i] != "-1" else -1

                # Solo nos interesan detecciones que sean números puros
                if not texto_detectado or not re.fullmatch(r"\d+", texto_detectado):
                    continue
                if confianza < 40:  # descarta detecciones poco confiables
                    continue

                # Si el número detectado coincide con el nombre del archivo, se deja tal cual
                if texto_detectado == nombre_sin_ext:
                    continue

                # --- No coincide: lo borramos ---
                x = datos["left"][i]
                y = datos["top"][i]
                w = datos["width"][i]
                h = datos["height"][i]

                # Convertir coordenadas de la franja recortada a coordenadas de la imagen completa
                x0 = max(0, x - MARGEN_BORRADO)
                y0 = max(0, y_inicio_franja + y - MARGEN_BORRADO)
                x1 = min(ancho_img, x + w + MARGEN_BORRADO)
                y1 = min(alto_img, y_inicio_franja + y + h + MARGEN_BORRADO)

                draw.rectangle([x0, y0, x1, y1], fill="white")
                borrados += 1
                print(f"   🧽 Borrado '{texto_detectado}' (no coincide con '{nombre_sin_ext}') en {nombre_archivo}")

            ruta_salida = os.path.join(carpeta_salida, nombre_archivo)
            img.save(ruta_salida)

            if borrados > 0:
                print(f"✅ {nombre_archivo}: {borrados} número(s) incorrecto(s) borrado(s).")
            else:
                print(f"➖ {nombre_archivo}: sin números incorrectos detectados.")

        except Exception as e:
            print(f"❌ Error procesando {ruta_imagen}: {e}")

    print("\n¡Proceso completado! Revisa la carpeta 'imagenes_numeradas'.")