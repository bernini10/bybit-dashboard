from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_session import Session
import os
import shutil
from datetime import datetime, timedelta
import pandas as pd

# Meus módulos
from bybit_client import fetch_all_trades, get_account_balance, get_account_transactions
from analysis import process_trades_data

# --- CONFIGURAÇÃO INICIAL ---
app = Flask(__name__)
app.config["SECRET_KEY"] = os.urandom(24)
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = "./flask_session"
Session(app)

if os.path.exists(app.config["SESSION_FILE_DIR"]):
    shutil.rmtree(app.config["SESSION_FILE_DIR"])
os.makedirs(app.config["SESSION_FILE_DIR"], exist_ok=True)

# --- ROTAS DA APLICAÇÃO ---

@app.route('/', methods=['GET'])
def index():
    return render_template('dashboard.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    form_data = request.form.to_dict()
    session['form_data'] = form_data
    
    try:
        # Buscar trades
        raw_df = fetch_all_trades(
            form_data['api_key'], 
            form_data['api_secret'],
            form_data['start_date'], 
            form_data['end_date']
        )
        
        if raw_df.empty:
            return jsonify({'status': 'error', 'message': 'Nenhum trade encontrado no período especificado.'})

        # Buscar saldo da conta
        try:
            account_balance = get_account_balance(form_data['api_key'], form_data['api_secret'])
        except Exception as e:
            print(f"Aviso: Não foi possível buscar saldo da conta: {e}")
            account_balance = None

        # Buscar movimentações
        try:
            transactions_df = get_account_transactions(
                form_data['api_key'], 
                form_data['api_secret'],
                form_data['start_date'], 
                form_data['end_date']
            )
        except Exception as e:
            print(f"Aviso: Não foi possível buscar movimentações: {e}")
            transactions_df = None

        analysis_results = process_trades_data(
            raw_df, 
            float(form_data.get('leverage', 10)),
            account_balance,
            transactions_df
        )
        
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
    if not session.get('analysis_done'):
        return jsonify({'status': 'error', 'message': 'Nenhuma análise encontrada na sessão.'})

    original_results = session['analysis_results']
    session['is_simulation'] = False

    return jsonify({
        'status': 'success',
        'template': render_template('partials/results.html', **original_results, form_data=session['form_data'], blacklist=session.get('blacklist', []), is_simulation=False)
    })

@app.route('/ban/<symbol>', methods=['POST'])
def ban_symbol(symbol):
    blacklist = session.get('blacklist', [])
    if symbol not in blacklist:
        blacklist.append(symbol)
        session['blacklist'] = blacklist
        return jsonify({'status': 'success', 'message': f'{symbol} adicionado à blacklist.'})
    else:
        return jsonify({'status': 'info', 'message': f'{symbol} já está na blacklist.'})

@app.route('/unban/<symbol>', methods=['POST'])
def unban_symbol(symbol):
    blacklist = session.get('blacklist', [])
    if symbol in blacklist:
        blacklist.remove(symbol)
        session['blacklist'] = blacklist
        return jsonify({'status': 'success', 'message': f'{symbol} removido da blacklist.'})
    else:
        return jsonify({'status': 'info', 'message': f'{symbol} não está na blacklist.'})

@app.route('/ban_multiple', methods=['POST'])
def ban_multiple():
    try:
        data = request.get_json()
        symbols = data.get('symbols', [])
        
        if not symbols:
            return jsonify({'status': 'error', 'message': 'Nenhum par selecionado.'})
        
        blacklist = session.get('blacklist', [])
        new_symbols = []
        
        for symbol in symbols:
            if symbol not in blacklist:
                blacklist.append(symbol)
                new_symbols.append(symbol)
        
        session['blacklist'] = blacklist
        
        if new_symbols:
            if len(new_symbols) == 1:
                message = f'{new_symbols[0]} adicionado à blacklist.'
            else:
                message = f'{len(new_symbols)} pares adicionados à blacklist: {", ".join(new_symbols)}'
        else:
            message = 'Todos os pares selecionados já estavam na blacklist.'
        
        return jsonify({'status': 'success', 'message': message})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Erro ao processar solicitação: {str(e)}'})

@app.route('/unban_all', methods=['POST'])
def unban_all():
    try:
        data = request.get_json()
        symbols = data.get('symbols', [])
        
        if not symbols:
            return jsonify({'status': 'error', 'message': 'Nenhum par fornecido.'})
        
        blacklist = session.get('blacklist', [])
        removed_symbols = []
        
        # Remover apenas símbolos que estão na blacklist
        for symbol in symbols:
            if symbol in blacklist:
                blacklist.remove(symbol)
                removed_symbols.append(symbol)
        
        session['blacklist'] = blacklist
        
        if removed_symbols:
            if len(removed_symbols) == 1:
                message = f'{removed_symbols[0]} removido da blacklist.'
            else:
                message = f'{len(removed_symbols)} pares removidos da blacklist: {", ".join(removed_symbols)}'
        else:
            message = 'Nenhum dos pares selecionados estava na blacklist.'
        
        return jsonify({'status': 'success', 'message': message})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Erro ao processar solicitação: {str(e)}'})

@app.route('/trades/<symbol>')
def trade_details(symbol):
    if not session.get('analysis_done'):
        return redirect(url_for('index'))
    analysis_data = session.get('analysis_results')
    trades = [trade for trade in analysis_data['all_trades'] if trade['symbol'] == symbol]
    return render_template('trades_detail.html', trades=trades, symbol=symbol)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
