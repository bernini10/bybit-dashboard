from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from flask_session import Session
import os
import shutil
from datetime import datetime, timedelta

# Meus módulos
from bybit_client import fetch_all_trades
from analysis import process_trades_data

# --- CONFIGURAÇÃO INICIAL ---
app = Flask(__name__)
app.config["SECRET_KEY"] = os.urandom(24)
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = "./flask_session"
Session(app)

# Limpa a pasta de sessão na inicialização para garantir um começo limpo
if os.path.exists(app.config["SESSION_FILE_DIR"]):
    shutil.rmtree(app.config["SESSION_FILE_DIR"])
os.makedirs(app.config["SESSION_FILE_DIR"], exist_ok=True)

# --- ROTAS DA APLICAÇÃO ---

@app.route('/', methods=['GET'])
def index():
    """
    Página inicial que renderiza o dashboard.
    Não limpa mais a sessão aqui para manter o estado.
    """
    # A lógica de limpeza foi movida para a rota /logout
    return render_template('dashboard.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    """Rota para a primeira análise de dados."""
    form_data = request.form.to_dict()
    session['form_data'] = form_data
    
    try:
        raw_df = fetch_all_trades(
            form_data['api_key'], 
            form_data['api_secret'],
            form_data['start_date'], 
            form_data['end_date']
        )
        
        if raw_df.empty:
            return jsonify({'status': 'error', 'message': 'Nenhum trade encontrado no período especificado.'})

        analysis_results = process_trades_data(raw_df, float(form_data.get('leverage', 10)))
        
        session['analysis_results'] = analysis_results
        session['analysis_done'] = True
        session['blacklist'] = []
        session['is_simulation'] = False

        return jsonify({
            'status': 'success',
            'template': render_template('partials/results.html', **analysis_results, form_data=form_data, blacklist=[], is_simulation=False)
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Erro ao processar a solicitação: {e}'})

@app.route('/recalculate', methods=['POST'])
def recalculate():
    """Recalcula a análise excluindo os pares da blacklist."""
    if not session.get('analysis_done'):
        return jsonify({'status': 'error', 'message': 'Nenhuma análise encontrada na sessão.'})

    original_results = session['analysis_results']
    blacklist = session.get('blacklist', [])
    
    filtered_df = original_results['raw_df'][~original_results['raw_df']['symbol'].isin(blacklist)]
    
    if filtered_df.empty:
        return jsonify({'status': 'error', 'message': 'Nenhum trade restante após aplicar a blacklist.'})

    recalculated_results = process_trades_data(filtered_df, float(session['form_data'].get('leverage', 10)))
    
    session['is_simulation'] = True

    return jsonify({
        'status': 'success',
        'template': render_template('partials/results.html', **recalculated_results, form_data=session['form_data'], blacklist=blacklist, is_simulation=True)
    })

@app.route('/restore', methods=['POST'])
def restore():
    """Restaura a análise original completa."""
    if not session.get('analysis_done'):
        return jsonify({'status': 'error', 'message': 'Nenhuma análise encontrada na sessão.'})
    
    session['is_simulation'] = False
    
    return jsonify({
        'status': 'success',
        'template': render_template('partials/results.html', **session['analysis_results'], form_data=session['form_data'], blacklist=session.get('blacklist', []), is_simulation=False)
    })

@app.route('/ban/<symbol>', methods=['POST'])
def ban_symbol(symbol):
    """Adiciona um símbolo à blacklist na sessão."""
    blacklist = session.get('blacklist', [])
    if symbol not in blacklist:
        blacklist.append(symbol)
        session['blacklist'] = blacklist
        return jsonify({'status': 'success', 'message': f'{symbol} adicionado à blacklist.'})
    return jsonify({'status': 'info', 'message': f'{symbol} já está na blacklist.'})

@app.route('/unban/<symbol>', methods=['POST'])
def unban_symbol(symbol):
    """Remove um símbolo da blacklist na sessão."""
    blacklist = session.get('blacklist', [])
    if symbol in blacklist:
        blacklist.remove(symbol)
        session['blacklist'] = blacklist
        return jsonify({'status': 'success', 'message': f'{symbol} removido da blacklist.'})
    return jsonify({'status': 'info', 'message': f'{symbol} não encontrado na blacklist.'})

@app.route('/trades/<symbol>')
def trade_details(symbol):
    """Mostra a página de detalhes para um símbolo específico."""
    if not session.get('analysis_done'):
        return redirect(url_for('index'))
    
    analysis_data = session.get('analysis_results')

    trades = [trade for trade in analysis_data['all_trades'] if trade['symbol'] == symbol]
    return render_template('trades_detail.html', trades=trades, symbol=symbol)

@app.route('/logout')
def logout():
    """Limpa a sessão e redireciona para a página inicial."""
    session.clear()
    return redirect(url_for('index'))

# --- EXECUÇÃO ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
