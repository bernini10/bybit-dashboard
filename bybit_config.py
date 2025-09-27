# bybit_config.py
import logging

def set_collateral_status(session, symbol, status):
    """
    Ativa ou desativa uma moeda como colateral na Bybit.
    :param session: A sessão da pybit.
    :param symbol: A moeda a ser modificada (ex: 'BTC', 'ETH').
    :param status: 'ON' para ativar, 'OFF' para desativar.
    :return: (success, message)
    """
    coin = symbol.replace('USDT', '') # Extrai a moeda base, ex: 'BTCUSDT' -> 'BTC'
    
    try:
        logging.info(f"Tentando alterar o status de colateral para {coin} para {status}...")
        
        # --- A CORREÇÃO ESTÁ AQUI ---
        # O nome correto do parâmetro é 'collateral_switch', com underscore.
        response = session.set_collateral_coin(coin=coin, collateral_switch=status)
        
        logging.info(f"Resposta da Bybit para set_collateral_status: {response}")

        if response.get('retCode') == 0:
            msg = f"Sucesso! Bybit confirmou: {coin} foi configurado como colateral '{status}'."
            logging.info(msg)
            return True, msg
        else:
            error_msg = response.get('retMsg', 'Erro desconhecido da Bybit.')
            error_code = response.get('retCode', 'N/A')
            msg = f"Falha ao alterar colateral para {coin}. Bybit: '{error_msg}' (Código: {error_code})"
            logging.error(msg)
            return False, msg

    except Exception as e:
        logging.error(f"Exceção ao chamar set_collateral_coin para {coin}: {e}")
        return False, f"Erro de conexão ou da biblioteca ao tentar alterar o status de {coin}."

def get_collateral_info(session):
    """
    Busca a lista de todas as moedas e seu status de colateral.
    :param session: A sessão da pybit.
    :return: Dicionário com {moeda: status}, ex: {'BTC': 'ON', 'ETH': 'OFF'}
    """
    try:
        logging.info("Buscando informações de colateral da conta...")
        response = session.get_collateral_info(currency=None)
        
        logging.info(f"Resposta da Bybit para get_collateral_info: {response}")

        if response.get('retCode') == 0 and response.get('result', {}).get('list'):
            collateral_status = {
                item['currency']: item['collateralSwitch']
                for item in response['result']['list']
            }
            logging.info(f"Status de colateral encontrado: {collateral_status}")
            return collateral_status, None
        else:
            error_msg = response.get('retMsg', 'Não foi possível buscar a lista de colateral.')
            return {}, error_msg

    except Exception as e:
        logging.error(f"Exceção ao chamar get_collateral_info: {e}")
        return {}, f"Erro de conexão ao buscar informações de colateral."
