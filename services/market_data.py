import os
import tempfile
import shutil
import certifi
import yfinance as yf

# ----- FIX PARA CARPETAS CON TILDES EN WINDOWS (curl_cffi / yfinance) -----
# Copia el certificado a una ruta limpia (sin tildes) en la carpeta Temp 
safe_cert_path = os.path.join(tempfile.gettempdir(), "cacert.pem")
if not os.path.exists(safe_cert_path):
    shutil.copy2(certifi.where(), safe_cert_path)
os.environ["CURL_CA_BUNDLE"] = safe_cert_path
os.environ["REQUESTS_CA_BUNDLE"] = safe_cert_path
# --------------------------------------------------------------------------
# Definición de activos y sus tickers referenciales en Yahoo Finance
ASSETS = {
    "S&P 500 (SPY)": "SPY",
    "Nasdaq 100 (QQQ)": "QQQ",
    "Dow Jones (DIA)": "DIA",
    "Bono US 10Y": "^TNX",
    "Petróleo WTI": "CL=F",
    "Oro": "GC=F",
    "Plata": "SI=F",
    "Soja": "ZS=F",
    "Trigo": "ZW=F",
    "Maíz": "ZC=F"
}

def get_market_data():
    """Obtiene precios y variación diaria de los activos definidos individualmente."""
    data = {}
    for name, ticker in ASSETS.items():
        try:
            ticker_obj = yf.Ticker(ticker)
            # Fetching 2 days or 5 days to ensure we get a previous close
            hist = ticker_obj.history(period="5d")
            
            if len(hist) < 2:
                # Mercado quizás no dio datos suficientes
                data[name] = {"price": 0.0, "variation": 0.0, "error": True}
                continue

            current_price = hist['Close'].iloc[-1]
            prev_close = hist['Close'].iloc[-2]
            
            variation_pct = ((current_price - prev_close) / prev_close) * 100
            
            data[name] = {
                "price": round(current_price, 2),
                "variation": round(variation_pct, 2)
            }
        except Exception as e:
            print(f"Error obteniendo datos para {name} ({ticker}): {e}")
            data[name] = {"price": 0.0, "variation": 0.0, "error": True}
            
    return data
