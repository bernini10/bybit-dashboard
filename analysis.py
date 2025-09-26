import pandas as pd

def analyze_data(raw_data_df):
    """
    Analisa os dados brutos de trades, identifica operações completas (compra/venda)
    e calcula o PnL e ROI para cada uma.
    """
    if raw_data_df.empty:
        return pd.DataFrame()

    # Converte tipos de dados para garantir cálculos corretos
    numeric_cols = ['execPrice', 'execQty', 'execFee']
    for col in numeric_cols:
        raw_data_df[col] = pd.to_numeric(raw_data_df[col], errors='coerce')
    
    raw_data_df['execTime'] = pd.to_datetime(raw_data_df['execTime'], unit='ms')
    raw_data_df.dropna(subset=numeric_cols, inplace=True)

    # Ordena por símbolo e tempo para processar na ordem correta
    raw_data_df.sort_values(by=['symbol', 'execTime'], inplace=True)

    closed_trades = []
    open_positions = {}

    for _, row in raw_data_df.iterrows():
        symbol = row['symbol']
        side = row['side']
        
        if row['execType'] != 'Trade':
            continue

        if symbol not in open_positions:
            open_positions[symbol] = {'trades': [], 'total_qty': 0, 'position_side': None}

        if open_positions[symbol]['position_side'] is None:
            open_positions[symbol]['position_side'] = side
            open_positions[symbol]['trades'].append(row)
            open_positions[symbol]['total_qty'] += row['execQty']
        elif side == open_positions[symbol]['position_side']:
            open_positions[symbol]['trades'].append(row)
            open_positions[symbol]['total_qty'] += row['execQty']
        else:
            closing_qty = row['execQty']
            
            entry_trades = open_positions[symbol]['trades']
            total_entry_value = sum(t['execPrice'] * t['execQty'] for t in entry_trades)
            total_entry_qty = sum(t['execQty'] for t in entry_trades)
            avg_entry_price = total_entry_value / total_entry_qty if total_entry_qty > 0 else 0
            
            entry_cost = avg_entry_price * closing_qty

            pnl = (row['execPrice'] - avg_entry_price) * closing_qty
            if open_positions[symbol]['position_side'] == 'Sell':
                pnl = -pnl

            total_fees = sum(t['execFee'] for t in entry_trades) + row['execFee']
            pnl_net = pnl - total_fees
            
            roi = (pnl_net / entry_cost) * 100 if entry_cost > 0 else 0

            # --- LÓGICA DE TIPO DE SAÍDA CORRIGIDA ---
            exit_type = row.get('stopOrderType')
            # Se o campo existe e não está vazio ou 'UNKNOWN'
            if exit_type and exit_type not in ['UNKNOWN', '']:
                pass # Mantém o valor (ex: 'StopLoss', 'TakeProfit', 'TrailingStop')
            # Se não, verifica como a ordem foi criada
            elif row.get('createType') == 'CreateByUser':
                exit_type = 'Parcial' # Mais descritivo
            else:
                exit_type = 'Desconhecido' # Caso genérico

            closed_trades.append({
                'symbol': symbol,
                'position_side': open_positions[symbol]['position_side'],
                'entry_time': entry_trades[0]['execTime'],
                'exit_time': row['execTime'],
                'quantity': closing_qty,
                'avg_entry_price': avg_entry_price,
                'exit_price': row['execPrice'],
                'entry_cost': entry_cost,
                'pnl_net': pnl_net,
                'roi_%': roi,
                'exit_type': exit_type # Usa o valor corrigido
            })

            open_positions.pop(symbol, None)

    if not closed_trades:
        return pd.DataFrame()

    return pd.DataFrame(closed_trades)
