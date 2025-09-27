import pandas as pd
import numpy as np

def process_trades_data(raw_df, leverage):
    """
    Processa o DataFrame bruto de trades, calcula PnL, ROI, e prepara os resumos.
    """
    # 1. Limpeza e preparação inicial dos dados
    df = raw_df.copy()
    df['execTime'] = pd.to_datetime(df['execTime'], unit='ms')
    df = df.sort_values(by='execTime').reset_index(drop=True)
    
    numeric_cols = ['execFee', 'execQty', 'execPrice', 'orderQty', 'orderPrice']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=numeric_cols)

    # 2. Identificar trades de abertura e fechamento
    trades = []
    open_positions = {}

    for _, row in df.iterrows():
        symbol = row['symbol']
        side = row['side']
        qty = row['execQty']
        price = row['execPrice']
        fee = row['execFee']
        exec_time = row['execTime']
        order_link_id = row['orderLinkId']

        position_key = (symbol, 'Long' if side == 'Buy' else 'Short')
        
        if symbol not in open_positions:
            open_positions[symbol] = {'qty': 0, 'cost': 0, 'entry_time': None, 'entry_price': 0}

        if open_positions[symbol]['qty'] == 0: # Abertura de uma nova posição
            open_positions[symbol]['qty'] = qty
            open_positions[symbol]['cost'] = qty * price
            open_positions[symbol]['entry_time'] = exec_time
            open_positions[symbol]['entry_price'] = price
            open_positions[symbol]['entry_fee'] = fee
        else: # Fechamento de uma posição existente
            if (side == 'Sell' and open_positions[symbol]['qty'] > 0) or \
               (side == 'Buy' and open_positions[symbol]['qty'] < 0):
                
                entry_qty = open_positions[symbol]['qty']
                avg_entry_price = open_positions[symbol]['entry_price']
                
                pnl = (price - avg_entry_price) * entry_qty if side == 'Sell' else (avg_entry_price - price) * abs(entry_qty)
                pnl_net = pnl - open_positions[symbol]['entry_fee'] - fee
                
                valor_nocional = abs(entry_qty * avg_entry_price)
                margem = valor_nocional / leverage if leverage > 0 else valor_nocional
                
                roi = (pnl_net / margem) * 100 if margem > 0 else 0

                exit_type = "StopLoss" if "StopLoss" in str(order_link_id) else \
                            "TakeProfit" if "TakeProfit" in str(order_link_id) else \
                            "TrailingStop" if "TrailingStop" in str(order_link_id) else \
                            "Parcial"

                trades.append({
                    'symbol': symbol,
                    'position_side': 'Long' if entry_qty > 0 else 'Short',
                    'entry_time': open_positions[symbol]['entry_time'],
                    'exit_time': exec_time,
                    'duration': exec_time - open_positions[symbol]['entry_time'],
                    'quantity': abs(entry_qty),
                    'avg_entry_price': avg_entry_price,
                    'exit_price': price,
                    'valor_nocional': valor_nocional,
                    'margem': margem,
                    'pnl_net': pnl_net,
                    'roi': roi,
                    'result': 'Lucro' if pnl_net > 0 else 'Perda',
                    'exit_type': exit_type
                })
                open_positions.pop(symbol, None) # Limpa a posição

    if not trades:
        return {
            'kpis': {'total_pnl': 0, 'win_rate': 0, 'avg_roi': 0},
            'winners_summary': pd.DataFrame(),
            'losers_summary': pd.DataFrame(),
            'exit_type_summary': pd.DataFrame(),
            'all_trades': [],
            'raw_df': raw_df
        }

    # 3. Criar DataFrames para análise
    analysis_df = pd.DataFrame(trades)
    analysis_df['duration'] = analysis_df['duration'].astype(str).str.replace('0 days ', '')

    # 4. Calcular KPIs
    total_pnl = analysis_df['pnl_net'].sum()
    total_trades = len(analysis_df)
    winning_trades = analysis_df[analysis_df['pnl_net'] > 0]
    win_rate = (len(winning_trades) / total_trades) * 100 if total_trades > 0 else 0
    avg_roi = analysis_df['roi'].mean()
    kpis = {'total_pnl': total_pnl, 'win_rate': win_rate, 'avg_roi': avg_roi}

    # 5. Criar resumos por símbolo
    symbol_summary = analysis_df.groupby('symbol').agg(
        total_pnl_net=('pnl_net', 'sum'),
        average_roi=('roi', 'mean'),
        win_rate=('result', lambda x: (x == 'Lucro').sum() / x.count() * 100),
        trade_count=('symbol', 'count')
    ).reset_index()

    winners_summary = symbol_summary[symbol_summary['total_pnl_net'] >= 0].sort_values(by='total_pnl_net', ascending=False)
    losers_summary = symbol_summary[symbol_summary['total_pnl_net'] < 0].sort_values(by='total_pnl_net', ascending=True)

    # 6. Criar resumo por tipo de saída
    exit_type_summary = analysis_df.groupby('exit_type').agg(
        total_pnl_net=('pnl_net', 'sum'),
        average_roi=('roi', 'mean'),
        win_rate=('result', lambda x: (x == 'Lucro').sum() / x.count() * 100),
        exit_count=('exit_type', 'count')
    ).reset_index().sort_values(by='total_pnl_net', ascending=False)

    return {
        'kpis': kpis,
        'winners_summary': winners_summary.to_dict('records'),
        'losers_summary': losers_summary.to_dict('records'),
        'exit_type_summary': exit_type_summary.to_dict('records'),
        'all_trades': analysis_df.to_dict('records'),
        'raw_df': raw_df
    }
