from datetime import datetime
from agents.base_agent import BaseAgent
from core.llm_client import generate_text_response
from core.telegram_client import send_message
from services.market_data import get_market_data
from config import TELEGRAM_DAILY_SUMMARY_TOPIC_ID

class SummaryAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Agente de Resumen Diario")

    def setup_schedule(self, schedule):
        # A las 17:00 hs locales
        schedule.every().day.at("17:00").do(self.run)

    def interpretar_datos(self, data):
        """Genera el prompt y llama a Gemini para redactar el resumen."""
        import json
        
        prompt = f"""
Actúa como un Analista de Mercados Financieros Institucional.
Tu tarea es escribir un breve reporte de cierre de mercado en base a las siguientes citas y variaciones de activos.

Datos del cierre de mercado:
{json.dumps(data, indent=2, ensure_ascii=False)}

Por favor, redacta un informe atractivo, profesional, y directo que el inversor pueda leer rápidamente por Telegram.
Instrucciones:
1. Usa etiquetas HTML de Telegram (ej. <b>texto</b>, <i>texto</i>) para resaltar tickers e ideas clave. NO uses markdown tradicional de asteriscos.
2. Comienza con un breve párrafo dando el panorama general del día (1 o 2 oraciones máximo).
3. Agrupa los movimientos en categorías e indica el valor de cierre y la variación porcentual.
4. Termina con una muy breve frase de conclusión o perspectiva.

Mantén el mensaje relativamente corto, directo al grano. Puedes usar emojis relacionados a las finanzas y mercados.
"""
        return generate_text_response(prompt)

    def run(self):
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [SummaryAgent] Obteniendo datos de mercado para el cierre...")
        
        # 1. Obtener datos crudos
        datos_mercado = get_market_data()
        
        if not datos_mercado:
            print("[SummaryAgent] No se pudieron obtener datos de mercado.")
            return

        # 2. IA Redacta el resumen
        print("[SummaryAgent] Datos obtenidos. Generando resumen con Gemini...")
        reporte_html = self.interpretar_datos(datos_mercado)

        if not reporte_html:
            print("[SummaryAgent] Error generando el reporte con la IA.")
            return

        # 3. Enviar a Telegram
        header = f"<b>📉 RESUMEN DE CIERRE DE MERCADOS ({datetime.now().strftime('%d/%m/%Y')})</b>\n\n"
        mensaje_final = header + reporte_html

        print(f"[SummaryAgent] Enviando resumen al topic {TELEGRAM_DAILY_SUMMARY_TOPIC_ID}...")
        sent = send_message(mensaje_final, topic_id=TELEGRAM_DAILY_SUMMARY_TOPIC_ID, parse_mode="HTML")
        if sent:
            print("[SummaryAgent] Resumen enviado con éxito.")
