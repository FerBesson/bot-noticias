import json
import google.generativeai as genai
from config import GEMINI_API_KEY

model = None
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
else:
    print("ADVERTENCIA: No se configuró GEMINI_API_KEY.")

def generate_json_response(prompt: str):
    """Ejecuta un prompt y asume que la respuesta esperada es un JSON (lista o dict)."""
    if not model:
        return None
    try:
        response = model.generate_content(prompt)
        text_resp = response.text.replace('```json', '').replace('```', '').strip()
        data = json.loads(text_resp)
        # Si devuelve un diccionario por error envuelto en otra llave
        if isinstance(data, dict):
            for _, v in data.items():
                if isinstance(v, list) or isinstance(v, dict): 
                    return v
            return data
        return data
    except Exception as e:
        print(f"Error al usar Gemini o parsear JSON: {e}")
        return None

def generate_text_response(prompt: str):
    """Ejecuta un prompt y devuelve texto plano o markdown."""
    if not model:
        return None
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Error generando texto con Gemini: {e}")
        return None
