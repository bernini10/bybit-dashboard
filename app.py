from flask import Flask, render_template, request, flash
import os
import logging

# Importa as funções que separamos
from bybit_client import fetch_bybit_data
from analysis import analyze_data

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'uma-chave-secreta-muito-forte-para-dev-local')
logging.basicConfig(level=logging.INFO)

@app.route('/', methods=['GET', 'POST'])
def dashboard():
    # Se a página for carregada via POST (formulário enviado)
    if request.method == 'POST':
        form_data = request.form
        api_key = form_data.get('api_key')
        api_secret = form_data.get('api_secret')
        start_date = form_data.get('start_date')
        end_date = form_data.get('end_date')
        account_name = form_data.get('account_name') or "Não especificado"

        raw_data_df, error_message = fetch_bybit_data(api_key, api_secret, start_date, end_date)
        
        if error_message:
            flash(error_message, 'error')
            return render_template('dashboard.html', analysis_done=False, form_data=form_data)
        
        if raw_data_df.empty:
            flash('Nenhum trade encontrado para o período e credenciais informados.', 'error')
            return render_template('dashboard.html', analysis_done=False, form_data=form_data)

        analysis_df = analyze_data(raw_data_df)
        
        if analysis_df.empty:
            flash('Nenhuma operação completa (abertura e fechamento) foi encontrada nos dados.', 'error')
            return render_template('dashboard.html', analysis_done=False, form_data=form_data)

        # Preparar os dados para o template
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

        return render_template('dashboard.html',
                               analysis_done=True,
                               summary=summary,
                               winners=winners_df,
                               losers=losers_df,
                               exit_summary=exit_type_summary,
                               start_date=start_date,
                               end_date=end_date,
                               account_name=account_name,
                               form_data=form_data)

    # Se a página for carregada via GET (primeiro acesso)
    return render_template('dashboard.html', analysis_done=False, form_data={})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True) # Mantendo a porta 5001 para seu ambiente local
