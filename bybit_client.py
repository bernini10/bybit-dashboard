import pandas as pd
from datetime import datetime, timedelta
from pybit.unified_trading import HTTP
import time
import logging

def fetch_all_trades(api_key, api_secret, start_date_str, end_date_str):
    """
    Busca todos os trades de uma conta Bybit em um determinado período.
    """
    session = HTTP(
        testnet=False,
        api_key=api_key,
        api_secret=api_secret,
    )
    
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    
    all_trades = []
    current_start = start_date
    while current_start <= end_date:
        current_end = min(current_start + timedelta(days=6), end_date)
        start_timestamp = int(current_start.timestamp() * 1000)
        end_timestamp = int((current_end + timedelta(days=1) - timedelta(seconds=1)).timestamp() * 1000)

        logging.info(f"Buscando dados de trades de {current_start.strftime('%Y-%m-%d')} a {current_end.strftime('%Y-%m-%d')}...")
        
        cursor = ""
        while True:
            try:
                response = session.get_executions(
                    category="linear", limit=100, cursor=cursor,
                    startTime=start_timestamp, endTime=end_timestamp,
                )
                if response['retCode'] != 0:
                    raise Exception(f"Erro da API Bybit (Trades): {response['retMsg']} (ErrCode: {response['retCode']})")

                trades = response['result']['list']
                all_trades.extend(trades)
                cursor = response['result'].get('nextPageCursor')
                if not cursor: break
                time.sleep(0.2)
            except Exception as e:
                logging.error(f"Exceção ao buscar trades: {e}")
                raise e
        current_start = current_end + timedelta(days=1)

    return pd.DataFrame(all_trades) if all_trades else pd.DataFrame()
