import os
import csv
import getpass
from datetime import datetime, timedelta, timezone
import time
from pybit.unified_trading import HTTP

def get_credentials():
    """Solicita as credenciais da API de forma segura."""
    print("--- Configuração das Credenciais da Bybit ---")
    api_key = getpass.getpass("Digite sua API Key: ")
    api_secret = getpass.getpass("Digite seu API Secret: ")
    return api_key, api_secret

def get_date_range():
    """Solicita o período de coleta de dados."""
    print("\n--- Definição do Período de Coleta ---")
    while True:
        try:
            start_str = input("Digite a data de início (DD-MM-AAAA): ")
            end_str = input("Digite a data de fim (DD-MM-AAAA): ")
            
            start_date = datetime.strptime(start_str, "%d-%m-%Y")
            end_date = datetime.strptime(end_str, "%d-%m-%Y").replace(hour=23, minute=59, second=59)
            
            # Converte para timestamp em milissegundos UTC
            start_timestamp = int(start_date.replace(tzinfo=timezone.utc).timestamp() * 1000)
            end_timestamp = int(end_date.replace(tzinfo=timezone.utc).timestamp() * 1000)
            
            if start_timestamp > end_timestamp:
                print("Erro: A data de início não pode ser posterior à data de fim. Tente novamente.")
                continue
            
            return start_timestamp, end_timestamp
        except ValueError:
            print("Formato de data inválido. Use o formato DD-MM-AAAA. Tente novamente.")

def fetch_all_trades(session, category, start_time, end_time):
    """Busca todos os trades em um período, lidando com paginação e limites de tempo."""
    all_trades = []
    
    current_start = start_time
    
    print(f"\nIniciando a coleta de trades para a categoria '{category}'...")

    while current_start < end_time:
        # A API da Bybit permite um intervalo máximo de 7 dias por requisição
        current_end = min(current_start + timedelta(days=7).total_seconds() * 1000, end_time)
        
        start_dt = datetime.fromtimestamp(current_start / 1000, tz=timezone.utc)
        end_dt = datetime.fromtimestamp(current_end / 1000, tz=timezone.utc)
        print(f"Buscando dados de {start_dt.strftime('%d-%m-%Y')} a {end_dt.strftime('%d-%m-%Y')}...")

        cursor = ""
        while True:
            try:
                response = session.get_executions(
                    category=category,
                    startTime=int(current_start),
                    endTime=int(current_end),
                    limit=100, # Máximo permitido pela API
                    cursor=cursor,
                )
                
                if response['retCode'] == 0:
                    trades = response['result']['list']
                    if not trades:
                        # Nenhuma trade encontrada nesta página, encerra o loop interno
                        break
                    
                    all_trades.extend(trades)
                    
                    cursor = response['result'].get('nextPageCursor', "")
                    if not cursor:
                        # Não há mais páginas, encerra o loop interno
                        break
                    
                    # Pausa para evitar atingir os limites de requisição da API
                    time.sleep(0.2) # 200ms de pausa
                
                else:
                    print(f"Erro na API: {response['retMsg']}")
                    break

            except Exception as e:
                print(f"Ocorreu uma exceção ao chamar a API: {e}")
                time.sleep(5) # Pausa maior em caso de erro de conexão
                continue
        
        # Avança para o próximo intervalo de 7 dias
        current_start = current_end

    print(f"Coleta finalizada. Total de {len(all_trades)} trades encontrados para a categoria '{category}'.")
    return all_trades

def save_to_csv(trades, filename="bybit_trades.csv"):
    """Salva a lista de trades em um arquivo CSV."""
    if not trades:
        print("Nenhum trade para salvar.")
        return

    # Pega as chaves do primeiro trade para usar como cabeçalho
    headers = trades[0].keys()
    
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()
            writer.writerows(trades)
        print(f"\nDados salvos com sucesso no arquivo '{filename}'!")
    except IOError as e:
        print(f"Erro ao salvar o arquivo CSV: {e}")

if __name__ == "__main__":
    api_key, api_secret = get_credentials()
    start_ts, end_ts = get_date_range()

    try:
        session = HTTP(
            api_key=api_key,
            api_secret=api_secret,
        )
    except Exception as e:
        print(f"Falha ao iniciar a sessão com a Bybit: {e}")
        exit()

    # Coleta trades de futuros (Perpétuos USDT/USDC)
    linear_trades = fetch_all_trades(session, "linear", start_ts, end_ts)
    
    # Você pode adicionar outras categorias se precisar, por exemplo:
    # inverse_trades = fetch_all_trades(session, "inverse", start_ts, end_ts)
    # spot_trades = fetch_all_trades(session, "spot", start_ts, end_ts)
    # all_trades = linear_trades + inverse_trades + spot_trades
    
    all_trades = linear_trades

    if all_trades:
        # Ordena os trades por data de execução para melhor visualização no CSV
        all_trades.sort(key=lambda x: int(x.get('execTime', 0)))
        save_to_csv(all_trades)
    else:
        print("\nNenhum trade foi encontrado no período e categoria especificados.")

