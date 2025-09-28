import pandas as pd
import numpy as np

def get_exit_type(row):
    """
    Determina o tipo de saída de forma mais precisa, priorizando a coluna stopOrderType.
    """
    stop_order_type = str(row.get('stopOrderType', ''))
    order_link_id = str(row.get('orderLinkId', ''))

    if 'StopLoss' in stop_order_type or 'StopLoss' in order_link_id:
        return 'StopLoss'
    if 'TakeProfit' in stop_order_type or 'TakeProfit' in order_link_id:
        return 'TakeProfit'
    if 'TrailingStop' in stop_order_type or 'TrailingStop' in order_link_id:
        return 'TrailingStop'
    
    return 'Parcial'


def process_trades_data(raw_df, leverage, account_balance=None, transactions_df=None):
    df = raw_df.copy()
    
    # Corrigir conversão de timestamp
    df['execTime'] = pd.to_numeric(df['execTime'], errors='coerce')
    df['execTime'] = pd.to_datetime(df['execTime'], unit='ms')
    df = df.sort_values(by='execTime').reset_index(drop=True)
    
    numeric_cols = ['execFee', 'execQty', 'execPrice', 'orderQty', 'orderPrice']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=numeric_cols)

    trades = []
    open_positions = {}

    for index, row in df.iterrows():
        symbol = row['symbol']
        side = row['side']
        qty = row['execQty']
        price = row['execPrice']
        fee = row['execFee']
        exec_time = row['execTime']

        if symbol not in open_positions:
            open_positions[symbol] = {'qty': 0, 'cost': 0, 'entry_time': None, 'entry_price': 0, 'entry_fee': 0}

        is_new_position = open_positions[symbol]['qty'] == 0
        
        if is_new_position:
            open_positions[symbol] = {
                'qty': qty if side == 'Buy' else -qty,
                'cost': qty * price,
                'entry_time': exec_time,
                'entry_price': price,
                'entry_fee': fee
            }
        else:
            current_qty = open_positions[symbol]['qty']
            is_closing_long = side == 'Sell' and current_qty > 0
            is_closing_short = side == 'Buy' and current_qty < 0

            if is_closing_long or is_closing_short:
                entry_qty = open_positions[symbol]['qty']
                avg_entry_price = open_positions[symbol]['entry_price']
                
                pnl = (price - avg_entry_price) * entry_qty if is_closing_long else (avg_entry_price - price) * abs(entry_qty)
                pnl_net = pnl - open_positions[symbol]['entry_fee'] - fee
                
                valor_nocional = abs(entry_qty * avg_entry_price)
                margem = valor_nocional / leverage if leverage > 0 else valor_nocional
                
                roi = (pnl_net / margem) * 100 if margem > 0 else 0

                exit_type = get_exit_type(row)

                trades.append({
                    'symbol': symbol, 'position_side': 'Long' if entry_qty > 0 else 'Short',
                    'entry_time': open_positions[symbol]['entry_time'], 'exit_time': exec_time,
                    'duration': exec_time - open_positions[symbol]['entry_time'],
                    'quantity': abs(entry_qty), 'avg_entry_price': avg_entry_price,
                    'exit_price': price, 'valor_nocional': valor_nocional,
                    'margem': margem, 'pnl_net': pnl_net, 'roi': roi,
                    'result': 'Lucro' if pnl_net > 0 else 'Perda', 'exit_type': exit_type
                })
                open_positions.pop(symbol, None)

    analysis_df = pd.DataFrame(trades)
    if not trades:
        analysis_df = pd.DataFrame(columns=['pnl_net', 'result', 'roi', 'symbol', 'exit_type', 'margem'])
    else:
        analysis_df['duration'] = analysis_df['duration'].astype(str).str.replace('0 days ', '')

    pnl_de_trades = analysis_df['pnl_net'].sum()
    total_trades = len(analysis_df)
    winning_trades = analysis_df[analysis_df['pnl_net'] > 0]
    win_rate = (len(winning_trades) / total_trades) * 100 if total_trades > 0 else 0
    total_margin_cost = analysis_df['margem'].sum()
    
    kpis = {
        'total_pnl': pnl_de_trades, 
        'win_rate': win_rate,
        'total_margin_cost': total_margin_cost,
        'total_trades': total_trades
    }

    if not analysis_df.empty:
        symbol_summary = analysis_df.groupby('symbol').agg(
            total_pnl_net=('pnl_net', 'sum'),
            total_margin=('margem', 'sum'),
            win_rate=('result', lambda x: (x == 'Lucro').sum() / x.count() * 100),
            trade_count=('symbol', 'count')
        ).reset_index()
        symbol_summary['roi_agregado'] = (symbol_summary['total_pnl_net'] / symbol_summary['total_margin']) * 100
        
        kpis['avg_roi'] = (analysis_df['pnl_net'].sum() / analysis_df['margem'].sum()) * 100 if analysis_df['margem'].sum() > 0 else 0

        winners_summary = symbol_summary[symbol_summary['total_pnl_net'] >= 0].sort_values(by='total_pnl_net', ascending=False)
        losers_summary = symbol_summary[symbol_summary['total_pnl_net'] < 0].sort_values(by='total_pnl_net', ascending=True)

        exit_type_summary = analysis_df.groupby('exit_type').agg(
            total_pnl_net=('pnl_net', 'sum'),
            total_margin=('margem', 'sum'),
            win_rate=('result', lambda x: (x == 'Lucro').sum() / x.count() * 100),
            exit_count=('exit_type', 'count')
        ).reset_index()
        exit_type_summary['roi_agregado'] = (exit_type_summary['total_pnl_net'] / exit_type_summary['total_margin']) * 100
        exit_type_summary = exit_type_summary.sort_values(by='total_pnl_net', ascending=False)
    else:
        kpis['avg_roi'] = 0
        winners_summary = pd.DataFrame()
        losers_summary = pd.DataFrame()
        exit_type_summary = pd.DataFrame()

    # Processar informações da conta
    account_info = {}
    if account_balance:
        account_info = {
            'balances': account_balance,
            'total_balance_usdt': account_balance.get('USDT', {}).get('wallet_balance', 0),
            'total_unrealized_pnl': sum([
                balance.get('unrealized_pnl', 0) for coin, balance in account_balance.items()
            ])
        }
    
    # Processar transações com transferências
    transactions_summary = {}
    if transactions_df is not None and not transactions_df.empty:
        # Separar por tipo
        deposits = transactions_df[transactions_df['type'] == 'Depósito']
        withdrawals = transactions_df[transactions_df['type'] == 'Retirada']
        transfers_in = transactions_df[transactions_df['type'] == 'Transferência Entrada']
        transfers_out = transactions_df[transactions_df['type'] == 'Transferência Saída']
        
        transactions_summary = {
            'total_deposits': deposits['amount'].sum() if not deposits.empty else 0,
            'total_withdrawals': withdrawals['amount'].sum() if not withdrawals.empty else 0,
            'total_transfers_in': transfers_in['amount'].sum() if not transfers_in.empty else 0,
            'total_transfers_out': transfers_out['amount'].sum() if not transfers_out.empty else 0,
            'deposits_count': len(deposits),
            'withdrawals_count': len(withdrawals),
            'transfers_in_count': len(transfers_in),
            'transfers_out_count': len(transfers_out),
            'net_flow': (
                (deposits['amount'].sum() if not deposits.empty else 0) +
                (transfers_in['amount'].sum() if not transfers_in.empty else 0) -
                (withdrawals['amount'].sum() if not withdrawals.empty else 0) -
                (transfers_out['amount'].sum() if not transfers_out.empty else 0)
            ),
            'transactions_detail': transactions_df.to_dict('records') if not transactions_df.empty else []
        }

    return {
        'kpis': kpis,
        'winners_summary': winners_summary.to_dict('records') if not winners_summary.empty else [],
        'losers_summary': losers_summary.to_dict('records') if not losers_summary.empty else [],
        'exit_type_summary': exit_type_summary.to_dict('records') if not exit_type_summary.empty else [],
        'all_trades': analysis_df.to_dict('records'),
        'raw_df': raw_df,
        'account_info': account_info,
        'transactions_summary': transactions_summary
    }
