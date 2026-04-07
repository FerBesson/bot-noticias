import json
import os
from datetime import datetime, timedelta, timezone
import feedparser
from bs4 import BeautifulSoup
from dateutil import parser

from config import HISTORY_FILE

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
        json.dump(history[-1500:], f)

def clean_html(raw_html):
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    return soup.get_text(separator=' ', strip=True)

def formatear_fecha(fecha_str):
    try:
        parsed = parser.parse(fecha_str)
        return parsed.strftime("%d/%m/%Y %H:%M UTC")
    except:
        return fecha_str if fecha_str else datetime.now().strftime("%d/%m/%Y %H:%M")

def recolectar_noticias_nuevas():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Recolectando noticias de feeds...")
    historial = load_history()
    noticias_candidatas = []
    nuevo_historial = list(historial)
    contador_id = 1

    for fuente_nombre, obj_url in FEEDS.items():
        try:
            feed = feedparser.parse(obj_url)
            for entry in feed.entries:
                link = entry.link
                if link not in historial:
                    fecha_raw = entry.get('published', '') or entry.get('pubDate', '')
                    
                    if fecha_raw:
                        try:
                            dt = parser.parse(fecha_raw)
                            if dt.tzinfo is None:
                                dt = dt.replace(tzinfo=timezone.utc)
                            now = datetime.now(timezone.utc)
                            if (now - dt) > timedelta(hours=4):
                                continue
                        except Exception:
                            pass 

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

    return noticias_candidatas, nuevo_historial
