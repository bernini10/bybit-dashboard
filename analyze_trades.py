import pandas as pd
from collections import defaultdict

def analyze_bybit_trades_v2(input_filename="bybit_trades.csv"):
    """
    Realiza uma análise avançada de um arquivo CSV de execuções da Bybit.
    Calcula PnL, ROI, e analisa o desempenho por símbolo e tipo de saída.
    """
    try:
        df = pd.read_csv(input_filename, dtype={'orderId': str, 'orderLinkId': str})
        numeric_cols = ['execQty', 'execPrice', 'execValue', 'execFee']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df['execTime'] = pd.to_datetime(df['execTime'], unit='ms')
        df = df.sort_values(by='execTime').reset_index(drop=True)
    except FileNotFoundError:
        print(f"Erro: O arquivo '{input_filename}' não foi encontrado.")
        return
    except Exception as e:
        print(f"Erro ao ler o arquivo CSV: {e}")
        return

    trades_df = df[df['execType'] == 'Trade'].copy()
    
    open_positions = defaultdict(lambda: {'qty': 0, 'cost': 0, 'fees': 0, 'entry_time': None, 'entry_count': 0})
    closed_trades = []
    
    print("Iniciando análise avançada de trades...")

    for index, row in trades_df.iterrows():
        symbol = row['symbol']
        side = row['side']
        qty = row['execQty']
        price = row['execPrice']
        fee = row['execFee']
        
        position = open_positions[symbol]
        
        # Define a direção da quantidade: positiva para Buy, negativa para Sell
        signed_qty = qty if side == 'Buy' else -qty
        
        # Se a posição está zerada, este é o primeiro trade de abertura
        if position['qty'] == 0:
            position['qty'] = signed_qty
            position['cost'] = signed_qty * price
            position['fees'] = fee
            position['entry_time'] = row['execTime']
            position['entry_count'] = 1
        # Se o trade é na mesma direção da posição, é um aumento de posição (preço médio)
        elif (position['qty'] > 0 and side == 'Buy') or (position['qty'] < 0 and side == 'Sell'):
            position['cost'] += signed_qty * price
            position['qty'] += signed_qty
            position['fees'] += fee
            position['entry_count'] += 1
        # Se o trade é na direção oposta, é um fechamento (parcial ou total)
        else:
            close_qty = min(abs(position['qty']), qty)
            
            # Preço médio de entrada da posição atual
            avg_entry_price = position['cost'] / position['qty']
            
            # Custo de entrada proporcional à quantidade que está sendo fechada
            entry_cost_of_closed_portion = abs(avg_entry_price * close_qty)
            
            # PnL Bruto
            if side == 'Buy': # Fechando uma posição Short
                pnl_gross = (abs(avg_entry_price) - price) * close_qty
            else: # Fechando uma posição Long
                pnl_gross = (price - abs(avg_entry_price)) * close_qty
            
            # Taxas
            entry_fees_of_closed_portion = (position['fees'] / abs(position['qty'])) * close_qty
            total_fees = entry_fees_of_closed_portion + fee
            
            pnl_net = pnl_gross - total_fees
            
            # ROI
            roi = (pnl_net / entry_cost_of_closed_portion) * 100 if entry_cost_of_closed_portion > 0 else 0

            # Tipo de fechamento
            exit_type = row['stopOrderType'] if pd.notna(row['stopOrderType']) and row['stopOrderType'] != 'UNKNOWN' else row['createType']

            closed_trades.append({
                'symbol': symbol,
                'position_side': 'Long' if position['qty'] > 0 else 'Short',
                'entry_time': position['entry_time'],
                'exit_time': row['execTime'],
                'quantity': close_qty,
                'avg_entry_price': abs(avg_entry_price),
                'exit_price': price,
                'entry_cost': entry_cost_of_closed_portion,
                'pnl_net': pnl_net,
                'roi_%': roi,
                'result': 'Lucro' if pnl_net > 0 else 'Perda',
                'exit_type': exit_type,
                'order_link_id': row['orderLinkId']
            })
            
            # Atualiza a posição restante
            position['qty'] += signed_qty
            position['cost'] = position['qty'] * avg_entry_price # O custo restante mantém o preço médio
            position['fees'] -= entry_fees_of_closed_portion
            
            # Se a posição foi completamente zerada, reseta
            if abs(position['qty']) < 1e-9:
                position['qty'] = 0
                position['cost'] = 0
                position['fees'] = 0
                position['entry_time'] = None
                position['entry_count'] = 0

    print(f"Análise concluída. {len(closed_trades)} operações fechadas foram identificadas.")

    if not closed_trades:
        print("Nenhuma operação completa foi encontrada.")
        return

    # --- GERAÇÃO DE RELATÓRIOS ---
    analysis_df = pd.DataFrame(closed_trades)
    
    # 1. Relatório detalhado de cada trade
    analysis_df.to_csv("trade_analysis_detailed.csv", index=False, float_format='%.6f')
    print("\n[1] Relatório detalhado de cada operação salvo em 'trade_analysis_detailed.csv'")

    # 2. Resumo por Símbolo (Par de Moedas)
    symbol_summary = analysis_df.groupby('symbol').agg(
        total_pnl_net=('pnl_net', 'sum'),
        average_roi=('roi_%', 'mean'),
        win_rate=('result', lambda x: (x == 'Lucro').mean() * 100),
        trade_count=('symbol', 'size')
    ).sort_values(by='total_pnl_net', ascending=False)
    symbol_summary.to_csv("symbol_summary.csv", float_format='%.4f')
    print("[2] Resumo de desempenho por símbolo salvo em 'symbol_summary.csv'")

    # 3. Resumo por Tipo de Saída
    exit_type_summary = analysis_df.groupby('exit_type').agg(
        total_pnl_net=('pnl_net', 'sum'),
        average_roi=('roi_%', 'mean'),
        win_rate=('result', lambda x: (x == 'Lucro').mean() * 100),
        exit_count=('exit_type', 'size')
    ).sort_values(by='total_pnl_net', ascending=False)
    exit_type_summary.to_csv("exit_type_summary.csv", float_format='%.4f')
    print("[3] Resumo de desempenho por tipo de saída salvo em 'exit_type_summary.csv'")

    # --- EXIBIÇÃO DOS INSIGHTS NO TERMINAL ---
    pd.set_option('display.width', 1000)
    
    print("\n" + "="*40)
    print("  INSIGHTS PRINCIPAIS DA SUA OPERAÇÃO")
    print("="*40)

    print("\n--- Desempenho por Símbolo (Pares de Moedas) ---")
    print(symbol_summary.to_string(float_format="%.2f"))
    
    print("\n--- Desempenho por Tipo de Fechamento ---")
    print(exit_type_summary.to_string(float_format="%.2f"))

    print("\n--- Top 5 Melhores Operações (por PnL) ---")
    print(analysis_df.nlargest(5, 'pnl_net').to_string())
    
    print("\n--- Top 5 Piores Operações (por PnL) ---")
    print(analysis_df.nsmallest(5, 'pnl_net').to_string())


if __name__ == "__main__":
    analyze_bybit_trades_v2()
