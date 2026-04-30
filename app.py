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
    "EVALUACION POR SEXO:\n\n"
    "MACHO:\n"
    "- ALETAS: spreading obligatorio >=180 grados (HM/DT), >=160 grados (HMPK/Plakat). "
    "Simetria bilateral perfecta en caudal, dorsal y anal. Ventrales largas y parejas. "
    "Penalizar asimetria, clamping, holes o bordes irregulares.\n"
    "- COLOR: maxima intensidad en flare. Iridiscencia y brillo metalico prominentes. "
    "Uniformidad del patron. Penalizar zonas decoloradas o wash-out.\n"
    "- POSTURA: actitud dominante, cuerpo fusiforme sin joroba, cabeza alineada.\n"
    "- MORPH: evaluar pureza estricta segun el tipo identificado.\n"
    "- CONDICION: peso adecuado, sin signos de enfermedad, aletas integras.\n\n"
    "HEMBRA:\n"
    "- ALETAS: aletas cortas son NORMALES. NO penalizar por spreading reducido. "
    "Evaluar integridad (sin fin rot, sin holes) y simetria relativa a su tipo.\n"
    "- COLOR: puede ser menos intensa que macho; evaluar calidad del patron "
    "y ausencia de decoloracion. En Koi/Galaxy evaluar distribucion cromatica.\n"
    "- POSTURA: cuerpo mas robusto y redondeado es normal. Mancha oviducto visible "
    "(punto blanco ventral) es signo positivo de condicion reproductora. "
    "Penalizar joroba, espina curvada o abdomen distendido anormal.\n"
    "- MORPH: mismos criterios de patron y tipo que macho; adaptar expectativa "
    "de aletas a proporciones normales de hembra.\n"
    "- CONDICION: prioritaria para breeding. Evaluar llenado corporal, "
    "ausencia de parasitos, color de agallas.\n\n"
    "Si no se especifica sexo: asumir macho salvo evidencia visual clara de hembra "
    "(cuerpo mas ancho, aletas cortas, mancha oviducto visible).\n\n"
    "EVALUACION POR MORPH (aplicar cuando el morph es conocido):\n\n"
    "HM - Halfmoon: Caudal en forma de D perfecta, spreading >=180 grados. "
    "Bordes del caudal rectos. Dorsal y anal proporcionales al caudal. "
    "Penalizar angulo menor a 180, bordes curvados o asimetria.\n\n"
    "HMPK - Halfmoon Plakat: Cuerpo compacto y musculoso. Aletas cortas pero "
    "spreading >=180 grados. Caudal con forma de D aunque reducida. "
    "Dorsal erecta y bien desarrollada. Penalizar cuerpo largo o spreading <160.\n\n"
    "CT - Crowntail: Extensiones de rayos mas alla del borde de membrana (webbing). "
    "Evaluar % de reduccion de membrana (>50% ideal) y simetria de rayos. "
    "Rayos dobles o cruzados penalizan. Extensiones parejas en todos los rayos.\n\n"
    "DT - Double Tail: Dos lobulos caudales claramente separados e igual tamano. "
    "Simetria entre lobulos critica. Dorsal extra-desarrollada es positiva. "
    "Penalizar lobulos de tamano desigual o fusion parcial.\n\n"
    "VT - Veiltail: Caudal largo y fluido, caida natural aceptable. "
    "Evaluar integridad y longitud. Color importa mas que el spread exacto.\n\n"
    "Koi / Galaxy / Koi Galaxy: Evaluar distribucion del patron de color sobre base "
    "clara o iridiscente. Galaxy: escamas iridiscentes y brillo metalico sobre fondo oscuro. "
    "Koi: manchas irregulares estilo carpa koi bien delimitadas. "
    "Koi Galaxy: combinacion de ambos; rareza del patron suma al score morph.\n\n"
    "Fancy / Multicolor: Evaluar numero de colores, separacion clara entre zonas, "
    "ausencia de bleeding (colores que se mezclan indeseablemente). "
    "Mayor complejidad del patron es positiva.\n\n"
    "Combinaciones (HMPK Koi, HMPK Galaxy, etc.): aplicar criterios de aletas "
    "del tipo de cola + criterios de color/patron del tipo de coloracion.\n\n"
    "Si el morph no es identificable con certeza: indicarlo en morph_identificado "
    "como \"Indeterminado - [descripcion breve]\" y bajar el score morph "
    "proporcionalmente a la incertidumbre.\n\n"
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

    sexo          = (data.get("sexo") or "").strip().lower()
    morph_usuario = (data.get("morph_usuario") or "").strip()

    parts = ["Evalua este betta splendens."]
    if sexo in ("macho", "hembra"):
        parts.append(f"Sexo: {sexo.capitalize()}.")
    if morph_usuario:
        parts.append(
            f"El criador identifica este pez como {morph_usuario}. "
            "Usa este morph como referencia principal para el parametro morph. "
            f"En morph_identificado devuelve exactamente \"{morph_usuario}\". "
            "No intentes reclasificarlo."
        )
    parts.append("Responde SOLO con el JSON estructurado.")
    user_text = " ".join(parts)

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
                {"text": user_text},
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
