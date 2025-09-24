import pandas as pd
from collections import defaultdict
from flask import Flask, render_template_string, request, redirect, url_for, flash
from datetime import datetime, timezone, timedelta
import time
from pybit.unified_trading import HTTP
import logging
import os

# --- HTML TEMPLATES ---

HTML_FORM_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Análise de Trades Bybit</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #121212; color: #e0e0e0; margin: 0; padding: 20px; }
        .container { max-width: 800px; margin: auto; background-color: #1e1e1e; padding: 30px; border-radius: 8px; border: 1px solid #333; }
        h1 { color: #00aaff; text-align: center; }
        form { display: flex; flex-direction: column; gap: 15px; }
        label { font-weight: bold; color: #bbb; }
        input[type="text"], input[type="password"], input[type="date"] { background-color: #333; border: 1px solid #555; color: #e0e0e0; padding: 10px; border-radius: 4px; font-size: 1em; }
        button { background-color: #00aaff; color: #121212; padding: 12px; border: none; border-radius: 4px; font-size: 1.1em; font-weight: bold; cursor: pointer; transition: background-color 0.3s; }
        button:hover { background-color: #0088cc; }
        .flash-message { padding: 15px; margin-bottom: 20px; border-radius: 4px; text-align: center; }
        .flash-error { background-color: #dc3545; color: white; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Análise de Trades Bybit</h1>
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="flash-message flash-{{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        <form action="/analyze" method="post">
            <label for="account_name">Nome da Conta (Opcional):</label>
            <input type="text" id="account_name" name="account_name" placeholder="Ex: Bot Principal">

            <label for="api_key">API Key:</label>
            <input type="password" id="api_key" name="api_key" required>
            
            <label for="api_secret">API Secret:</label>
            <input type="password" id="api_secret" name="api_secret" required>

            <label for="start_date">Data de Início:</label>
            <input type="date" id="start_date" name="start_date" required>

            <label for="end_date">Data de Fim:</label>
            <input type="date" id="end_date" name="end_date" required>

            <button type="submit">Analisar Trades</button>
        </form>
    </div>
</body>
</html>
"""

HTML_RESULTS_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard de Trades Bybit</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #121212; color: #e0e0e0; margin: 0; padding: 20px; }
        .container { max-width: 1200px; margin: auto; }
        h1, h2 { color: #00aaff; border-bottom: 2px solid #00aaff; padding-bottom: 10px; }
        a { color: #00aaff; text-decoration: none; }
        .header-info { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; }
        .kpi-container { display: flex; justify-content: space-around; flex-wrap: wrap; gap: 20px; margin-bottom: 40px; }
        .kpi-card { background-color: #1e1e1e; border-radius: 8px; padding: 20px; text-align: center; flex-grow: 1; border: 1px solid #333; }
        .kpi-card h3 { margin-top: 0; font-size: 1.2em; color: #bbb; }
        .kpi-value { font-size: 2.5em; font-weight: bold; }
        .positive { color: #28a745; }
        .negative { color: #dc3545; }
        .content-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(450px, 1fr)); gap: 30px; margin-top: 20px; }
        .table-wrapper { background-color: #1e1e1e; padding: 20px; border-radius: 8px; border: 1px solid #333; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { padding: 10px; border-bottom: 1px solid #333; text-align: left; font-size: 0.9em; }
        th { color: #00aaff; }
        td.positive { color: #28a745; font-weight: bold; }
        td.negative { color: #dc3545; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header-info">
            <h1>Dashboard de Análise</h1>
            <p><a href="/">&larr; Voltar para nova análise</a></p>
        </div>
        <p><strong>Conta:</strong> {{ account_name }} | <strong>Período:</strong> {{ start_date }} a {{ end_date }}</p>

        <div class="kpi-container">
            <div class="kpi-card">
                <h3>PnL Líquido Total</h3>
                <p class="kpi-value {{ 'positive' if summary.total_pnl > 0 else 'negative' }}">{{ "%.2f"|format(summary.total_pnl) }} USDT</p>
            </div>
            <div class="kpi-card">
                <h3>Taxa de Acerto</h3>
                <p class="kpi-value">{{ "%.2f"|format(summary.win_rate) }}%</p>
            </div>
            <div class="kpi-card">
                <h3>ROI Médio Total</h3>
                <p class="kpi-value {{ 'positive' if summary.avg_roi > 0 else 'negative' }}">{{ "%.2f"|format(summary.avg_roi) }}%</p>
            </div>
        </div>

        <div class="content-grid">
            <div class="table-wrapper">
                <h2>🏆 Ranking de Ganhadores</h2>
                <table>
                    <thead><tr>{% for col in winners.columns %}<th>{{ col }}</th>{% endfor %}</tr></thead>
                    <tbody>
                        {% for _, row in winners.iterrows() %}
                        <tr>
                            <td>{{ row['Par'] }}</td>
                            <td class="positive">{{ "%.2f"|format(row['PnL Total (USDT)']) }}</td>
                            <td class="positive">{{ "%.2f"|format(row['ROI Total (%)']) }}</td>
                            <td>{{ row['Nº de Trades'] }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            <div class="table-wrapper">
                <h2>💔 Ranking de Perdedores</h2>
                <table>
                     <thead><tr>{% for col in losers.columns %}<th>{{ col }}</th>{% endfor %}</tr></thead>
                    <tbody>
                        {% for _, row in losers.iterrows() %}
                        <tr>
                            <td>{{ row['Par'] }}</td>
                            <td class="negative">{{ "%.2f"|format(row['PnL Total (USDT)']) }}</td>
                            <td class="negative">{{ "%.2f"|format(row['ROI Total (%)']) }}</td>
                            <td>{{ row['Nº de Trades'] }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>

        <div class="table-wrapper" style="margin-top: 30px;">
            <h2>📊 Resumo por Tipo de Saída</h2>
            <table>
                <thead><tr>{% for col in exit_summary.columns %}<th>{{ col }}</th>{% endfor %}</tr></thead>
                <tbody>
                    {% for _, row in exit_summary.iterrows() %}
                    <tr>
                        <td>{{ row['Tipo de Saída'] }}</td>
                        <td class="{{ 'positive' if row['PnL Total (USDT)'] > 0 else 'negative' }}">{{ "%.2f"|format(row['PnL Total (USDT)']) }}</td>
                        <td class="{{ 'positive' if row['ROI Médio (%)'] > 0 else 'negative' }}">{{ "%.2f"|format(row['ROI Médio (%)']) }}</td>
                        <td>{{ "%.2f"|format(row['Taxa de Acerto (%)']) }}</td>
                        <td>{{ row['Contagem'] }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""

# --- LÓGICA DA APLICAÇÃO ---
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'uma-chave-secreta-muito-forte-para-dev-local')
logging.basicConfig(level=logging.INFO)

def fetch_bybit_data(api_key, api_secret, start_date_str, end_date_str):
    """Busca dados da Bybit, lidando com paginação e o limite de 7 dias."""
    try:
        session = HTTP(api_key=api_key, api_secret=api_secret)
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    except Exception as e:
        logging.error(f"Erro nas credenciais ou formato de data: {e}")
        return None, f"Erro nas credenciais ou formato de data: {e}"

    all_executions = []
    current_start_dt = start_date
    
    while current_start_dt < end_date:
        current_end_dt = min(current_start_dt + timedelta(days=7), end_date)
        start_ts = int(current_start_dt.replace(tzinfo=timezone.utc).timestamp() * 1000)
        end_ts = int(current_end_dt.replace(tzinfo=timezone.utc).timestamp() * 1000)
        
        logging.info(f"Buscando dados de {current_start_dt.date()} a {current_end_dt.date()}...")
        
        cursor = ""
        while True:
            try:
                response = session.get_executions(
                    category="linear", startTime=start_ts, endTime=end_ts, limit=100, cursor=cursor
                )
                if response['retCode'] == 0:
                    executions = response['result']['list']
                    all_executions.extend(executions)
                    cursor = response['result'].get('nextPageCursor', "")
                    if not cursor: break
                    time.sleep(0.2)
                else:
                    msg = f"Erro da API Bybit ao buscar trades: {response['retMsg']} (ErrCode: {response['retCode']})"
                    logging.error(msg)
                    return None, msg
            except Exception as e:
                msg = f"Exceção ao buscar trades: {e}"
                logging.error(msg)
                return None, msg
        
        current_start_dt += timedelta(days=7)

    return pd.DataFrame(all_executions), None

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

@app.route('/')
def index():
    """Exibe o formulário de entrada."""
    return render_template_string(HTML_FORM_TEMPLATE)

@app.route('/analyze', methods=['POST'])
def analyze():
    """Coleta, analisa e exibe os resultados."""
    api_key = request.form['api_key']
    api_secret = request.form['api_secret']
    start_date = request.form['start_date']
    end_date = request.form['end_date']
    account_name = request.form.get('account_name') or "Não especificado"

    raw_data_df, error_message = fetch_bybit_data(api_key, api_secret, start_date, end_date)
    
    if error_message:
        flash(error_message, 'error')
        return redirect(url_for('index'))
    
    if raw_data_df.empty:
        flash('Nenhum trade encontrado para o período e credenciais informados.', 'error')
        return redirect(url_for('index'))

    analysis_df = analyze_data(raw_data_df)
    
    if analysis_df.empty:
        flash('Nenhuma operação completa (abertura e fechamento) foi encontrada nos dados coletados.', 'error')
        return redirect(url_for('index'))

    total_pnl = analysis_df['pnl_net'].sum()
    win_rate = (analysis_df['pnl_net'] > 0).mean() * 100 if not analysis_df.empty else 0
    avg_roi = analysis_df['roi_%'].mean() if not analysis_df.empty else 0
    summary = {'total_pnl': total_pnl, 'win_rate': win_rate, 'avg_roi': avg_roi}

    symbol_summary = analysis_df.groupby('symbol').agg(
        pnl_total=('pnl_net', 'sum'), roi_total=('roi_%', 'sum'), n_trades=('symbol', 'size')
    ).reset_index()
    symbol_summary.rename(columns={'symbol': 'Par', 'pnl_total': 'PnL Total (USDT)', 'roi_total': 'ROI Total (%)', 'n_trades': 'Nº de Trades'}, inplace=True)
    winners_df = symbol_summary[symbol_summary['PnL Total (USDT)'] >= 0].sort_values(by='PnL Total (USDT)', ascending=False)
    losers_df = symbol_summary[symbol_summary['PnL Total (USDT)'] < 0].sort_values(by='PnL Total (USDT)', ascending=True)

    exit_type_summary = analysis_df.groupby('exit_type').agg(
        pnl_total=('pnl_net', 'sum'), roi_medio=('roi_%', 'mean'), taxa_acerto=('pnl_net', lambda x: (x > 0).mean() * 100), contagem=('exit_type', 'size')
    ).reset_index()
    exit_type_summary.rename(columns={'exit_type': 'Tipo de Saída', 'pnl_total': 'PnL Total (USDT)', 'roi_medio': 'ROI Médio (%)', 'taxa_acerto': 'Taxa de Acerto (%)', 'contagem': 'Contagem'}, inplace=True)
    exit_type_summary = exit_type_summary.sort_values(by='PnL Total (USDT)', ascending=False)

    return render_template_string(HTML_RESULTS_TEMPLATE,
                                  summary=summary, winners=winners_df, losers=losers_df,
                                  exit_summary=exit_type_summary, start_date=start_date, end_date=end_date,
                                  account_name=account_name)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
