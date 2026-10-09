from pathlib import Path
import cv2


# ==========================================
# CONFIGURACIÓN
# ==========================================

carpeta_entrada = "imagenes_originales"
carpeta_salida = "imagenes_numeradas"

# Distancia desde la parte inferior.
# 0.03 = 3% de la altura de la imagen.
margen_inferior_porcentaje = 0.03

# Color del número en formato BGR
# Negro = (0, 0, 0)
color_numero = (0, 0, 0)

# Grosor del texto
grosor = 3


# ==========================================
# CREAR CARPETAS
# ==========================================

entrada = Path(carpeta_entrada)
salida = Path(carpeta_salida)

salida.mkdir(parents=True, exist_ok=True)


# ==========================================
# OBTENER NÚMERO DEL ARCHIVO
# ==========================================

def obtener_numero(nombre):
    """
    Obtiene el número del nombre del archivo.

    Ejemplos:

    001.png -> 1
    002.png -> 2
    017.png -> 17
    125.png -> 125
    """

    try:
        return int(Path(nombre).stem)
    except ValueError:
        return None


# ==========================================
# AGREGAR NÚMERO
# ==========================================

def agregar_numero(imagen, numero):

    texto = str(numero)

    # --------------------------------------
    # Dimensiones de la imagen
    # --------------------------------------

    alto_imagen, ancho_imagen = imagen.shape[:2]

    # --------------------------------------
    # Fuente OpenCV
    # --------------------------------------

    fuente = cv2.FONT_HERSHEY_SIMPLEX

    # --------------------------------------
    # Tamaño proporcional de la fuente
    # --------------------------------------

    # Una imagen de 1000 px de alto tendrá
    # aproximadamente escala 1.0.
    escala = max(1.0, alto_imagen / 1000)

    # --------------------------------------
    # Obtener dimensiones del texto
    # --------------------------------------

    (ancho_texto, alto_texto), baseline = cv2.getTextSize(
        texto,
        fuente,
        escala,
        grosor
    )

    # --------------------------------------
    # Centrar horizontalmente
    # --------------------------------------

    x = (ancho_imagen - ancho_texto) // 2

    # --------------------------------------
    # Margen inferior proporcional
    # --------------------------------------

    margen_inferior = int(
        alto_imagen * margen_inferior_porcentaje
    )

    # --------------------------------------
    # Posición vertical
    # --------------------------------------

    # OpenCV utiliza la coordenada Y como
    # la línea BASE del texto.
    y = alto_imagen - margen_inferior - baseline

    # --------------------------------------
    # Dibujar número
    # --------------------------------------

    cv2.putText(
        imagen,
        texto,
        (x, y),
        fuente,
        escala,
        color_numero,
        grosor,
        cv2.LINE_AA
    )

    return imagen


# ==========================================
# EXTENSIONES PERMITIDAS
# ==========================================

extensiones = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp"
}


# ==========================================
# VERIFICAR CARPETA DE ENTRADA
# ==========================================

if not entrada.exists():

    print("❌ ERROR")
    print()
    print(f"No existe la carpeta:")
    print(f"   {entrada.resolve()}")
    print()
    print("Crea la carpeta 'imagenes_originales' y coloca")
    print("las imágenes dentro de ella.")

    exit()


# ==========================================
# OBTENER ARCHIVOS
# ==========================================

archivos = [
    archivo
    for archivo in entrada.iterdir()
    if archivo.is_file()
    and archivo.suffix.lower() in extensiones
]


# ==========================================
# ORDENAR POR NÚMERO
# ==========================================

archivos.sort(
    key=lambda archivo: (
        obtener_numero(archivo.name)
        if obtener_numero(archivo.name) is not None
        else float("inf")
    )
)


# ==========================================
# PROCESAMIENTO
# ==========================================

if not archivos:

    print("⚠️ No se encontraron imágenes.")
    print()
    print(f"Revisa la carpeta:")
    print(f"   {entrada.resolve()}")

else:

    print()
    print("==========================================")
    print("     NUMERANDO IMÁGENES")
    print("==========================================")
    print()
    print(f"Entrada : {entrada.resolve()}")
    print(f"Salida  : {salida.resolve()}")
    print(f"Imágenes: {len(archivos)}")
    print()

    procesadas = 0
    errores = 0

    for archivo in archivos:

        numero = obtener_numero(archivo.name)

        # ----------------------------------
        # Ignorar archivos sin número
        # ----------------------------------

        if numero is None:

            print(
                f"⚠️ Ignorado: {archivo.name} "
                f"(el nombre no contiene un número)"
            )

            continue

        print(
            f"Procesando: {archivo.name} "
            f"→ número {numero}"
        )

        try:

            # ----------------------------------
            # Leer imagen
            # ----------------------------------

            imagen = cv2.imread(
                str(archivo),
                cv2.IMREAD_UNCHANGED
            )

            # ----------------------------------
            # Validar imagen
            # ----------------------------------

            if imagen is None:

                print(
                    f"   ❌ No se pudo abrir la imagen"
                )

                errores += 1
                continue

            # ----------------------------------
            # Manejar imágenes grayscale
            # ----------------------------------

            if len(imagen.shape) == 2:

                imagen = cv2.cvtColor(
                    imagen,
                    cv2.COLOR_GRAY2BGR
                )

            # ----------------------------------
            # Manejar PNG con transparencia
            # ----------------------------------

            elif (
                len(imagen.shape) == 3
                and imagen.shape[2] == 4
            ):

                # OpenCV carga PNG como BGRA.
                #
                # Conservamos la imagen RGBA/BGRA
                # para no perder transparencia.

                agregar_numero(
                    imagen,
                    numero
                )

            # ----------------------------------
            # Imagen normal BGR
            # ----------------------------------

            else:

                agregar_numero(
                    imagen,
                    numero
                )

            # ----------------------------------
            # Agregar número si tiene alpha
            # ----------------------------------

            if (
                len(imagen.shape) == 3
                and imagen.shape[2] == 4
            ):

                # El texto ya fue dibujado sobre
                # los canales BGR.
                pass

            # ----------------------------------
            # Ruta de salida
            # ----------------------------------

            destino = salida / archivo.name

            # ----------------------------------
            # Guardar
            # ----------------------------------

            guardado = cv2.imwrite(
                str(destino),
                imagen
            )

            if not guardado:

                print(
                    f"   ❌ No se pudo guardar: "
                    f"{destino}"
                )

                errores += 1
                continue

            procesadas += 1

            print(
                f"   ✓ Guardado: {destino}"
            )

        except Exception as error:

            errores += 1

            print(
                f"   ❌ Error procesando "
                f"{archivo.name}:"
            )

            print(
                f"      {error}"
            )


# ==========================================
# RESUMEN
# ==========================================

print()
print("==========================================")
print("           PROCESO TERMINADO")
print("==========================================")
print()
print(f"✓ Procesadas : {procesadas}")
print(f"❌ Errores   : {errores}")
print()
print(f"Entrada:")
print(f"  {entrada.resolve()}")
print()
print(f"Salida:")
print(f"  {salida.resolve()}")
print()
print("==========================================")
