import os
import re
import shutil
import sys
import zipfile
import xml.etree.ElementTree as ET

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

# --- Configuración ---
# Los nombres de carpeta NO corresponden a su número de guía real:
# "...Comunion1" es la guía 2 y "...Comunion2" es la guía 1 (según la portada
# de cada cuaderno: "ENCUENTRO CON JESÚS EN LOS SACRAMENTOS - 1" / "- 2").
carpeta_cuaderno1 = r"C:\Users\Laptop\Documents\1CatequesisPrimeraComunion\II ETAPA\2CatequesisPrimeraComunion2"
carpeta_cuaderno2 = r"C:\Users\Laptop\Documents\1CatequesisPrimeraComunion\II ETAPA\2CatequesisPrimeraComunion1"
ruta_indice = r"C:\Users\Laptop\Documents\1CatequesisPrimeraComunion\II ETAPA\Indice- Primera Comunión Etapa II.docx"
carpeta_salida = r"C:\Users\Laptop\Documents\1CatequesisPrimeraComunion\II ETAPA\CuadernoUnido"

WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
PATRON_TEMA = re.compile(r"Tema\s*#\s*(\d+)\s*-\s*gu[ií]a\s*(\d+)", re.IGNORECASE)

carpetas_por_guia = {1: carpeta_cuaderno1, 2: carpeta_cuaderno2}

# Rango de páginas físicas (portada + todas sus actividades) que ocupa cada
# Tema dentro de la carpeta de su propia guía. Verificado manualmente
# revisando el contenido de las páginas, porque el nombre del PNG NO
# corresponde ni al número de Tema ni a un desplazamiento fijo.
# Clave: (numero_guia, numero_tema) -> (pagina_inicio, pagina_fin) o None
# si esa página todavía no ha sido escaneada/numerada.
RANGOS_MANUALES = {
    (1, 1): (1, 3),
    (1, 7): (16, 18),
    (1, 8): (19, 20),
    (1, 9): (21, 23),
    (1, 10): (24, 25),
    (1, 11): (26, 28),
    (1, 14): (35, 38),
    (1, 16): (43, 46),
    (1, 17): (47, 49),
    (1, 19): (52, 55),
    (1, 20): (56, 59),
    (1, 21): (60, 63),

    (2, 5): (18, 20),
    (2, 6): (21, 23),
    (2, 7): (24, 27),
    (2, 8): (28, 30),
    (2, 9): (31, 32),
    (2, 13): (42, 44),
    (2, 14): (45, 47),
    (2, 15): (48, 50),
    (2, 16): (51, 53),
    (2, 17): (54, 56),
    (2, 18): (57, 58),
    (2, 19): (59, 60),
    (2, 21): (64, 65),
    (2, 23): (69, 71),
}


def leer_indice(ruta_docx):
    """Lee el .docx del índice y devuelve una lista de (numero_tema, numero_guia)
    en el orden en que deben quedar en el cuaderno unido."""
    with zipfile.ZipFile(ruta_docx) as z:
        xml_bytes = z.read("word/document.xml")

    root = ET.fromstring(xml_bytes)
    body = root.find(f"{WORD_NS}body")

    entradas = []
    for parrafo in body.findall(f"{WORD_NS}p"):
        texto = "".join(t.text or "" for t in parrafo.iter(f"{WORD_NS}t"))
        coincidencia = PATRON_TEMA.search(texto)
        if coincidencia:
            numero_tema = int(coincidencia.group(1))
            numero_guia = int(coincidencia.group(2))
            entradas.append((numero_tema, numero_guia))

    return entradas


def main():
    entradas = leer_indice(ruta_indice)

    if not entradas:
        print(f"No se encontraron entradas 'Tema # N - guía X' en '{ruta_indice}'.")
        return

    if not os.path.exists(carpeta_salida):
        os.makedirs(carpeta_salida)

    contador_salida = 0
    faltantes = []

    for posicion, (numero_tema, numero_guia) in enumerate(entradas, start=1):
        carpeta_origen = carpetas_por_guia.get(numero_guia)
        rango = RANGOS_MANUALES.get((numero_guia, numero_tema))

        if carpeta_origen is None or rango is None:
            print(f"❌ Posición {posicion:02d}: Tema #{numero_tema} - guía #{numero_guia} "
                  f"no está disponible todavía. Se omite.")
            faltantes.append((posicion, numero_tema, numero_guia))
            continue

        pagina_inicio, pagina_fin = rango
        paginas_copiadas = []

        for numero_pagina in range(pagina_inicio, pagina_fin + 1):
            ruta_origen = os.path.join(carpeta_origen, f"{numero_pagina}.png")
            if not os.path.exists(ruta_origen):
                print(f"  ⚠️  Falta la página '{numero_pagina}.png' dentro del Tema #{numero_tema} "
                      f"- guía #{numero_guia}.")
                continue

            contador_salida += 1
            nombre_salida = f"{contador_salida:03d}.png"
            shutil.copy2(ruta_origen, os.path.join(carpeta_salida, nombre_salida))
            paginas_copiadas.append(nombre_salida)

        print(f"✅ Posición {posicion:02d}: Tema #{numero_tema} - guía #{numero_guia} "
              f"(páginas {pagina_inicio}-{pagina_fin}) -> {paginas_copiadas}")

    print(f"\n¡Proceso completado! {contador_salida} páginas copiadas a '{carpeta_salida}'.")

    if faltantes:
        print("\nTemas que no se pudieron incluir (todavía no disponibles):")
        for posicion, numero_tema, numero_guia in faltantes:
            print(f"  - Posición {posicion}: Tema #{numero_tema} - guía #{numero_guia}")


if __name__ == "__main__":
    main()
