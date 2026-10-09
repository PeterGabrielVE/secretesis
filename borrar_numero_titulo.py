#!/usr/bin/env python3
"""
Elimina mediante borrado generativo (inpainting) el número que aparece
antes del punto en el TÍTULO de páginas escaneadas.

Ejemplo:  «19. Los sacramentos, signos de vida»  ->  «Los sacramentos, signos de vida»

Pensado para títulos CENTRADOS, donde el número se desplaza según la
longitud del título; por eso se localiza con OCR y no con una posición fija.

NOVEDADES respecto a la versión anterior:
  - El OCR suele leer el punto como coma ("19,"): ahora se acepta . , o -.
  - Se detecta la zona de la página (ignora el borde oscuro del escaneo).
  - El número se busca como el token más arriba/izquierda de la cabecera.
  - Idioma por defecto 'eng' (leer un número no necesita español -> evita
    el error de spa.traineddata).
  - Al final se listan las páginas que quedaron SIN número (sin tocar).

DETECCIÓN (--deteccion):
  ocr     (por defecto) Localiza el número con OCR. Requiere pytesseract
          y el binario de Tesseract instalado.
  region  Rectángulo fijo en la parte superior (sin OCR).

RECONSTRUCCIÓN (--metodo):
  opencv  (por defecto) OpenCV Inpainting (TELEA). Rápido; ideal aquí.
  lama    Inpainting generativo (pip install simple-lama-inpainting).

Por defecto se borra el número Y el punto. Usa --conservar-punto para
quitar solo el número.

Ejemplos:
    python borrar_numero_titulo.py ./paginas ./salida
    python borrar_numero_titulo.py ./paginas ./salida --desde 19 --guardar-mascara
    python borrar_numero_titulo.py ./paginas ./salida --deteccion region
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import cv2
import numpy as np

import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


EXTENSIONES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}

# Número de 1 a 4 dígitos con . , o - final opcional (el OCR confunde . con ,)
PATRON_NUMERO = re.compile(r"^(\d{1,4})[.,\-]?$")


# --------------------------------------------------------------------------- #
#  Utilidades
# --------------------------------------------------------------------------- #
def clave_natural(path: Path) -> list:
    partes = re.split(r"(\d+)", path.name)
    return [int(p) if p.isdigit() else p.lower() for p in partes]


def obtener_archivos(carpeta: Path, recursivo: bool) -> list[Path]:
    patron = "**/*" if recursivo else "*"
    archivos = [
        p for p in carpeta.glob(patron)
        if p.is_file()
        and p.suffix.lower() in EXTENSIONES
        and "_MASK" not in p.stem  # nunca procesar las máscaras de depuración
    ]
    return sorted(archivos, key=clave_natural)


def detectar_zona_pagina(imagen: np.ndarray, pagina_completa: bool) -> tuple[int, int, int, int]:
    """
    Devuelve (x, y, w, h) del rectángulo de la página blanca, para ignorar el
    borde oscuro del escaneo. Si no se detecta algo razonable, usa la imagen
    entera.
    """
    h_img, w_img = imagen.shape[:2]
    if pagina_completa:
        return 0, 0, w_img, h_img
    gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    _, binaria = cv2.threshold(gris, 200, 255, cv2.THRESH_BINARY)
    contornos, _ = cv2.findContours(binaria, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contornos:
        return 0, 0, w_img, h_img
    x, y, w, h = cv2.boundingRect(max(contornos, key=cv2.contourArea))
    if w * h < 0.40 * w_img * h_img:  # detección poco fiable -> imagen entera
        return 0, 0, w_img, h_img
    return x, y, w, h


# --------------------------------------------------------------------------- #
#  Máscaras
# --------------------------------------------------------------------------- #
def crear_mascara_ocr(
    imagen: np.ndarray,
    idioma: str,
    zona_superior_rel: float,
    conf_min: float,
    conservar_punto: bool,
    margen: int,
    pagina_completa: bool,
) -> np.ndarray | None:
    """
    Localiza el número inicial del título y devuelve una máscara que lo cubre.
    Devuelve None si no se encuentra número.
    """
    try:
        import pytesseract
    except ImportError as exc:
        raise RuntimeError(
            "pytesseract no está instalado. Ejecuta:  pip install pytesseract\n"
            "y ten instalado el binario de Tesseract, o usa --deteccion region."
        ) from exc

    h_img, w_img = imagen.shape[:2]
    px, py, pw, ph = detectar_zona_pagina(imagen, pagina_completa)

    banda_alto = max(1, int(ph * zona_superior_rel))
    banda = imagen[py:py + banda_alto, px:px + pw]

    gris = cv2.cvtColor(banda, cv2.COLOR_BGR2GRAY)
    binaria = cv2.threshold(gris, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

    # OCR con un par de reintentos (WinError 32: archivo temporal ocupado).
    datos = None
    ultimo_error = None
    for _ in range(3):
        try:
            datos = pytesseract.image_to_data(
                binaria, lang=idioma, config="--psm 6",
                output_type=pytesseract.Output.DICT,
            )
            break
        except Exception as exc:  # noqa: BLE001
            ultimo_error = exc
            time.sleep(0.4)
    if datos is None:
        raise RuntimeError(f"OCR falló: {ultimo_error}")

    candidatos = []
    for i in range(len(datos["text"])):
        texto = (datos["text"][i] or "").strip()
        if not texto or not PATRON_NUMERO.match(texto):
            continue
        try:
            conf = float(datos["conf"][i])
        except (ValueError, TypeError):
            conf = -1.0
        if conf < conf_min:
            continue
        candidatos.append(
            {
                "text": texto,
                "left": int(datos["left"][i]) + px,
                "top": int(datos["top"][i]) + py,
                "width": int(datos["width"][i]),
                "height": int(datos["height"][i]),
            }
        )

    if not candidatos:
        return None

    # El número del título es el más arriba; a igualdad, el más a la izquierda.
    candidatos.sort(key=lambda c: (c["top"], c["left"]))
    obj = candidatos[0]

    x1, y1 = obj["left"], obj["top"]
    x2, y2 = obj["left"] + obj["width"], obj["top"] + obj["height"]

    # Margen proporcional al tamaño del número (mínimo el que pida el usuario).
    m = max(margen, int(obj["height"] * 0.20))

    if conservar_punto and obj["text"][-1] in ".,-" and len(obj["text"]) > 1:
        # Deja fuera el signo final recortando ~1 carácter por la derecha.
        ancho_char = obj["width"] / len(obj["text"])
        x2 = int(x2 - ancho_char)

    x1 = max(0, x1 - m)
    y1 = max(0, y1 - m)
    x2 = min(w_img, x2 + m)
    y2 = min(h_img, y2 + m)

    mask = np.zeros((h_img, w_img), dtype=np.uint8)
    if x2 > x1 and y2 > y1:
        cv2.rectangle(mask, (x1, y1), (x2, y2), 255, -1)
    return mask


def crear_mascara_region(
    imagen: np.ndarray,
    ancho_rel: float,
    alto_rel: float,
    pos_x_rel: float,
    pos_y_rel: float,
    margen: int,
) -> np.ndarray:
    h, w = imagen.shape[:2]
    mask_w = max(10, int(w * ancho_rel))
    mask_h = max(10, int(h * alto_rel))
    cx, cy = int(w * pos_x_rel), int(h * pos_y_rel)
    x1 = max(0, cx - mask_w // 2 - margen)
    x2 = min(w, cx + mask_w // 2 + margen)
    y1 = max(0, cy - mask_h // 2 - margen)
    y2 = min(h, cy + mask_h // 2 + margen)
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.rectangle(mask, (x1, y1), (x2, y2), 255, -1)
    return mask


# --------------------------------------------------------------------------- #
#  Inpainting
# --------------------------------------------------------------------------- #
def inpaint_opencv(imagen: np.ndarray, mask: np.ndarray, radio: int) -> np.ndarray:
    return cv2.inpaint(imagen, mask, radio, cv2.INPAINT_TELEA)


def inpaint_lama(imagen: np.ndarray, mask: np.ndarray) -> np.ndarray:
    try:
        from simple_lama_inpainting import SimpleLama
    except ImportError as exc:
        raise RuntimeError(
            "No está instalado LaMa. Ejecuta:  pip install simple-lama-inpainting\n"
            "o utiliza --metodo opencv."
        ) from exc
    from PIL import Image
    lama = SimpleLama()
    imagen_pil = Image.fromarray(cv2.cvtColor(imagen, cv2.COLOR_BGR2RGB))
    resultado = lama(imagen_pil, Image.fromarray(mask))
    return cv2.cvtColor(np.array(resultado), cv2.COLOR_RGB2BGR)


# --------------------------------------------------------------------------- #
#  Procesamiento de una imagen
# --------------------------------------------------------------------------- #
def procesar_imagen(origen, destino, args, region_params) -> str:
    imagen = cv2.imread(str(origen), cv2.IMREAD_COLOR)
    if imagen is None:
        raise ValueError(f"No se pudo leer la imagen: {origen}")

    if args.deteccion == "ocr":
        mask = crear_mascara_ocr(
            imagen,
            idioma=args.idioma,
            zona_superior_rel=args.zona_superior,
            conf_min=args.conf_min,
            conservar_punto=args.conservar_punto,
            margen=args.margen,
            pagina_completa=args.pagina_completa,
        )
        if mask is None:
            if args.fallback_region:
                mask = crear_mascara_region(imagen, margen=args.margen, **region_params)
            else:
                destino.parent.mkdir(parents=True, exist_ok=True)
                cv2.imwrite(str(destino), imagen)  # copia sin cambios
                return "sin_numero"
    else:
        mask = crear_mascara_region(imagen, margen=args.margen, **region_params)

    if args.metodo == "lama":
        resultado = inpaint_lama(imagen, mask)
    else:
        resultado = inpaint_opencv(imagen, mask, args.radio)

    destino.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(destino), resultado):
        raise IOError(f"No se pudo guardar: {destino}")

    if args.guardar_mascara:
        cv2.imwrite(str(destino.with_name(f"{destino.stem}_MASK{destino.suffix}")), mask)

    return "ok"


# --------------------------------------------------------------------------- #
#  CLI
# --------------------------------------------------------------------------- #
def main() -> int:
    p = argparse.ArgumentParser(
        description="Borra el número antes del punto del título de páginas escaneadas."
    )
    p.add_argument("entrada", type=Path, help="Carpeta con las imágenes.")
    p.add_argument("salida", type=Path, help="Carpeta de salida.")
    p.add_argument("--desde", type=int, default=19,
                   help="Empieza en este fichero (posición, 1 = primero). Def: 19.")
    p.add_argument("--metodo", choices=("opencv", "lama"), default="opencv")
    p.add_argument("--deteccion", choices=("ocr", "region"), default="ocr")
    p.add_argument("--idioma", default="eng",
                   help="Idioma de Tesseract. Def: eng (suficiente para números).")
    p.add_argument("--zona-superior", type=float, default=0.18,
                   help="Franja superior donde buscar el título (proporción). Def: 0.18.")
    p.add_argument("--conf-min", type=float, default=50,
                   help="Confianza mínima del OCR para aceptar el número. Def: 50.")
    p.add_argument("--conservar-punto", action="store_true",
                   help="Borra solo el número y deja el punto.")
    p.add_argument("--fallback-region", action="store_true",
                   help="Si el OCR no encuentra número, usa la región fija.")
    p.add_argument("--pagina-completa", action="store_true",
                   help="No detectar la zona de página; usar la imagen entera.")
    # Modo region
    p.add_argument("--region-ancho", type=float, default=0.14)
    p.add_argument("--region-alto", type=float, default=0.06)
    p.add_argument("--region-x", type=float, default=0.30)
    p.add_argument("--region-y", type=float, default=0.09)
    # Comunes
    p.add_argument("--margen", type=int, default=6)
    p.add_argument("--radio", type=int, default=7)
    p.add_argument("--recursivo", action="store_true")
    p.add_argument("--guardar-mascara", action="store_true",
                   help="Guarda *_MASK (negro = se conserva, blanco = se borra).")

    args = p.parse_args()

    if not args.entrada.exists() or not args.entrada.is_dir():
        print(f"ERROR: no es una carpeta válida: {args.entrada}")
        return 1
    if args.desde < 1:
        print("ERROR: --desde debe ser >= 1")
        return 1

    archivos = obtener_archivos(args.entrada, args.recursivo)
    if not archivos:
        print("No se encontraron imágenes.")
        return 0

    total = len(archivos)
    seleccion = archivos[args.desde - 1:]
    if not seleccion:
        print(f"No hay ficheros desde la posición {args.desde} (solo hay {total}).")
        return 0

    region_params = {
        "ancho_rel": args.region_ancho, "alto_rel": args.region_alto,
        "pos_x_rel": args.region_x, "pos_y_rel": args.region_y,
    }

    print(f"Imágenes: {total}   Se procesan desde la posición {args.desde}: {len(seleccion)}")
    print(f"Detección: {args.deteccion}   Método: {args.metodo}   Idioma OCR: {args.idioma}")
    print(f"Salida: {args.salida}\n")

    ok = errores = 0
    sin_numero = []

    for offset, origen in enumerate(seleccion):
        posicion = args.desde + offset
        destino = args.salida / origen.relative_to(args.entrada)
        print(f"[{posicion}/{total}] {origen.name} ... ", end="")
        try:
            estado = procesar_imagen(origen, destino, args, region_params)
            if estado == "sin_numero":
                print("SIN NÚMERO (copiada tal cual)")
                sin_numero.append(origen.name)
            else:
                print("OK")
                ok += 1
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR: {exc}")
            errores += 1

    print(f"\nProcesadas: {ok}   Sin número: {len(sin_numero)}   Errores: {errores}")
    if sin_numero:
        print("\nPáginas sin número detectado (revísalas a mano si deberían tenerlo):")
        for nombre in sin_numero:
            print(f"  - {nombre}")

    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())