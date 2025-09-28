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

def get_account_balance(api_key, api_secret):
    """
    Busca o saldo atual da conta UTA (Unified Trading Account).
    """
    session = HTTP(
        testnet=False,
        api_key=api_key,
        api_secret=api_secret,
    )
    
    try:
        response = session.get_wallet_balance(accountType="UNIFIED")
        if response['retCode'] != 0:
            raise Exception(f"Erro da API Bybit (Saldo): {response['retMsg']} (ErrCode: {response['retCode']})")
        
        # Extrair informações do saldo
        account_info = response['result']['list'][0] if response['result']['list'] else {}
        coins = account_info.get('coin', [])
        
        balance_data = {}
        for coin in coins:
            # Função auxiliar para converter valores com segurança
            def safe_float(value, default=0.0):
                try:
                    return float(value) if value and str(value).strip() != '' else default
                except (ValueError, TypeError):
                    return default
            
            wallet_balance = safe_float(coin.get('walletBalance', 0))
            if wallet_balance > 0:
                balance_data[coin['coin']] = {
                    'wallet_balance': wallet_balance,
                    'available_balance': safe_float(coin.get('availableToWithdraw', 0)),
                    'used_margin': safe_float(coin.get('totalPositionMM', 0)),
                    'unrealized_pnl': safe_float(coin.get('totalUnrealisedPnl', 0))
                }
        
        return balance_data
    except Exception as e:
        logging.error(f"Erro ao buscar saldo da conta: {e}")
        raise e

def get_account_transactions(api_key, api_secret, start_date_str, end_date_str):
    """
    Busca as movimentações de depósito/retirada/transferência da conta no período especificado.
    CORRIGIDO: Divide o período em chunks de 7 dias para respeitar limitação da API.
    """
    session = HTTP(
        testnet=False,
        api_key=api_key,
        api_secret=api_secret,
    )
    
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    
    print(f"DEBUG: Buscando transações de {start_date_str} a {end_date_str}")
    
    all_transactions = []
    
    # Dividir o período em chunks de 7 dias
    current_start = start_date
    while current_start <= end_date:
        current_end = min(current_start + timedelta(days=6), end_date)
        start_timestamp = int(current_start.timestamp() * 1000)
        end_timestamp = int((current_end + timedelta(days=1) - timedelta(seconds=1)).timestamp() * 1000)
        
        print(f"DEBUG: Processando chunk {current_start.strftime('%Y-%m-%d')} a {current_end.strftime('%Y-%m-%d')}")
        print(f"DEBUG: Timestamps {start_timestamp} a {end_timestamp}")
        
        try:
            # Buscar depósitos para este chunk
            logging.info(f"Buscando depósitos de {current_start.strftime('%Y-%m-%d')} a {current_end.strftime('%Y-%m-%d')}...")
            cursor = ""
            while True:
                try:
                    response = session.get_deposit_records(
                        limit=50, 
                        cursor=cursor,
                        startTime=start_timestamp,
                        endTime=end_timestamp
                    )
                    if response['retCode'] != 0:
                        print(f"DEBUG: Erro ao buscar depósitos: {response['retMsg']}")
                        break
                    
                    deposits = response['result']['rows']
                    print(f"DEBUG: Encontrados {len(deposits)} depósitos neste chunk")
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
                except Exception as e:
                    print(f"DEBUG: Exceção ao buscar depósitos: {e}")
                    break
            
            # Buscar retiradas para este chunk
            logging.info(f"Buscando retiradas de {current_start.strftime('%Y-%m-%d')} a {current_end.strftime('%Y-%m-%d')}...")
            cursor = ""
            while True:
                try:
                    response = session.get_withdrawal_records(
                        limit=50,
                        cursor=cursor,
                        startTime=start_timestamp,
                        endTime=end_timestamp
                    )
                    if response['retCode'] != 0:
                        print(f"DEBUG: Erro ao buscar retiradas: {response['retMsg']}")
                        break
                    
                    withdrawals = response['result']['rows']
                    print(f"DEBUG: Encontradas {len(withdrawals)} retiradas neste chunk")
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
                except Exception as e:
                    print(f"DEBUG: Exceção ao buscar retiradas: {e}")
                    break

            # Buscar transferências internas para este chunk
            logging.info(f"Buscando transferências de {current_start.strftime('%Y-%m-%d')} a {current_end.strftime('%Y-%m-%d')}...")
            cursor = ""
            while True:
                try:
                    response = session.get_internal_transfer_records(
                        limit=50,
                        cursor=cursor,
                        startTime=start_timestamp,
                        endTime=end_timestamp
                    )
                    if response['retCode'] != 0:
                        print(f"DEBUG: Erro ao buscar transferências: {response['retMsg']}")
                        break
                    
                    transfers = response['result']['list']
                    print(f"DEBUG: Encontradas {len(transfers)} transferências neste chunk")
                    for transfer in transfers:
                        print(f"DEBUG: Transferência: {transfer}")
                        # Determinar se é entrada ou saída baseado no tipo de conta
                        from_account = transfer.get('fromAccountType', '')
                        to_account = transfer.get('toAccountType', '')
                        
                        if from_account == 'UNIFIED':
                            transfer_type = 'Transferência Saída'
                        elif to_account == 'UNIFIED':
                            transfer_type = 'Transferência Entrada'
                        else:
                            transfer_type = 'Transferência'
                        
                        amount = float(transfer.get('amount', 0)) if transfer.get('amount') else 0
                        
                        all_transactions.append({
                            'type': transfer_type,
                            'coin': transfer.get('coin', ''),
                            'amount': amount,
                            'status': transfer.get('status', ''),
                            'timestamp': transfer.get('timestamp', ''),
                            'tx_id': transfer.get('transferId', ''),
                            'from_account': from_account,
                            'to_account': to_account
                        })
                    
                    cursor = response['result'].get('nextPageCursor')
                    if not cursor:
                        break
                    time.sleep(0.2)
                except Exception as e:
                    print(f"DEBUG: Exceção ao buscar transferências: {e}")
                    break

        except Exception as e:
            print(f"DEBUG: Erro no chunk {current_start.strftime('%Y-%m-%d')} a {current_end.strftime('%Y-%m-%d')}: {e}")
        
        # Avançar para o próximo chunk
        current_start = current_end + timedelta(days=1)
        time.sleep(0.5)  # Pausa entre chunks para evitar rate limiting

    print(f"DEBUG: Total de transações encontradas: {len(all_transactions)}")
    for transaction in all_transactions:
        print(f"DEBUG: {transaction}")
    
    return pd.DataFrame(all_transactions) if all_transactions else pd.DataFrame()
