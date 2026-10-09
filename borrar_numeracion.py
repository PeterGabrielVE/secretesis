#!/usr/bin/env python3
"""
Elimina automáticamente la numeración de páginas situada en la parte
inferior/central de imágenes escaneadas.

Por defecto usa OpenCV Inpainting (TELEA), que funciona muy bien cuando
la zona a reconstruir es papel relativamente uniforme.

Opcionalmente puede usarse LaMa (inpainting generativo) si instalas:
    pip install simple-lama-inpainting

Ejemplos:
    python borrar_numeracion.py ./paginas ./paginas_sin_numeracion

    python borrar_numeracion.py ./paginas ./salida --metodo lama

    python borrar_numeracion.py ./paginas ./salida --ancho 0.18 --alto 0.07
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import cv2
import numpy as np


EXTENSIONES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def crear_mascara_numeracion(
    imagen: np.ndarray,
    ancho_rel: float = 0.16,
    alto_rel: float = 0.075,
    desplazamiento_x: float = 0.0,
    margen: int = 12,
) -> np.ndarray:
    """
    Crea una máscara rectangular alrededor del número de página.

    ancho_rel: ancho de la máscara como proporción del ancho de imagen.
    alto_rel: altura de la máscara como proporción del alto de imagen.
    desplazamiento_x: mueve la máscara horizontalmente (-1 a 1).
    margen: margen adicional para asegurar que se cubran los dígitos.
    """
    h, w = imagen.shape[:2]

    mask_w = max(20, int(w * ancho_rel))
    mask_h = max(20, int(h * alto_rel))

    centro_x = int(w * (0.50 + desplazamiento_x))
    centro_y = int(h * 0.955)

    x1 = max(0, centro_x - mask_w // 2 - margen)
    x2 = min(w, centro_x + mask_w // 2 + margen)
    y1 = max(0, centro_y - mask_h // 2 - margen)
    y2 = min(h, centro_y + mask_h // 2 + margen)

    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.rectangle(mask, (x1, y1), (x2, y2), 255, -1)

    return mask


def inpaint_opencv(imagen: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """
    Reconstrucción rápida mediante OpenCV.
    """
    return cv2.inpaint(imagen, mask, 7, cv2.INPAINT_TELEA)


def inpaint_lama(imagen: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """
    Reconstrucción generativa mediante LaMa.

    Requiere:
        pip install simple-lama-inpainting
    """
    try:
        from simple_lama_inpainting import SimpleLama
    except ImportError:
        raise RuntimeError(
            "No está instalado LaMa. Ejecuta:\n"
            "    pip install simple-lama-inpainting\n"
            "o utiliza --metodo opencv."
        )

    from PIL import Image

    lama = SimpleLama()

    # SimpleLama espera PIL Image y máscara PIL.
    imagen_pil = Image.fromarray(cv2.cvtColor(imagen, cv2.COLOR_BGR2RGB))
    mask_pil = Image.fromarray(mask)

    resultado = lama(imagen_pil, mask_pil)

    return cv2.cvtColor(np.array(resultado), cv2.COLOR_RGB2BGR)


def procesar_imagen(
    origen: Path,
    destino: Path,
    metodo: str,
    ancho_rel: float,
    alto_rel: float,
    desplazamiento_x: float,
    margen: int,
    guardar_mascara: bool,
) -> None:
    imagen = cv2.imread(str(origen), cv2.IMREAD_COLOR)

    if imagen is None:
        raise ValueError(f"No se pudo leer la imagen: {origen}")

    mask = crear_mascara_numeracion(
        imagen,
        ancho_rel=ancho_rel,
        alto_rel=alto_rel,
        desplazamiento_x=desplazamiento_x,
        margen=margen,
    )

    if metodo == "lama":
        resultado = inpaint_lama(imagen, mask)
    else:
        resultado = inpaint_opencv(imagen, mask)

    destino.parent.mkdir(parents=True, exist_ok=True)

    if not cv2.imwrite(str(destino), resultado):
        raise IOError(f"No se pudo guardar: {destino}")

    if guardar_mascara:
        mascara_path = destino.with_name(
            f"{destino.stem}_MASK{destino.suffix}"
        )
        cv2.imwrite(str(mascara_path), mask)


def obtener_archivos(carpeta: Path, recursivo: bool) -> list[Path]:
    patron = "**/*" if recursivo else "*"
    return sorted(
        p for p in carpeta.glob(patron)
        if p.is_file() and p.suffix.lower() in EXTENSIONES
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Borra la numeración inferior de páginas escaneadas."
    )

    parser.add_argument(
        "entrada",
        type=Path,
        help="Carpeta que contiene las imágenes.",
    )
    parser.add_argument(
        "salida",
        type=Path,
        help="Carpeta donde se guardarán las imágenes procesadas.",
    )
    parser.add_argument(
        "--metodo",
        choices=("opencv", "lama"),
        default="opencv",
        help="opencv = rápido; lama = inpainting generativo.",
    )
    parser.add_argument(
        "--ancho",
        type=float,
        default=0.16,
        help="Ancho relativo de la máscara. Por defecto: 0.16.",
    )
    parser.add_argument(
        "--alto",
        type=float,
        default=0.075,
        help="Alto relativo de la máscara. Por defecto: 0.075.",
    )
    parser.add_argument(
        "--desplazamiento-x",
        type=float,
        default=0.0,
        help="Mueve la máscara horizontalmente. 0 = centro.",
    )
    parser.add_argument(
        "--margen",
        type=int,
        default=12,
        help="Margen adicional alrededor de la numeración.",
    )
    parser.add_argument(
        "--recursivo",
        action="store_true",
        help="Procesa también subcarpetas.",
    )
    parser.add_argument(
        "--guardar-mascara",
        action="store_true",
        help="Guarda una imagen *_MASK para revisar qué zona se borró.",
    )

    args = parser.parse_args()

    if not args.entrada.exists():
        print(f"ERROR: no existe la carpeta: {args.entrada}")
        return 1

    if not args.entrada.is_dir():
        print(f"ERROR: no es una carpeta: {args.entrada}")
        return 1

    if not 0.01 <= args.ancho <= 0.50:
        print("ERROR: --ancho debe estar entre 0.01 y 0.50")
        return 1

    if not 0.01 <= args.alto <= 0.30:
        print("ERROR: --alto debe estar entre 0.01 y 0.30")
        return 1

    archivos = obtener_archivos(args.entrada, args.recursivo)

    if not archivos:
        print("No se encontraron imágenes.")
        return 0

    print(f"Imágenes encontradas: {len(archivos)}")
    print(f"Método: {args.metodo}")
    print(f"Salida: {args.salida}")
    print()

    procesadas = 0
    errores = 0

    for indice, origen in enumerate(archivos, start=1):
        relativo = origen.relative_to(args.entrada)
        destino = args.salida / relativo

        print(f"[{indice}/{len(archivos)}] {origen.name} ... ", end="")

        try:
            procesar_imagen(
                origen=origen,
                destino=destino,
                metodo=args.metodo,
                ancho_rel=args.ancho,
                alto_rel=args.alto,
                desplazamiento_x=args.desplazamiento_x,
                margen=args.margen,
                guardar_mascara=args.guardar_mascara,
            )
            print("OK")
            procesadas += 1
        except Exception as exc:
            print(f"ERROR: {exc}")
            errores += 1

    print()
    print(f"Procesadas: {procesadas}")
    print(f"Errores:    {errores}")

    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
