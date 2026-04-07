import json
from datetime import datetime
from agents.base_agent import BaseAgent
from services.feed_reader import recolectar_noticias_nuevas, save_history, formatear_fecha
from core.llm_client import generate_json_response
from core.telegram_client import send_message
from config import TELEGRAM_NEWS_TOPIC_ID

class NewsAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Agente de Noticias")

    def setup_schedule(self, schedule):
        # Ejecutar cada 1 hora
        schedule.every(1).hours.do(self.run)

    def procesar_con_ia(self, noticias_candidatas):
        if not noticias_candidatas:
            return []
        
        lista_para_ia = []
        for noti in noticias_candidatas:
            lista_para_ia.append({
                "id": noti["id"],
                "titulo": noti["titulo"],
                "desc": noti["desc"][:750]  # Reducido a 750 caracteres para ahorrar tokens
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
    "resumen": "Un resumen extremadamente corto y directo, yendo directo al grano y sin utilizar palabras de relleno (máximo 2 oraciones en ESPAÑOL)",
    "sector": "Ej. Commodities, Macro U.S., Central Banks, Geopolítica, etc."
  }}
]

Si ninguna noticia de la lista tiene relevancia >= 7, devuelve un arreglo vacío [].
¡Es OBLIGATORIO que devuelvas SOLO EL JSON sin comillas invertidas (```), sin la palabra JSON y sin texto adicional!
"""
        return generate_json_response(prompt) or []

    def enviar_bloque(self, noticias_formateadas):
        import html
        if not noticias_formateadas:
            return
            
        print(f"[NewsAgent] Enviando {len(noticias_formateadas)} noticias a Telegram de forma individual...")

        for nf in noticias_formateadas:
            titulo = html.escape(nf['titulo'])
            fuente = html.escape(nf['fuente'])
            sector = html.escape(nf['sector'])
            resumen = html.escape(nf['resumen'])
            fecha = html.escape(nf['fecha'])
            link = nf['link']
            sentimiento = html.escape(str(nf.get('sentimiento', 'Neutral')))
            relevancia = html.escape(str(nf.get('relevancia', '7')))
            impacto = html.escape(str(nf.get('impacto_esperado', 'Desconocido')))

            mensaje = ""
            mensaje += f"📰 <b>{titulo}</b>\n"
            mensaje += f"📈 <b>Relevancia:</b> {relevancia}/10 | <b>Sentimiento:</b> {sentimiento}\n"
            mensaje += f"🏢 <b>Fuente:</b> {fuente} | <b>Sector:</b> {sector}\n"
            mensaje += f"📝 <b>Resumen:</b> {resumen}\n"
            mensaje += f"💥 <b>Impacto Esperado:</b> {impacto}\n"
            mensaje += f"🕒 <b>Publicado:</b> {fecha}\n"
            mensaje += f"🔗 <a href='{link}'>Leer noticia completa</a>\n"

            sent = send_message(mensaje, topic_id=TELEGRAM_NEWS_TOPIC_ID)
            if not sent:
                print(f"❌ Error al enviar la noticia: {titulo}")

        print(f"✅ Bloque de {len(noticias_formateadas)} noticias procesado.")

    def run(self):
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [NewsAgent] Iniciando búsqueda horaria...")
        noticias_candidatas, nuevo_historial = recolectar_noticias_nuevas()
        
        if not noticias_candidatas:
            print("[NewsAgent] No se encontraron noticias nuevas en esta hora.")
            return

        print(f"[NewsAgent] Se recolectaron {len(noticias_candidatas)} noticias. Evaluando con IA...")
        seleccionadas_ia = self.procesar_con_ia(noticias_candidatas)
        
        noticias_finales_a_enviar = []
        for item_ia in seleccionadas_ia:
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

        if noticias_finales_a_enviar:
            noticias_finales_a_enviar.sort(key=lambda x: int(x.get("relevancia", 0)), reverse=True)
            noticias_finales_a_enviar = noticias_finales_a_enviar[:5]

        for n in noticias_candidatas:
            if n["link"] not in nuevo_historial:
                nuevo_historial.append(n["link"])

        if noticias_finales_a_enviar:
            self.enviar_bloque(noticias_finales_a_enviar)
            save_history(nuevo_historial)
        else:
            print("[NewsAgent] La IA descartó las candidatas porque no cumplían con los requisitos.")
            save_history(nuevo_historial)
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [NewsAgent] Ciclo finalizado.")
