from flask import Flask, render_template, request, flash, session, redirect, url_for
from flask_session import Session
import os
import logging
import pandas as pd

from bybit_client import fetch_bybit_data
from analysis import analyze_data

app = Flask(__name__)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'uma-chave-secreta-muito-forte-para-dev-local')
Session(app)

logging.basicConfig(level=logging.INFO)

@app.route('/', methods=['GET', 'POST'])
def dashboard():
    if request.method == 'POST':
        session['form_data'] = request.form
        
        api_key = request.form.get('api_key')
        api_secret = request.form.get('api_secret')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        account_name = request.form.get('account_name') or "Não especificado"
        # Pega a alavancagem do formulário
        leverage = float(request.form.get('leverage', 1))
        session['leverage'] = leverage # Salva na sessão para a página de detalhes

        raw_data_df, error_message = fetch_bybit_data(api_key, api_secret, start_date, end_date)
        
        if error_message:
            flash(error_message, 'error')
            return render_template('dashboard.html', analysis_done=False, form_data=session.get('form_data', {}))
        
        if raw_data_df.empty:
            flash('Nenhum trade encontrado para o período e credenciais informados.', 'error')
            return render_template('dashboard.html', analysis_done=False, form_data=session.get('form_data', {}))

        analysis_df = analyze_data(raw_data_df)
        
        if analysis_df.empty:
            flash('Nenhuma operação completa (abertura e fechamento) foi encontrada nos dados.', 'error')
            return render_template('dashboard.html', analysis_done=False, form_data=session.get('form_data', {}))

        session['analysis_df'] = analysis_df.to_json(orient='split', date_format='iso')

        total_pnl = analysis_df['pnl_net'].sum()
        win_rate = (analysis_df['pnl_net'] > 0).mean() * 100 if not analysis_df.empty else 0
        avg_roi = analysis_df['roi_%'].mean() if not analysis_df.empty else 0
        summary = {'total_pnl': total_pnl, 'win_rate': win_rate, 'avg_roi': avg_roi}

        symbol_summary = analysis_df.groupby('symbol').agg(
            pnl_total=('pnl_net', 'sum'),
            roi_total=('roi_%', 'sum'),
            n_trades=('symbol', 'size'),
            win_rate=('pnl_net', lambda x: (x > 0).mean() * 100)
        ).reset_index()
        
        symbol_summary.rename(columns={
            'symbol': 'Par', 'pnl_total': 'PnL Total (USDT)', 'roi_total': 'ROI Total (%)', 
            'n_trades': 'Nº de Trades', 'win_rate': 'Taxa de Acerto (%)'
        }, inplace=True)
        
        symbol_summary = symbol_summary[['Par', 'PnL Total (USDT)', 'ROI Total (%)', 'Taxa de Acerto (%)', 'Nº de Trades']]
        
        winners_df = symbol_summary[symbol_summary['PnL Total (USDT)'] >= 0].sort_values(by='PnL Total (USDT)', ascending=False)
        losers_df = symbol_summary[symbol_summary['PnL Total (USDT)'] < 0].sort_values(by='PnL Total (USDT)', ascending=True)

        exit_type_summary = analysis_df.groupby('exit_type').agg(
            pnl_total=('pnl_net', 'sum'), roi_medio=('roi_%', 'mean'), taxa_acerto=('pnl_net', lambda x: (x > 0).mean() * 100), contagem=('exit_type', 'size')
        ).reset_index()
        exit_type_summary.rename(columns={'exit_type': 'Tipo de Saída', 'pnl_total': 'PnL Total (USDT)', 'roi_medio': 'ROI Médio (%)', 'taxa_acerto': 'Taxa de Acerto (%)', 'contagem': 'Contagem'}, inplace=True)
        exit_type_summary = exit_type_summary.sort_values(by='PnL Total (USDT)', ascending=False)

        return render_template('dashboard.html',
                               analysis_done=True, summary=summary, winners=winners_df, losers=losers_df,
                               exit_summary=exit_type_summary, start_date=start_date, end_date=end_date,
                               account_name=account_name, form_data=session.get('form_data', {}))

    session.clear()
    return render_template('dashboard.html', analysis_done=False, form_data={})

@app.route('/trades/<symbol>')
def trade_details(symbol):
    analysis_json = session.get('analysis_df')
    leverage = session.get('leverage', 1.0) # Recupera a alavancagem da sessão
    
    if not analysis_json:
        flash('Sessão expirada ou dados não encontrados. Por favor, faça uma nova análise.', 'error')
        return redirect(url_for('dashboard'))

    analysis_df = pd.read_json(analysis_json, orient='split')
    
    analysis_df['entry_time'] = pd.to_datetime(analysis_df['entry_time'])
    analysis_df['exit_time'] = pd.to_datetime(analysis_df['exit_time'])

    symbol_trades = analysis_df[analysis_df['symbol'] == symbol].copy()
    
    if symbol_trades.empty:
        flash(f'Nenhum trade encontrado para o símbolo {symbol}.', 'error')
        return redirect(url_for('dashboard'))

    # Calcula a margem usada
    symbol_trades['margin_used'] = symbol_trades['entry_cost'] / leverage

    symbol_trades['duration'] = symbol_trades['exit_time'] - symbol_trades['entry_time']
    symbol_trades['duration'] = symbol_trades['duration'].apply(lambda x: str(x).split('.')[0])
    
    symbol_trades.rename(columns={'roi_%': 'roi'}, inplace=True)
    trades_list = symbol_trades.to_dict('records')

    return render_template('trades_detail.html', trades=trades_list, symbol=symbol)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
