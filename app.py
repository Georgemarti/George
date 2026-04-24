import os
import json
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import google.generativeai as genai

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__, static_folder="static")
CORS(app)

SYSTEM_PROMPT = """Eres un juez experto en Betta Splendens con certificación IBC (International Betta Congress).
Evalúa la imagen usando el estándar técnico IBC para selección de reproductores y valoración comercial en el mercado estadounidense.

PARÁMETROS (escala 0-10):
1. ALETAS (25%): Simetría bilateral, spreading ≥180°, integridad de dorsal/caudal/anal/ventrales/pectorales
2. COLOR (25%): Intensidad, uniformidad, patrón, iridiscencia, brillo metálico, ausencia de decoloración
3. POSTURA (20%): Porte erguido, proporciones correctas, actitud dominante, cuerpo fusiforme sin deformidades
4. MORPH (15%): Identificación precisa del tipo (HM, HMPK, CT, DT, VT, Koi, Galaxy, Fancy, etc.) y pureza respecto al estándar
5. CONDICIÓN (15%): Salud general, ausencia de velvet/ich/fin rot/lesiones, peso y proporciones adecuadas

CÁLCULO: nota_final = (aletas×0.25) + (color×0.25) + (postura×0.20) + (morph×0.15) + (condicion×0.15)
Redondea nota_final a 1 decimal.

CATEGORÍAS:
9.0-10.0 → "Campeón"
7.5-8.9  → "Show Quality"
6.0-7.4  → "Breeding Quality"
4.0-5.9  → "Pet Quality"
0.0-3.9  → "No recomendado"

Responde ÚNICAMENTE con JSON válido, sin markdown, sin texto adicional:
{
  "nota_final": <número con 1 decimal>,
  "categoria": <"Campeón"|"Show Quality"|"Breeding Quality"|"Pet Quality"|"No recomendado">,
  "morph_identificado": <nombre técnico completo>,
  "scores": {
    "aletas": <0.0-10.0>,
    "color": <0.0-10.0>,
    "postura": <0.0-10.0>,
    "morph": <0.0-10.0>,
    "condicion": <0.0-10.0>
  },
  "comentarios": {
    "aletas": <análisis técnico, 1-2 oraciones en español>,
    "color": <análisis técnico, 1-2 oraciones en español>,
    "postura": <análisis técnico, 1-2 oraciones en español>,
    "morph": <análisis técnico, 1-2 oraciones en español>,
    "condicion": <análisis técnico, 1-2 oraciones en español>
  },
  "resumen": <2-3 oraciones orientadas a breeding o reventa, en español>,
  "recomendacion": <"Apto reproductor"|"Apto reventa premium"|"Apto reventa estándar"|"Solo mascota"|"No recomendado">
}"""


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json()
    if not data or "b64" not in data or "mime" not in data:
        return jsonify({"error": "Se requieren los campos b64 y mime"}), 400

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return jsonify({"error": "GOOGLE_API_KEY no está configurada en el archivo .env"}), 500

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            system_instruction=SYSTEM_PROMPT,
        )

        image_part = {
            "inline_data": {
                "mime_type": data["mime"],
                "data": data["b64"],
            }
        }

        response = model.generate_content([
            image_part,
            "Evalúa este betta splendens. Responde SOLO con el JSON estructurado.",
        ])

        raw = response.text.strip()
        # Strip markdown code fences if Gemini wraps the JSON
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(lines[1:])
            if raw.rstrip().endswith("```"):
                raw = raw.rstrip()[:-3].rstrip()

        result = json.loads(raw)
        return jsonify(result)

    except json.JSONDecodeError as e:
        return jsonify({"error": f"Error parseando respuesta de IA: {e}"}), 500
    except Exception as e:
        return jsonify({"error": f"Error inesperado: {e}"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    print(f"\n🐟  Betta Judge → http://localhost:{port}")
    print("    Requiere: GOOGLE_API_KEY en entorno o archivo .env\n")
    app.run(host="0.0.0.0", port=port, debug=False)
