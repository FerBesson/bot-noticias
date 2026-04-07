import os
import time
import json
import feedparser
import requests
import schedule
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from dateutil import parser
from dotenv import load_dotenv
import google.generativeai as genai

# Cargar variables de entorno
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_TOPIC_ID = os.getenv("TELEGRAM_TOPIC_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configurar Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    # Usar el modelo gen-2.5-flash
    model = genai.GenerativeModel('gemini-2.5-flash')
else:
    print("ADVERTENCIA: No se configuró GEMINI_API_KEY.")
    model = None

# Archivo de historial para no repetir envíos
HISTORY_FILE = "noticias_enviadas.json"

FEEDS = {
    "Yahoo Finance": "https://finance.yahoo.com/news/rss",
    "CNBC": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
    # Buscamos noticias financieras globales recientes en Google News
    "Google Finance (News)": "https://news.google.com/rss/search?q=when:24h+finance+markets&hl=en-US&gl=US&ceid=US:en",
    "Investing.com": "https://www.investing.com/rss/news_25.rss"
}

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return []

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history[-1500:], f) # Mantenemos solo las ultimas 1500 para no hacer infinito el file

def clean_html(raw_html):
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    return soup.get_text(separator=' ', strip=True)

def formatear_fecha(fecha_str):
    try:
        # Intentar formatear con un estilo estandar si viene del feed (suelen ser tipo RFC 822)
        # Como fallback, parseo simplificado devolviendo hora actual o la original.
        from dateutil import parser
        parsed = parser.parse(fecha_str)
        return parsed.strftime("%d/%m/%Y %H:%M UTC")
    except:
        return fecha_str if fecha_str else datetime.now().strftime("%d/%m/%Y %H:%M")

def procesar_con_ia(noticias_candidatas):
    if not model or not noticias_candidatas:
        return []
    
    # Preparamos un listado simplificado para que la IA no se pierda leyendo tanto HTML
    lista_para_ia = []
    for noti in noticias_candidatas:
        lista_para_ia.append({
            "id": noti["id"],
            "titulo": noti["titulo"],
            "desc": noti["desc"][:400] # Acortamos la descripcion para tokens
        })
    
    prompt = f"""
Actúa como un analista financiero experto. Te daré una lista de noticias recientes en formato JSON.
Tu tarea es filtrar y seleccionar un MÁXIMO de 5 o 6 noticias globales que sean las MÁS relevantes y de alto impacto, EXCLUSIVAMENTE sobre estos temas:
1. Macroeconomía de Estados Unidos (Tasas, FED, inflación, etc)
2. Acciones Globales (Global Stocks destacados)
3. Conflictos Bélicos con impacto en el mercado global

Si una noticia no encaja fuertemente en esos temas, ignórala. Queremos evitar el spam.

Aquí están las noticias candidatas:
{json.dumps(lista_para_ia, ensure_ascii=False)}

Debes devolver ÚNICAMENTE un JSON válido que sea un arreglo bidimensional (lista de objetos) con las noticias que seleccionaste, en este formato exacto:
[
  {{
    "id": 1,
    "resumen": "Un resumen corto de máximo 2 oraciones, directo y profesional en ESPAÑOL",
    "sector": "Escribe un nombre de sector o tema muy específico creado por ti (ej. Inteligencia Artificial, Tasas de la FED, Guerra en Medio Oriente, Chips, etc)"
  }}
]
¡Es OBLIGATORIO que devuelvas SOLO EL JSON sin comillas invertidas (```), sin la palabra JSON y sin texto adicional!
"""
    try:
        response = model.generate_content(prompt)
        text_resp = response.text.replace('```json', '').replace('```', '').strip()
        data = json.loads(text_resp)
        # Si devuelve un diccionario por error envuelto en otra llave, corregir.
        if isinstance(data, dict):
             # a veces Gemini responde {"noticias": [...]}
             for _, v in data.items():
                 if isinstance(v, list): return v
             return []
        if isinstance(data, list):
            return data
        return []
    except Exception as e:
        print(f"Error al usar Gemini o parsear JSON: {e}")
        return []

def enviar_telegram_bloque(noticias_formateadas):
    if not noticias_formateadas:
        print("No hay noticias relevantes para enviar en esta hora.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    # Armamos el mensaje con HTML
    mensaje = f"<b>📊 RESUMEN HORARIO DE MERCADOS</b>\n<i>Selección de Macro U.S., Acciones y Geopolítica</i>\n\n"
    
    for nf in noticias_formateadas:
        mensaje += f"📰 <b>{nf['titulo']}</b>\n"
        mensaje += f"🏢 <b>Fuente:</b> {nf['fuente']}\n"
        mensaje += f"📊 <b>Sector:</b> {nf['sector']}\n"
        mensaje += f"📝 <b>Resumen:</b> {nf['resumen']}\n"
        mensaje += f"🕒 <b>Publicado:</b> {nf['fecha']}\n"
        mensaje += f"🔗 <a href='{nf['link']}'>Leer noticia completa</a>\n\n"

    # Si por alguna razon el mensaje supera el limite de Telegram
    if len(mensaje) > 4000:
        mensaje = mensaje[:3800] + "\n\n...(Mensaje cortado por límite de longitud)"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje,
        "parse_mode": "HTML",
        "disable_web_page_preview": True # Previene que los links generen miniaturas gigantes
    }

    if TELEGRAM_TOPIC_ID:
        payload["message_thread_id"] = TELEGRAM_TOPIC_ID

    try:
        req = requests.post(url, json=payload)
        if req.status_code != 200:
            print(f"Error Telegram: {req.text}")
        else:
            print(f"✅ Bloque de {len(noticias_formateadas)} noticias enviadas a Telegram de forma exitosa.")
    except Exception as e:
        print(f"Error request Telegram: {e}")

def buscar_y_procesar_noticias():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Iniciando búsqueda horaria y recolección...")
    historial = load_history()
    noticias_candidatas = []
    
    nuevo_historial = list(historial)
    contador_id = 1

    for fuente_nombre, obj_url in FEEDS.items():
        try:
            feed = feedparser.parse(obj_url)
            # Tomamos las más recientes de cada feed
            for entry in feed.entries[:8]:
                link = entry.link
                if link not in historial:
                    fecha_raw = entry.get('published', '') or entry.get('pubDate', '')
                    
                    # Filtro de noticias estricto: solo las de "hoy" (últimas 24 hs aprox)
                    if fecha_raw:
                        try:
                            dt = parser.parse(fecha_raw)
                            if dt.tzinfo is None:
                                dt = dt.replace(tzinfo=timezone.utc)
                            now = datetime.now(timezone.utc)
                            # Si la noticia tiene más de 24 horas, la ignoramos.
                            if (now - dt) > timedelta(hours=24):
                                continue
                        except Exception:
                            pass # si no pudimos parsear la fecha, la dejamos pasar como actual.

                    titulo = entry.title
                    desc = clean_html(entry.get('summary', '') or entry.get('description', ''))
                    
                    noticias_candidatas.append({
                        "id": contador_id,
                        "fuente": fuente_nombre,
                        "titulo": titulo,
                        "desc": desc,
                        "link": link,
                        "fecha_raw": fecha_raw
                    })
                    contador_id += 1
        except Exception as e:
            print(f"Error leyendo {fuente_nombre}: {e}")

    if not noticias_candidatas:
        print("No se encontraron noticias nuevas en esta hora.")
        return

    print(f"Se recolectaron {len(noticias_candidatas)} noticias para filtrar. Evaluando con IA...")
    
    # La IA selecciona y resume
    seleccionadas_ia = procesar_con_ia(noticias_candidatas)
    
    # Relacionamos el ID que devolvió la IA con la info original
    noticias_finales_a_enviar = []
    
    for item_ia in seleccionadas_ia:
        # Buscar en el dict original el ID que eligió
        noti_original = next((n for n in noticias_candidatas if n["id"] == item_ia.get("id")), None)
        
        if noti_original:
            noticias_finales_a_enviar.append({
                "titulo": noti_original["titulo"],
                "fuente": noti_original["fuente"],
                "link": noti_original["link"],
                "fecha": formatear_fecha(noti_original["fecha_raw"]),
                "resumen": item_ia.get("resumen", "Sin resumen"),
                "sector": item_ia.get("sector", "General")
            })
            # La marcamos como enviada y agregamos al historial real
            nuevo_historial.append(noti_original["link"])

    # Enviamos un solo mensaje si hubo elegidas
    if noticias_finales_a_enviar:
        enviar_telegram_bloque(noticias_finales_a_enviar)
        save_history(nuevo_historial)
    else:
        print("La IA descartó las candidatas porque no cumplían con los requisitos.")
        # Opcional: podemos marcarlas como procesadas para que no vuelva a evaluarlas
        for n in noticias_candidatas:
            nuevo_historial.append(n["link"])
        save_history(nuevo_historial)

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Ciclo horario finalizado.")

if __name__ == "__main__":
    print("=== Bot de Noticias de Mercado (Agrupado & Filtrado) Iniciado ===")
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("ERROR: Asegúrate de configurar TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID en tu archivo .env")
        exit(1)
        
    if not GEMINI_API_KEY:
        print("ADVERTENCIA: No tienes GEMINI_API_KEY configurada, la IA no funcionará.")
    
    # Ejecutar una vez al inicio
    buscar_y_procesar_noticias()

    # Programar la ejecución cada 1 hora
    schedule.every(1).hours.do(buscar_y_procesar_noticias)

    print("Programador activo (ejecución cada 1 hora). Presiona Ctrl+C para salir.")
    while True:
        schedule.run_pending()
        time.sleep(60)
