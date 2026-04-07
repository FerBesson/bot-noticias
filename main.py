import time
import schedule
from agents.news_agent import NewsAgent
from agents.summary_agent import SummaryAgent
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

def main():
    print("=== Bot de Mercados Multi-Agente Iniciado ===")
    
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("ERROR: Asegúrate de configurar TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID en tu archivo .env")
        exit(1)

    # Inicializamos los agentes
    agents = [
        NewsAgent(),
        SummaryAgent()
    ]

    print("Registrando programaciones (schedules)...")
    for agent in agents:
        agent.setup_schedule(schedule)
        print(f" - {agent.name} registrado.")

    print("\n[INFO] Ejecutando rutinas de inicio (NewsAgent)...")
    
    # Arrancamos con las noticias (la primera ejecución en el momento 0)
    # NOTA: SummaryAgent correrá a las 17:00hs según su schedule.
    agents[0].run()

    print("\nProgramador activo. Esperando siguientes ejecuciones. Presiona Ctrl+C para salir.")
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
