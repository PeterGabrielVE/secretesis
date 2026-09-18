import os
import re
import shutil
import sys

import pytesseract
from PIL import Image, ImageDraw, ImageFont
from pytesseract import Output

import unir_cuadernos as uc

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

# --- Configuración ---
carpeta_entrada = uc.carpeta_salida  # CuadernoUnido
carpeta_salida = os.path.join(os.path.dirname(carpeta_entrada), "CuadernoUnido_Renumerado")

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

FRACCION_SUPERIOR = 0.13
PATRON_NUMERO = re.compile(r"[|Il]?\d{1,2}[.,]?")


def calcular_portadas():
    """Reconstruye, a partir del índice y los mismos rangos usados por
    unir_cuadernos.py, qué archivo de salida es la portada de cada Tema
    y qué número de posición (1-26) le corresponde en el cuaderno unido."""
    entradas = uc.leer_indice(uc.ruta_indice)
    contador = 0
    portadas = {}

    for posicion, (numero_tema, numero_guia) in enumerate(entradas, start=1):
        rango = uc.RANGOS_MANUALES.get((numero_guia, numero_tema))
        if rango is None:
            continue

        pagina_inicio, pagina_fin = rango
        carpeta_origen = uc.carpetas_por_guia[numero_guia]
        es_portada = True

        for numero_pagina in range(pagina_inicio, pagina_fin + 1):
            ruta_origen = os.path.join(carpeta_origen, f"{numero_pagina}.png")
            if not os.path.exists(ruta_origen):
                continue
            contador += 1
            nombre_salida = f"{contador:03d}.png"
            if es_portada:
                portadas[nombre_salida] = posicion
                es_portada = False

    return portadas


def encontrar_caja_numero(ruta_imagen):
    """Ubica, dentro de la franja superior de la página, la caja del número
    de Tema impreso en el título (ej. el "7" de "7. El pueblo se aleja...")."""
    img = Image.open(ruta_imagen).convert("L")
    ancho, alto = img.size
    franja = img.crop((0, 0, ancho, int(alto * FRACCION_SUPERIOR)))
    franja = franja.resize((franja.width * 2, franja.height * 2))

    datos = pytesseract.image_to_data(franja, config="--psm 6", output_type=Output.DICT)
    n = len(datos["text"])

    for i in range(n):
        texto = datos["text"][i].strip()
        if texto and PATRON_NUMERO.fullmatch(texto):
            x, y, w, h = datos["left"][i], datos["top"][i], datos["width"][i], datos["height"][i]
            # Si el punto/coma quedó como token aparte justo después, se incluye
            if i + 1 < n and datos["text"][i + 1].strip() in {".", ","}:
                w = datos["left"][i + 1] + datos["width"][i + 1] - x
            # Deshacer el escalado x2 para volver a coordenadas de la franja original
            return x / 2, y / 2, w / 2, h / 2

    return None


def cargar_fuente(tamano):
    rutas_fuente = [
        "arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for ruta in rutas_fuente:
        try:
            return ImageFont.truetype(ruta, tamano)
        except IOError:
            continue
    return ImageFont.load_default()


def renumerar(ruta_entrada, ruta_salida, nuevo_numero):
    caja = encontrar_caja_numero(ruta_entrada)
    img = Image.open(ruta_entrada).convert("RGB")

    if caja is None:
        img.save(ruta_salida)
        return False

    x, y, w, h = caja
    margen = h * 0.3
    x0, y0 = max(0, x - margen), max(0, y - margen)
    x1, y1 = x + w + margen, y + h + margen

    draw = ImageDraw.Draw(img)
    draw.rectangle([x0, y0, x1, y1], fill="white")

    fuente = cargar_fuente(int(h * 1.15))
    draw.text((x0, y0 - margen * 0.3), f"{nuevo_numero}.", font=fuente, fill="black")

    img.save(ruta_salida)
    return True


def main():
    if not os.path.exists(carpeta_salida):
        os.makedirs(carpeta_salida)

    portadas = calcular_portadas()
    archivos = sorted(f for f in os.listdir(carpeta_entrada) if f.lower().endswith(".png"))

    for nombre in archivos:
        ruta_entrada = os.path.join(carpeta_entrada, nombre)
        ruta_salida = os.path.join(carpeta_salida, nombre)

        if nombre in portadas:
            nuevo_numero = portadas[nombre]
            ok = renumerar(ruta_entrada, ruta_salida, nuevo_numero)
            estado = "✅ renumerada" if ok else "⚠️  no se detectó el número; copiada sin cambios"
            print(f"{nombre}: {estado} -> Tema #{nuevo_numero}")
        else:
            shutil.copy2(ruta_entrada, ruta_salida)

    print(f"\n¡Listo! Carpeta generada: '{carpeta_salida}'.")


if __name__ == "__main__":
    main()
