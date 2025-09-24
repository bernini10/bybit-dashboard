import time
import logging
from datetime import datetime, timezone, timedelta
import pandas as pd
from pybit.unified_trading import HTTP

def fetch_bybit_data(api_key, api_secret, start_date_str, end_date_str):
    """Busca dados da Bybit, lidando com paginação e o limite de 7 dias."""
    try:
        session = HTTP(api_key=api_key, api_secret=api_secret)
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    except Exception as e:
        logging.error(f"Erro nas credenciais ou formato de data: {e}")
        return None, f"Erro nas credenciais ou formato de data: {e}"

    all_executions = []
    current_start_dt = start_date
    
    while current_start_dt < end_date:
        current_end_dt = min(current_start_dt + timedelta(days=7), end_date)
        start_ts = int(current_start_dt.replace(tzinfo=timezone.utc).timestamp() * 1000)
        end_ts = int(current_end_dt.replace(tzinfo=timezone.utc).timestamp() * 1000)
        
        logging.info(f"Buscando dados de {current_start_dt.date()} a {current_end_dt.date()}...")
        
        cursor = ""
        while True:
            try:
                response = session.get_executions(
                    category="linear", startTime=start_ts, endTime=end_ts, limit=100, cursor=cursor
                )
                if response['retCode'] == 0:
                    executions = response['result']['list']
                    all_executions.extend(executions)
                    cursor = response['result'].get('nextPageCursor', "")
                    if not cursor: break
                    time.sleep(0.2)
                else:
                    msg = f"Erro da API Bybit ao buscar trades: {response['retMsg']} (ErrCode: {response['retCode']})"
                    logging.error(msg)
                    return None, msg
            except Exception as e:
                msg = f"Exceção ao buscar trades: {e}"
                logging.error(msg)
                return None, msg
        
        current_start_dt += timedelta(days=7)

    return pd.DataFrame(all_executions), None
