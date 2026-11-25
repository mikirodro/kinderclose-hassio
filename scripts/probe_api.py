"""Comprueba la API de KinderClose con una cuenta real sin mostrar datos personales.

Uso (las credenciales se leen del entorno y no se guardan):

    KINDERCLOSE_EMAIL=... KINDERCLOSE_PASSWORD=... .venv/bin/python scripts/probe_api.py

Muestra el estado HTTP y la *estructura* de cada respuesta: claves, tipos y el
formato de los textos con las letras y los dígitos enmascarados ("dddd-dd-dd").
Después usa el cliente de la integración para leer la última ficha y muestra qué
campos normalizados tienen valor. Al terminar cierra la sesión del dispositivo.
Revisa la salida antes de compartirla: no debería contener nombres ni valores.
"""
import asyncio
from datetime import date, timedelta
import json
import os
from pathlib import Path
import re
import sys

import aiohttp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from custom_components.kinderclose.client import KinderClose  # noqa: E402


def shape(value):
    if isinstance(value, dict):
        return {key: shape(item) for key, item in value.items()}
    if isinstance(value, list):
        return [shape(value[0]), f"len={len(value)}"] if value else []
    if isinstance(value, str):
        return "str:" + re.sub(r"[^\W\d_]", "a", re.sub(r"\d", "d", value))[:40]
    if isinstance(value, int) and not isinstance(value, bool) and -2 <= value <= 9:
        return f"int:{value}"  # Enumeraciones (comidas, tipos): su valor no identifica a nadie.
    return type(value).__name__


def filled(value):
    if isinstance(value, dict):
        return {key: filled(item) for key, item in value.items()}
    if isinstance(value, list):
        return f"{len(value)} elementos"
    return "con valor" if value not in (None, "", False) else "vacío"


async def main():
    email, password = os.environ.get("KINDERCLOSE_EMAIL"), os.environ.get("KINDERCLOSE_PASSWORD")
    if not email or not password:
        sys.exit("Define KINDERCLOSE_EMAIL y KINDERCLOSE_PASSWORD.")
    async with KinderClose(aiohttp.ClientSession(cookie_jar=aiohttp.DummyCookieJar()), email, password) as client:
        pupils = await client.pupils()
        print("Inicio de sesión correcto. Alumnos:", len(pupils), "activos:", sum(p["activo"] for p in pupils.values()))
        status, data = await client._request("GET", "/familiar/alumno")
        print("GET /familiar/alumno", status, json.dumps(shape(data), ensure_ascii=False))
        for pupil_id in pupils:
            print(f"\nAlumno n.º {list(pupils).index(pupil_id) + 1}")
            status, data = await client._request("GET", f"/familiar/alumno/{pupil_id}/ficha/null")
            print("  ficha de hoy:", status, json.dumps(shape(data), ensure_ascii=False))
            for days in range(1, 4):
                day = (date.today() - timedelta(days=days)).isoformat()
                status, data = await client._request("GET", f"/familiar/alumno/{pupil_id}/ficha/null", {"fecha": day})
                print(f"  ficha de hace {days} días:", status, json.dumps(shape(data.get("fecha") if isinstance(data, dict) else data)))
            result = await client.fetch(pupil_id)
            print("  ficha normalizada:", json.dumps(filled(result["ficha"]), ensure_ascii=False) if result["ficha"] else "ninguna en los últimos días")
        await client.logout()


if __name__ == "__main__":
    asyncio.run(main())
