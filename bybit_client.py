import pandas as pd
from datetime import datetime, timedelta
from pybit.unified_trading import HTTP
import time
import logging

def fetch_closed_positions(api_key, api_secret, start_date_str, end_date_str):
    """
    Busca posições fechadas (trades completos) usando a API específica da Bybit.
    Esta API retorna trades já processados e agrupados pela própria Bybit.
    """
    session = HTTP(
        testnet=False,
        api_key=api_key,
        api_secret=api_secret,
    )
    
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    
    all_positions = []
    current_start = start_date
    
    # Processar em chunks de 7 dias (limitação da API)
    while current_start <= end_date:
        current_end = min(current_start + timedelta(days=6), end_date)
        start_timestamp = int(current_start.timestamp() * 1000)
        end_timestamp = int((current_end + timedelta(days=1) - timedelta(seconds=1)).timestamp() * 1000)

        logging.info(f"Buscando posições fechadas de {current_start.strftime('%Y-%m-%d')} a {current_end.strftime('%Y-%m-%d')}...")
        print(f"DEBUG: Buscando posições fechadas - {current_start.strftime('%Y-%m-%d')} a {current_end.strftime('%Y-%m-%d')}")
        
        cursor = ""
        while True:
            try:
                response = session.get_closed_pnl(
                    category="linear",
                    startTime=start_timestamp,
                    endTime=end_timestamp,
                    limit=100,
                    cursor=cursor
                )
                
                if response['retCode'] != 0:
                    raise Exception(f"Erro da API Bybit (Posições): {response['retMsg']}")
                
                positions = response['result']['list']
                print(f"DEBUG: Encontradas {len(positions)} posições neste chunk")
                
                for position in positions:
                    print(f"DEBUG: Posição {position['symbol']} - PnL: {position.get('closedPnl', 0)}")
                
                all_positions.extend(positions)
                
                cursor = response['result'].get('nextPageCursor')
                if not cursor:
                    break
                    
                time.sleep(0.2)  # Rate limiting
                
            except Exception as e:
                logging.error(f"Erro ao buscar posições fechadas: {e}")
                print(f"DEBUG: Erro no chunk: {e}")
                break
        
        current_start = current_end + timedelta(days=1)
        time.sleep(0.5)
    
    print(f"DEBUG: Total de posições fechadas coletadas: {len(all_positions)}")
    return pd.DataFrame(all_positions) if all_positions else pd.DataFrame()

def fetch_account_balance(api_key, api_secret):
    """
    Busca o saldo atual da conta UTA.
    """
    try:
        session = HTTP(
            testnet=False,
            api_key=api_key,
            api_secret=api_secret,
        )
        
        response = session.get_wallet_balance(accountType="UNIFIED")
        
        if response['retCode'] != 0:
            raise Exception(f"Erro da API: {response['retMsg']}")
        
        balances = {}
        for account in response['result']['list']:
            for coin in account['coin']:
                coin_name = coin['coin']
                balances[coin_name] = {
                    'wallet_balance': float(coin.get('walletBalance', 0)) if coin.get('walletBalance') else 0,
                    'available_balance': float(coin.get('availableToWithdraw', 0)) if coin.get('availableToWithdraw') else 0,
                    'unrealized_pnl': float(coin.get('unrealisedPnl', 0)) if coin.get('unrealisedPnl') else 0
                }
        
        return balances
        
    except Exception as e:
        logging.error(f"Erro ao buscar saldo da conta: {e}")
        return {}

def fetch_account_transactions(api_key, api_secret, start_date_str, end_date_str):
    """
    Busca movimentações da conta (depósitos, retiradas).
    Nota: Transferências internas não estão disponíveis na API pública.
    """
    try:
        session = HTTP(
            testnet=False,
            api_key=api_key,
            api_secret=api_secret,
        )
        
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        
        all_transactions = []
        current_start = start_date
        
        # Processar em chunks de 7 dias
        while current_start <= end_date:
            current_end = min(current_start + timedelta(days=6), end_date)
            start_timestamp = int(current_start.timestamp() * 1000)
            end_timestamp = int((current_end + timedelta(days=1) - timedelta(seconds=1)).timestamp() * 1000)
            
            print(f"DEBUG: Buscando transações de {current_start.strftime('%Y-%m-%d')} a {current_end.strftime('%Y-%m-%d')}")
            
            # Buscar depósitos
            try:
                cursor = ""
                while True:
                    response = session.get_deposit_records(
                        startTime=start_timestamp,
                        endTime=end_timestamp,
                        limit=50,
                        cursor=cursor
                    )
                    
                    if response['retCode'] == 0:
                        deposits = response['result']['rows']
                        for deposit in deposits:
                            all_transactions.append({
                                'type': 'Depósito',
                                'coin': deposit.get('coin', ''),
                                'amount': float(deposit.get('amount', 0)) if deposit.get('amount') else 0,
                                'status': deposit.get('status', ''),
                                'timestamp': deposit.get('successAt', deposit.get('createdTime', '')),
                                'tx_id': deposit.get('txID', ''),
                                'address': deposit.get('toAddress', '')
                            })
                        
                        cursor = response['result'].get('nextPageCursor')
                        if not cursor:
                            break
                        time.sleep(0.2)
                    else:
                        print(f"DEBUG: Erro ao buscar depósitos: {response['retMsg']}")
                        break
                        
            except Exception as e:
                print(f"DEBUG: Erro no chunk de depósitos: {e}")
            
            # Buscar retiradas
            try:
                cursor = ""
                while True:
                    response = session.get_withdrawal_records(
                        startTime=start_timestamp,
                        endTime=end_timestamp,
                        limit=50,
                        cursor=cursor
                    )
                    
                    if response['retCode'] == 0:
                        withdrawals = response['result']['rows']
                        for withdrawal in withdrawals:
                            all_transactions.append({
                                'type': 'Retirada',
                                'coin': withdrawal.get('coin', ''),
                                'amount': float(withdrawal.get('amount', 0)) if withdrawal.get('amount') else 0,
                                'status': withdrawal.get('status', ''),
                                'timestamp': withdrawal.get('updateTime', withdrawal.get('createTime', '')),
                                'tx_id': withdrawal.get('txID', ''),
                                'address': withdrawal.get('toAddress', '')
                            })
                        
                        cursor = response['result'].get('nextPageCursor')
                        if not cursor:
                            break
                        time.sleep(0.2)
                    else:
                        print(f"DEBUG: Erro ao buscar retiradas: {response['retMsg']}")
                        break
                        
            except Exception as e:
                print(f"DEBUG: Erro no chunk de retiradas: {e}")
            
            current_start = current_end + timedelta(days=1)
            time.sleep(0.5)

        print(f"DEBUG: Total de transações encontradas: {len(all_transactions)}")
        for transaction in all_transactions:
            print(f"DEBUG: {transaction}")
        
        return pd.DataFrame(all_transactions) if all_transactions else pd.DataFrame()
        
    except Exception as e:
        logging.error(f"Erro ao buscar movimentações da conta: {e}")
        print(f"DEBUG: Erro geral: {e}")
        return pd.DataFrame()

# Manter função antiga para compatibilidade (caso seja necessária)
def fetch_all_trades(api_key, api_secret, start_date_str, end_date_str):
    """
    DEPRECATED: Usar fetch_closed_positions() em vez desta função.
    Mantida apenas para compatibilidade.
    """
    print("AVISO: Usando fetch_closed_positions() em vez de fetch_all_trades()")
    return fetch_closed_positions(api_key, api_secret, start_date_str, end_date_str)

# Aliases para compatibilidade
def get_account_balance(api_key, api_secret):
    return fetch_account_balance(api_key, api_secret)

def get_account_transactions(api_key, api_secret, start_date_str, end_date_str):
    return fetch_account_transactions(api_key, api_secret, start_date_str, end_date_str)
