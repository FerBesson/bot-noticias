import html
import requests
import time
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

def split_text(text: str, limit: int = 4000) -> list:
    """Divide un texto en fragmentos que no excedan el límite, intentando cortar por saltos de línea."""
    if len(text) <= limit:
        return [text]

    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        
        # Intentar cortar por el último salto de línea doble antes del límite
        split_at = text.rfind('\n\n', 0, limit)
        if split_at == -1:
            # Si no hay doble salto, intentar con salto simple
            split_at = text.rfind('\n', 0, limit)
        if split_at == -1:
            # Si no hay saltos, intentar con espacio
            split_at = text.rfind(' ', 0, limit)
        if split_at == -1:
            # Si no hay nada, cortar al límite
            split_at = limit
        
        chunks.append(text[:split_at].strip())
        text = text[split_at:].strip()
    
    return chunks

def send_message(text: str, topic_id: str = None, parse_mode: str = "HTML", disable_web_page_preview: bool = True):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("ERROR: Faltan credenciales de Telegram.")
        return False

    # Dividir el mensaje si es muy largo
    chunks = split_text(text)
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    all_sent = True
    for chunk in chunks:
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": chunk,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview
        }

        if topic_id:
            payload["message_thread_id"] = topic_id

        try:
            req = requests.post(url, json=payload)
            if req.status_code != 200:
                print(f"Error enviando fragmento a Telegram: {req.text}")
                all_sent = False
            
            # Pequeña pausa para evitar hitting limits en mensajes seguidos
            if len(chunks) > 1:
                time.sleep(0.5)
                
        except Exception as e:
            print(f"Excepción al enviar a Telegram: {e}")
            all_sent = False
    
    return all_sent
