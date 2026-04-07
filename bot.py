import os
import time
import json
import html
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
    "Yahoo Finance (Top)": "https://finance.yahoo.com/news/rss",
    "CNBC (Top)": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
    "Google News (Macro)": "https://news.google.com/rss/search?q=(FED+OR+inflation+OR+macro+OR+earnings)+AND+(US+OR+global)+when:24h&hl=en-US&gl=US&ceid=US:en",
    "Investing (Commodities)": "https://www.investing.com/rss/commodities.rss",
    "Investing (Central Banks)": "https://www.investing.com/rss/central_banks.rss"
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
            "desc": noti["desc"][:1000] # Acortamos la descripcion para tokens
        })
    
    prompt = f"""
Actúa como un Portfolio Manager Institucional. Evalúa estas noticias recientes.
Para cada noticia, decide su relevancia del 1 al 10 basándote en su utilidad e impacto para un inversor.
⚠️ INSTRUCCIONES DE PUNTUACIÓN:
- 8 a 10: Noticias muy relevantes (balances de empresas grandes, datos macroeconómicos, movimientos fuertes de commodities o acciones líderes).
- 7: Noticias importantes que resaltan tendencias del sector financiero y que un inversor agradecería leer.
- 1 a 6: Ruido diario, resúmenes genéricos, eventos corporativos menores sin impacto global.

Aquí están las noticias candidatas:
{json.dumps(lista_para_ia, ensure_ascii=False)}

Devuelve ÚNICAMENTE un JSON válido que sea un arreglo (lista de objetos) con AQUELLAS noticias que superen una calificación de relevancia de 7 o más (>= 7). Usa EXACTAMENTE este formato:
[
  {{
    "id": 1,
    "relevancia": 8,
    "sentimiento": "🔴 Bearish",
    "impacto_esperado": "Podría subir los rendimientos de los bonos...",
    "resumen": "Un resumen corto de máximo 2 oraciones, directo y profesional en ESPAÑOL",
    "sector": "Ej. Commodities, Macro U.S., Central Banks, Geopolítica, etc."
  }}
]

Si ninguna noticia de la lista tiene relevancia >= 7, devuelve un arreglo vacío [].
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
    mensaje = f"<b>📊 RESUMEN HORARIO DE MERCADOS</b>\n<i>Filtro de Alto Impacto (Relevancia >= 7)</i>\n\n"
    
    for nf in noticias_formateadas:
        # Escapamos los contenidos dinamicos para evitar errores en el parse_mode="HTML"
        titulo = html.escape(nf['titulo'])
        fuente = html.escape(nf['fuente'])
        sector = html.escape(nf['sector'])
        resumen = html.escape(nf['resumen'])
        fecha = html.escape(nf['fecha'])
        link = nf['link']
        sentimiento = html.escape(str(nf.get('sentimiento', 'Neutral')))
        relevancia = html.escape(str(nf.get('relevancia', '7')))
        impacto = html.escape(str(nf.get('impacto_esperado', 'Desconocido')))

        mensaje += f"📰 <b>{titulo}</b>\n"
        mensaje += f"📈 <b>Relevancia:</b> {relevancia}/10 | <b>Sentimiento:</b> {sentimiento}\n"
        mensaje += f"🏢 <b>Fuente:</b> {fuente} | <b>Sector:</b> {sector}\n"
        mensaje += f"📝 <b>Resumen:</b> {resumen}\n"
        mensaje += f"💥 <b>Impacto Esperado:</b> {impacto}\n"
        mensaje += f"🕒 <b>Publicado:</b> {fecha}\n"
        mensaje += f"🔗 <a href='{link}'>Leer noticia completa</a>\n\n"

    # Si el mensaje supera el limite de Telegram (4096 caracteres), lo cortamos de forma segura.
    # Un error "Unclosed start tag" suele ocurrir si truncamos en medio de un tag HTML.
    if len(mensaje) > 4090:
        # Cortamos y nos aseguramos de no dejar tags abiertos de forma simple (aunque el escape ya ayuda mucho)
        mensaje = mensaje[:4000] + "\n\n...(Mensaje cortado por longitud)"

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
            # Tomamos todos los elementos del feed, la fecha de c/u será el filtro
            for entry in feed.entries:
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
                            # Filtro estricto: Si la noticia tiene más de 4 horas, la ignoramos.
                            # Reduce dramáticamente el spam inicial.
                            if (now - dt) > timedelta(hours=4):
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
                "sector": item_ia.get("sector", "General"),
                "sentimiento": item_ia.get("sentimiento", "Neutral"),
                "relevancia": item_ia.get("relevancia", 7),
                "impacto_esperado": item_ia.get("impacto_esperado", "Desconocido")
            })
            # ...
            # No guardamos al historial aquí individualmente, lo haremos debajo para TODAS.

    # Ordenar por relevancia descendente y quedarnos con el Top 5
    if noticias_finales_a_enviar:
        # Nos aseguramos de castear relevancia a int para ordenamiento seguro
        noticias_finales_a_enviar.sort(key=lambda x: int(x.get("relevancia", 0)), reverse=True)
        noticias_finales_a_enviar = noticias_finales_a_enviar[:5]

    # TODAS las evaluadas (elegidas o descartadas) van al historial para no consumir más tokens
    for n in noticias_candidatas:
        if n["link"] not in nuevo_historial:
            nuevo_historial.append(n["link"])

    # Enviamos un solo mensaje si hubo elegidas
    if noticias_finales_a_enviar:
        enviar_telegram_bloque(noticias_finales_a_enviar)
        save_history(nuevo_historial)
    else:
        print("La IA descartó las candidatas porque no cumplían con los requisitos.")
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
