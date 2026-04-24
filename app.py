# -*- coding: utf-8 -*-
import os
import sys
import json
import requests as http
from flask import Flask, request, Response, send_from_directory, abort
from flask_cors import CORS

# Forzar UTF-8 en stdout/stderr para evitar errores de encoding en Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__, static_folder="static")
CORS(app)

GEMINI_API = (
    "https://generativelanguage.googleapis.com"
    "/v1beta/models/gemini-2.0-flash:generateContent"
)

SYSTEM_PROMPT = (
    "Eres un juez experto en Betta Splendens con certificacion IBC "
    "(International Betta Congress). Evalua la imagen usando el estandar "
    "tecnico IBC para seleccion de reproductores y valoracion comercial "
    "en el mercado estadounidense.\n\n"
    "PARAMETROS (escala 0-10):\n"
    "1. ALETAS (25%): Simetria bilateral, spreading >=180 grados, "
    "integridad de dorsal/caudal/anal/ventrales/pectorales\n"
    "2. COLOR (25%): Intensidad, uniformidad, patron, iridiscencia, "
    "brillo metalico, ausencia de decoloracion\n"
    "3. POSTURA (20%): Porte erguido, proporciones correctas, actitud "
    "dominante, cuerpo fusiforme sin deformidades\n"
    "4. MORPH (15%): Identificacion precisa del tipo (HM, HMPK, CT, DT, "
    "VT, Koi, Galaxy, Fancy, etc.) y pureza respecto al estandar\n"
    "5. CONDICION (15%): Salud general, ausencia de velvet/ich/fin rot/"
    "lesiones, peso y proporciones adecuadas\n\n"
    "CALCULO: nota_final = (aletas*0.25)+(color*0.25)+(postura*0.20)"
    "+(morph*0.15)+(condicion*0.15). Redondea a 1 decimal.\n\n"
    "CATEGORIAS:\n"
    "9.0-10.0 -> \"Campeon\"\n"
    "7.5-8.9  -> \"Show Quality\"\n"
    "6.0-7.4  -> \"Breeding Quality\"\n"
    "4.0-5.9  -> \"Pet Quality\"\n"
    "0.0-3.9  -> \"No recomendado\"\n\n"
    "Responde UNICAMENTE con JSON valido, sin markdown, sin texto adicional:\n"
    '{"nota_final":<decimal>,"categoria":<"Campeon"|"Show Quality"|'
    '"Breeding Quality"|"Pet Quality"|"No recomendado">,'
    '"morph_identificado":<string>,'
    '"scores":{"aletas":<0-10>,"color":<0-10>,"postura":<0-10>,'
    '"morph":<0-10>,"condicion":<0-10>},'
    '"comentarios":{"aletas":<string>,"color":<string>,"postura":<string>,'
    '"morph":<string>,"condicion":<string>},'
    '"resumen":<2-3 oraciones sobre breeding o reventa>,'
    '"recomendacion":<"Apto reproductor"|"Apto reventa premium"|'
    '"Apto reventa estandar"|"Solo mascota"|"No recomendado">}'
)


def _json(data, status=200):
    # ensure_ascii=True produce salida 100% ASCII (escapa ó → ó).
    # Imposible de fallar con UnicodeEncodeError en cualquier plataforma.
    body = json.dumps(data, ensure_ascii=True)
    return Response(body, status=status, content_type="application/json")


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json()
    if not data or "b64" not in data or "mime" not in data:
        return _json({"error": "Se requieren los campos b64 y mime"}, 400)

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return _json({"error": "GOOGLE_API_KEY no esta configurada en .env"}, 500)

    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{
            "parts": [
                {
                    "inline_data": {
                        "mime_type": data["mime"],
                        "data": data["b64"],
                    }
                },
                {
                    "text": (
                        "Evalua este betta splendens. "
                        "Responde SOLO con el JSON estructurado."
                    )
                },
            ]
        }],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 1500,
        },
    }

    try:
        resp = http.post(
            f"{GEMINI_API}?key={api_key}",
            json=payload,
            timeout=60,
        )

        # Decodificar siempre como UTF-8, ignorando lo que diga la cabecera
        body = json.loads(resp.content.decode("utf-8"))

        if not resp.ok:
            detail = body.get("error", {}).get("message", f"HTTP {resp.status_code}")
            return _json({"error": f"Error Gemini API: {detail}"}, 500)

        raw = body["candidates"][0]["content"]["parts"][0]["text"].strip()

        # Strip markdown code fences si Gemini envuelve el JSON
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(lines[1:])
            if raw.rstrip().endswith("```"):
                raw = raw.rstrip()[:-3].rstrip()

        result = json.loads(raw)
        return _json(result)

    except json.JSONDecodeError as e:
        return _json({"error": f"Error parseando respuesta: {e}"}, 500)
    except Exception as e:
        return _json({"error": f"Error inesperado: {e}"}, 500)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    print(f"\n  Betta Judge -> http://localhost:{port}")
    print("  Requiere: GOOGLE_API_KEY en archivo .env\n")
    app.run(host="0.0.0.0", port=port, debug=False)
