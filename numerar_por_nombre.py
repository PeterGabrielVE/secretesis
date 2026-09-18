import os
import glob
from PIL import Image, ImageDraw, ImageFont

# --- Configuración ---
carpeta_entrada = "imagenes_originales"
carpeta_salida = "imagenes_numeradas"

# Crear la carpeta de salida si no existe
if not os.path.exists(carpeta_salida):
    os.makedirs(carpeta_salida)

# Buscar imágenes JPG y PNG
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
            img = Image.open(ruta_imagen)

            # Si el archivo se llama "0", lo copiamos sin modificar
            if nombre_sin_ext == "0":
                ruta_salida = os.path.join(carpeta_salida, nombre_archivo)
                if img.mode in ("RGBA", "P") and ruta_salida.lower().endswith(('.jpg', '.jpeg')):
                    img = img.convert("RGB")
                img.save(ruta_salida)
                print(f"⏩ Omitida numeración para {nombre_archivo} (Copiada intacta)")
                continue

            draw = ImageDraw.Draw(img)
            ancho_img, alto_img = img.size

            # --- Búsqueda robusta de fuente ---
            rutas_fuente = [
                "arial.ttf",
                "C:/Windows/Fonts/arial.ttf",
                "/System/Library/Fonts/Supplemental/Arial.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            ]
            font = None
            for ruta in rutas_fuente:
                try:
                    font = ImageFont.truetype(ruta, 45)
                    break
                except IOError:
                    continue
            if font is None:
                font = ImageFont.load_default()

            texto = nombre_sin_ext
            x_centro = ancho_img / 2

            # ------------------------------------------------------------------
            # PARCHE BLANCO GRANDE: cubre tanto la posición del número nuevo
            # como la posición del número original impreso en el escaneo
            # (el "50" que se veía debajo del parche pequeño).
            #
            # Ajusta estos dos valores si el número viejo queda muy arriba
            # o muy abajo respecto al que estás viendo en tus imágenes:
            #   y_top_parche    -> dónde empieza el parche (más arriba = número más grande)
            #   y_bottom_parche -> dónde termina el parche (más abajo = tapa más)
            # ------------------------------------------------------------------
            y_top_parche = alto_img - 150     # antes: alto_img - 120 (ahora un poco más alto)
            y_bottom_parche = alto_img - 30   # baja lo suficiente para tapar el número viejo

            margen_parche = 60  # más ancho que antes, por si el número viejo no está perfectamente centrado

            draw.rectangle(
                [x_centro - margen_parche, y_top_parche, x_centro + margen_parche, y_bottom_parche],
                fill="white"
            )

            # Calcular posición del texto centrado dentro del parche
            bbox = draw.textbbox((0, 0), texto, font=font)
            ancho_texto = bbox[2] - bbox[0]
            alto_texto = bbox[3] - bbox[1]

            x_texto = x_centro - (ancho_texto / 2)
            y_texto = y_top_parche + ((y_bottom_parche - y_top_parche) - alto_texto) / 2 - bbox[1]

            draw.text((x_texto, y_texto), texto, font=font, fill="black")

            ruta_salida = os.path.join(carpeta_salida, nombre_archivo)

            if img.mode in ("RGBA", "P") and ruta_salida.lower().endswith(('.jpg', '.jpeg')):
                img = img.convert("RGB")

            img.save(ruta_salida)
            print(f"✅ Procesada: {nombre_archivo} -> Numerada como '{texto}' (número original tapado)")

        except Exception as e:
            print(f"❌ Error procesando {ruta_imagen}: {e}")

    print("\n¡Proceso completado! Revisa la carpeta 'imagenes_numeradas'.")