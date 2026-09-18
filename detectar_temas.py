import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

import pytesseract
from PIL import Image

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

# --- Configuración ---
# "...Comunion1" es la guía 2 y "...Comunion2" es la guía 1 (según la portada
# de cada cuaderno: "ENCUENTRO CON JESÚS EN LOS SACRAMENTOS - 1" / "- 2").
carpetas = {
    1: r"C:\Users\Laptop\Documents\1CatequesisPrimeraComunion\II ETAPA\2CatequesisPrimeraComunion2",
    2: r"C:\Users\Laptop\Documents\1CatequesisPrimeraComunion\II ETAPA\2CatequesisPrimeraComunion1",
}
ruta_indice = r"C:\Users\Laptop\Documents\1CatequesisPrimeraComunion\II ETAPA\Indice- Primera Comunión Etapa II.docx"

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Franja donde está el título "N. Título del tema"
FRACCION_SUPERIOR_INICIO = 0.0
FRACCION_SUPERIOR_FIN = 0.13

# Un título de tema: número (1-2 dígitos) + punto/coma + espacio + letra
# (esto descarta falsos positivos como "ACTIVIDAD 3.")
PATRON_TITULO = re.compile(r"(?<!\d)(\d{1,2})\s*[.,]\s*[A-Za-zÁÉÍÓÚáéíóúÑñ]")

# El OCR a veces confunde el "1" inicial con "|" o "I" pegado al número
# (ej. "|0." -> "10."). Solo se corrige si no hay espacio de por medio,
# para no confundir viñetas/adornos sueltos ("| 2." no es "12.").
CORRECCION_PIPE = re.compile(r"(?<![A-Za-z0-9])[|Il](?=\d+\s*[.,])")

# Manual: correcciones confirmadas por inspección directa de la página
# (claves ya ajustadas a la asignación de guía correcta)
CORRECCIONES_MANUALES = {
    (2, "7"): 1,
    (1, "11"): 5,
}


def detectar_tema(ruta_imagen):
    img = Image.open(ruta_imagen).convert("L")
    ancho, alto = img.size
    franja = img.crop(
        (0, int(alto * FRACCION_SUPERIOR_INICIO), ancho, int(alto * FRACCION_SUPERIOR_FIN))
    )
    franja = franja.resize((franja.width * 2, franja.height * 2))

    texto = pytesseract.image_to_string(franja, config="--psm 6")
    texto = texto.strip()

    texto_corregido = CORRECCION_PIPE.sub("1", texto)

    lineas_validas = [
        linea for linea in texto_corregido.splitlines()
        if "actividad" not in linea.lower()
    ]
    texto_filtrado = "\n".join(lineas_validas)

    coincidencia = PATRON_TITULO.search(texto_filtrado)
    if coincidencia:
        return int(coincidencia.group(1)), texto
    return None, texto


def listar_archivos_numericos(carpeta):
    """Devuelve [(numero_pagina, nombre_archivo), ...] ordenado, y aparte
    los archivos cuyo nombre no es puramente numérico."""
    numericos = []
    no_numericos = []
    for nombre in os.listdir(carpeta):
        if not nombre.lower().endswith(".png"):
            continue
        base = os.path.splitext(nombre)[0]
        if base.isdigit():
            numericos.append((int(base), nombre))
        else:
            no_numericos.append(nombre)
    numericos.sort(key=lambda par: par[0])
    return numericos, no_numericos


def subsecuencia_creciente_mas_larga(candidatos):
    """candidatos: lista de (numero_pagina, tema_detectado, nombre_archivo)
    ordenada por numero_pagina. Devuelve la subsecuencia donde tema_detectado
    es estrictamente creciente y más larga (descarta falsos positivos/dups)."""
    n = len(candidatos)
    if n == 0:
        return []

    longitudes = [1] * n
    anteriores = [-1] * n

    for i in range(n):
        for j in range(i):
            if candidatos[j][1] < candidatos[i][1] and longitudes[j] + 1 > longitudes[i]:
                longitudes[i] = longitudes[j] + 1
                anteriores[i] = j

    fin = max(range(n), key=lambda i: longitudes[i])
    secuencia = []
    while fin != -1:
        secuencia.append(candidatos[fin])
        fin = anteriores[fin]
    secuencia.reverse()
    return secuencia


def leer_temas_requeridos(ruta_docx):
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    patron = re.compile(r"Tema\s*#\s*(\d+)\s*-\s*gu[ií]a\s*(\d+)", re.IGNORECASE)
    with zipfile.ZipFile(ruta_docx) as z:
        xml_bytes = z.read("word/document.xml")
    root = ET.fromstring(xml_bytes)
    body = root.find(f"{ns}body")

    requeridos = {1: set(), 2: set()}
    for parrafo in body.findall(f"{ns}p"):
        texto = "".join(t.text or "" for t in parrafo.iter(f"{ns}t"))
        m = patron.search(texto)
        if m:
            requeridos[int(m.group(2))].add(int(m.group(1)))
    return requeridos


def main():
    requeridos = leer_temas_requeridos(ruta_indice)
    mapa_completo = {}  # {numero_guia: {tema: (pagina_inicio, pagina_fin, archivo_inicio)}}

    for numero_guia, carpeta in carpetas.items():
        print(f"\n{'=' * 60}")
        print(f"Guía #{numero_guia}: {carpeta}")
        print(f"{'=' * 60}")

        numericos, no_numericos = listar_archivos_numericos(carpeta)

        if no_numericos:
            print(f"  ⚠️  Archivos sin numerar (no se pueden ubicar automáticamente): {no_numericos}")

        candidatos = []
        for numero_pagina, nombre in numericos:
            ruta = os.path.join(carpeta, nombre)
            tema, texto = detectar_tema(ruta)
            correccion = CORRECCIONES_MANUALES.get((numero_guia, str(numero_pagina)))
            if correccion is not None:
                tema = correccion
            if tema is not None:
                candidatos.append((numero_pagina, tema, nombre))

        secuencia = subsecuencia_creciente_mas_larga(candidatos)
        descartados = [c for c in candidatos if c not in secuencia]

        if descartados:
            print("  Candidatos descartados por romper el orden creciente (probables falsos positivos):")
            for numero_pagina, tema, nombre in descartados:
                print(f"    - {nombre} detectado como Tema #{tema}")

        # páginas máximas para poder cerrar el rango del último tema
        ultima_pagina = numericos[-1][0] if numericos else 0

        mapa = {}
        for idx, (numero_pagina, tema, nombre) in enumerate(secuencia):
            fin = secuencia[idx + 1][0] - 1 if idx + 1 < len(secuencia) else ultima_pagina
            mapa[tema] = (numero_pagina, fin, nombre)

        mapa_completo[numero_guia] = mapa

        print(f"\n--- Rangos detectados guía #{numero_guia} ---")
        for tema in sorted(mapa):
            inicio, fin, _ = mapa[tema]
            marca_requerido = " (usado en índice)" if tema in requeridos[numero_guia] else ""
            print(f"  Tema #{tema:>2}: páginas {inicio}-{fin}{marca_requerido}")

        faltan = requeridos[numero_guia] - set(mapa)
        if faltan:
            print(f"\n  ❌ Temas requeridos por el índice que NO se detectaron: {sorted(faltan)}")

    print(f"\n{'=' * 60}")
    print("MAPEO_RANGOS = " + repr(mapa_completo))


if __name__ == "__main__":
    main()
