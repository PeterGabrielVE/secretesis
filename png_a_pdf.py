# ==========================================
# CONVERTIR PNGs A PDF CON MARGENES PEQUEÑOS
# ==========================================

import sys
import subprocess

# ==========================================
# INSTALAR PILLOW SI NO ESTÁ INSTALADO
# ==========================================

try:
    from PIL import Image
except ImportError:
    print("Pillow no está instalado.")
    print("Instalando Pillow...")
    print()

    subprocess.check_call([
        sys.executable,
        "-m",
        "pip",
        "install",
        "Pillow"
    ])

    print()
    print("✓ Pillow instalado correctamente.")
    print()

    from PIL import Image

from pathlib import Path


# ==========================================
# CONFIGURACIÓN
# ==========================================

CARPETA_ENTRADA = "imagenes_numeradas"
ARCHIVO_SALIDA = "resultado.pdf"

# Margen pequeño alrededor de cada imagen.
# Se expresa como porcentaje del tamaño de la página.
MARGEN = 0.03


# ==========================================
# FUNCIONES
# ==========================================

def obtener_numero(nombre):
    """
    Obtiene el número del nombre del archivo.

    Ejemplos:
        000.png -> 0
        001.png -> 1
        025.png -> 25
    """
    try:
        return int(Path(nombre).stem)
    except ValueError:
        return None


def preparar_imagen(imagen):
    """
    Convierte la imagen a RGB y conserva correctamente
    la transparencia colocando un fondo blanco.
    """

    if imagen.mode in ("RGBA", "LA"):
        imagen_rgba = imagen.convert("RGBA")

        fondo = Image.new(
            "RGBA",
            imagen_rgba.size,
            "white"
        )

        fondo.alpha_composite(imagen_rgba)

        return fondo.convert("RGB")

    if imagen.mode != "RGB":
        return imagen.convert("RGB")

    return imagen


def agregar_margen(imagen, margen):
    """
    Agrega un margen blanco pequeño alrededor de la imagen.
    """

    ancho, alto = imagen.size

    margen_x = max(1, int(ancho * margen))
    margen_y = max(1, int(alto * margen))

    lienzo = Image.new(
        "RGB",
        (
            ancho + margen_x * 2,
            alto + margen_y * 2
        ),
        "white"
    )

    lienzo.paste(
        imagen,
        (margen_x, margen_y)
    )

    return lienzo


# ==========================================
# CARPETAS
# ==========================================

entrada = Path(CARPETA_ENTRADA)
salida = Path(ARCHIVO_SALIDA)


if not entrada.exists():
    print("❌ ERROR")
    print()
    print(f"No existe la carpeta:")
    print(f"  {entrada.resolve()}")
    print()
    print("Crea la carpeta y coloca allí los archivos PNG.")
    sys.exit(1)


# ==========================================
# BUSCAR ARCHIVOS PNG
# ==========================================

archivos = [
    archivo
    for archivo in entrada.iterdir()
    if archivo.is_file()
    and archivo.suffix.lower() == ".png"
]


# ==========================================
# ORDENAR NUMÉRICAMENTE
# ==========================================
#
# Esto permite ordenar:
#
# 000.png
# 001.png
# 002.png
# ...
# 010.png
# 011.png
#
# correctamente.

archivos.sort(
    key=lambda archivo: (
        obtener_numero(archivo.name)
        if obtener_numero(archivo.name) is not None
        else float("inf")
    )
)


if not archivos:
    print("⚠️ No se encontraron archivos PNG.")
    print()
    print(f"Carpeta revisada: {entrada.resolve()}")
    sys.exit(1)


# ==========================================
# INFORMACIÓN
# ==========================================

print("=" * 50)
print("CONVERSIÓN DE PNG A PDF")
print("=" * 50)
print()

print(f"Carpeta de entrada:")
print(f"  {entrada.resolve()}")
print()

print(f"Archivo de salida:")
print(f"  {salida.resolve()}")
print()

print(f"Archivos encontrados: {len(archivos)}")
print(f"Margen: {MARGEN * 100:.1f}%")
print()

print("Orden de las páginas:")
for posicion, archivo in enumerate(archivos, start=1):
    numero = obtener_numero(archivo.name)

    if numero is not None:
        print(f"  Página {posicion}: {numero:03d}.png")
    else:
        print(f"  Página {posicion}: {archivo.name}")

print()


# ==========================================
# CARGAR IMÁGENES
# ==========================================

imagenes = []
errores = 0

for posicion, archivo in enumerate(archivos, start=1):

    try:
        print(
            f"[{posicion}/{len(archivos)}] "
            f"Procesando {archivo.name}..."
        )

        imagen = Image.open(archivo)

        # Cargar completamente la imagen antes de cerrarla.
        imagen.load()

        # Convertir a RGB y manejar transparencia.
        imagen = preparar_imagen(imagen)

        # Agregar margen blanco.
        imagen = agregar_margen(
            imagen,
            MARGEN
        )

        imagenes.append(imagen)

    except Exception as error:
        errores += 1

        print(
            f"  ❌ Error procesando {archivo.name}:"
        )
        print(
            f"     {error}"
        )


# ==========================================
# VALIDAR IMÁGENES
# ==========================================

if not imagenes:
    print()
    print("❌ No se pudo procesar ninguna imagen.")
    sys.exit(1)


# ==========================================
# CREAR PDF
# ==========================================

print()
print("Creando PDF...")

primera_imagen = imagenes[0]
imagenes_restantes = imagenes[1:]


primera_imagen.save(
    salida,
    "PDF",
    resolution=100.0,
    save_all=True,
    append_images=imagenes_restantes
)


# ==========================================
# RESULTADO
# ==========================================

print()
print("=" * 50)
print("✓ PDF CREADO CORRECTAMENTE")
print("=" * 50)
print()

print(f"Archivo:")
print(f"  {salida.resolve()}")

print()
print(f"Páginas creadas: {len(imagenes)}")

if errores > 0:
    print(f"⚠️ Imágenes con error: {errores}")
else:
    print("Errores: 0")

print()
print("El PDF incluye:")
print("  ✓ 000.png")
print("  ✓ 001.png")
print("  ✓ 002.png")
print("  ✓ ...")
print("  ✓ Margen blanco pequeño")
print("  ✓ Imágenes centradas")
print("  ✓ Fondo blanco para transparencias")
print()
