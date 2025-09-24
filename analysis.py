import pandas as pd
from collections import defaultdict
import logging

def analyze_data(df):
    """Processa o DataFrame de execuções e calcula PnL/ROI."""
    if df.empty:
        return pd.DataFrame()
        
    trades_df = df[df['execType'] == 'Trade'].copy()
    if trades_df.empty: 
        return pd.DataFrame()
    
    numeric_cols = ['execQty', 'execPrice', 'execValue', 'execFee']
    for col in numeric_cols:
        trades_df[col] = pd.to_numeric(trades_df[col], errors='coerce')
    trades_df.dropna(subset=numeric_cols, inplace=True)
    
    trades_df['execTime'] = pd.to_numeric(trades_df['execTime'], errors='coerce')
    trades_df.dropna(subset=['execTime'], inplace=True)
    trades_df['execTime'] = pd.to_datetime(trades_df['execTime'], unit='ms')
    
    trades_df = trades_df.sort_values(by='execTime').reset_index(drop=True)

    open_positions = defaultdict(lambda: {'qty': 0.0, 'cost': 0.0, 'fees': 0.0, 'entry_time': None})
    closed_trades = []

    for _, row in trades_df.iterrows():
        try:
            symbol, side, qty, price, fee = row['symbol'], row['side'], row['execQty'], row['execPrice'], row['execFee']
            position = open_positions[symbol]
            signed_qty = qty if side == 'Buy' else -qty
            
            is_closing = (position['qty'] > 0 and side == 'Sell') or \
                         (position['qty'] < 0 and side == 'Buy')
            
            if not is_closing:
                if position['qty'] == 0: position['entry_time'] = row['execTime']
                position['cost'] += signed_qty * price
                position['qty'] += signed_qty
                position['fees'] += fee
            else:
                close_qty = min(abs(position['qty']), qty)
                if close_qty == 0: continue
                
                avg_entry_price = position['cost'] / position['qty']
                entry_cost_closed = abs(avg_entry_price * close_qty)
                
                pnl_gross = (price - abs(avg_entry_price)) * close_qty if position['qty'] > 0 else (abs(avg_entry_price) - price) * close_qty
                
                entry_fees_closed = (position['fees'] / abs(position['qty'])) * close_qty if abs(position['qty']) > 0 else 0
                pnl_net = pnl_gross - (entry_fees_closed + fee)
                roi = (pnl_net / entry_cost_closed) * 100 if entry_cost_closed > 0 else 0
                
                exit_type = row.get('stopOrderType')
                if pd.isna(exit_type) or exit_type in ['UNKNOWN', '']:
                    exit_type = row.get('createType', 'Manual')

                closed_trades.append({
                    'symbol': symbol, 'position_side': 'Long' if position['qty'] > 0 else 'Short',
                    'entry_time': position['entry_time'], 'exit_time': row['execTime'], 'quantity': close_qty,
                    'avg_entry_price': abs(avg_entry_price), 'exit_price': price, 'pnl_net': pnl_net, 'roi_%': roi,
                    'exit_type': exit_type
                })
                
                position['qty'] += signed_qty
                position['cost'] = position['qty'] * avg_entry_price
                position['fees'] -= entry_fees_closed
                
                if abs(position['qty']) < 1e-9:
                    open_positions.pop(symbol, None)

        except (ZeroDivisionError, TypeError, KeyError) as e:
            logging.error(f"Erro ao processar trade para o símbolo {row.get('symbol', 'N/A')}: {e}")
            continue
            
    return pd.DataFrame(closed_trades)
