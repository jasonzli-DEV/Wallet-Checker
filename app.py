
from flask import Flask, render_template_string, request, redirect, session
from dotenv import load_dotenv
import os
from bip_utils import Bip39SeedGenerator, Bip44, Bip44Coins, Bip44Changes, Bip86, Bip86Coins
from mnemonic import Mnemonic
import sqlite3
import data_store
import requests
import threading
import time

load_dotenv()

print('app.py loaded')

app = Flask(__name__)
app.secret_key = os.urandom(24)

PORT = int(os.getenv('PORT', 6060))
PASSWORD = os.getenv('PASSWORD', 'changeme')

# Global auto-gen settings (server-wide)
app.config['AUTO_GEN_RATE'] = 0  # seeds per second, 0 = disabled
app.config['SAVE_IF_BALANCE'] = False

LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Wallet Checker Login</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css">
</head>
<body class="bg-light">
<div class="container mt-5">
    <div class="row justify-content-center">
        <div class="col-md-4">
            <div class="card p-4 shadow">
                <h2 class="mb-3">Login</h2>
                <form method="post">
                    <input type="password" class="form-control mb-2" name="password" placeholder="Password" required />
                    <button type="submit" class="btn btn-primary w-100">Login</button>
                    {% if error %}<p class="text-danger mt-2">{{ error }}</p>{% endif %}
                </form>
            </div>
        </div>
    </div>
</div>
</body>
</html>
'''

WALLET_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
        <title>Wallet Checker</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css">
        <style>
            body { background:#f6f8fa }
            .card { border-radius:8px }
            .small-muted { font-size:0.85rem; color:#6c757d }
        </style>
</head>
<body>
<div class="container my-4">
    <div class="d-flex mb-3 justify-content-between align-items-center">
        <h1 class="h4 mb-0">Wallet Checker</h1>
        <div>
            <a href="/logout" class="btn btn-outline-secondary btn-sm">Logout</a>
            <button class="btn btn-outline-secondary btn-sm ms-2" data-bs-toggle="modal" data-bs-target="#settingsModal">Settings</button>
        </div>
    </div>

    <ul class="nav nav-tabs" id="mainTab" role="tablist">
        <li class="nav-item" role="presentation">
            <button class="nav-link active" id="wallet-tab" data-bs-toggle="tab" data-bs-target="#wallet" type="button" role="tab">Wallet</button>
        </li>
        <li class="nav-item" role="presentation">
            <button class="nav-link" id="stats-tab" data-bs-toggle="tab" data-bs-target="#stats" type="button" role="tab">Stats</button>
        </li>
    </ul>

    <div class="tab-content mt-3">
        <div class="tab-pane fade show active" id="wallet" role="tabpanel">
            <div class="card p-4 shadow-sm">
                <form method="post">
                    <div class="d-flex gap-2">
                        <button type="submit" class="btn btn-success">Generate & Check</button>
                        <div class="small-muted align-self-center">Auto-gen: <b>{{ settings.auto_generate }}</b>/s · Save-if-balance: <b>{{ 'Yes' if settings.save_if_balance else 'No' }}</b></div>
                    </div>
                </form>

                {% if result %}
                <div class="alert alert-info mt-3">
                    <div class="d-flex justify-content-between">
                        <div>
                            <h6 class="mb-1">Latest Generated</h6>
                            <div class="small-muted">Seed hidden — use Copy</div>
                        </div>
                        <div class="small-muted">Balances — BTC: {{ result['btc_balance'] }} · ETH: {{ result['eth_balance'] }} · SOL: {{ result['sol_balance'] }}</div>
                    </div>
                </div>
                                {% endif %}

                                <!-- Result Modal (shows details after manual generate) -->
                                <div class="modal fade" id="resultModal" tabindex="-1" aria-labelledby="resultModalLabel" aria-hidden="true">
                                    <div class="modal-dialog">
                                        <div class="modal-content">
                                            <div class="modal-header">
                                                <h5 class="modal-title" id="resultModalLabel">Generated Wallet</h5>
                                                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                                            </div>
                                            <div class="modal-body">
                                                <div class="mb-2"><strong>Seed Phrase</strong></div>
                                                <div class="mb-2"><code>{{ result['mnemonic'] }}</code> <button class="btn btn-sm btn-outline-secondary ms-2" onclick="copyToClipboard('{{ result['mnemonic'] }}')">Copy</button></div>
                                                <hr />
                                                <div><strong>BTC</strong></div>
                                                <div class="mb-2">{{ result['btc'] }} <button class="btn btn-sm btn-outline-secondary ms-2" onclick="copyToClipboard('{{ result['btc'] }}')">Copy</button></div>
                                                <div><strong>ETH</strong></div>
                                                <div class="mb-2">{{ result['eth'] }} <button class="btn btn-sm btn-outline-secondary ms-2" onclick="copyToClipboard('{{ result['eth'] }}')">Copy</button></div>
                                                <div><strong>SOL</strong></div>
                                                <div class="mb-2">{{ result['sol'] }} <button class="btn btn-sm btn-outline-secondary ms-2" onclick="copyToClipboard('{{ result['sol'] }}')">Copy</button></div>
                                                <hr />
                                                <div class="small-muted">Balances — BTC: {{ result['btc_balance'] }} · ETH: {{ result['eth_balance'] }} · SOL: {{ result['sol_balance'] }}</div>
                                            </div>
                                            <div class="modal-footer">
                                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <div class="d-flex justify-content-between align-items-center">
                                    <h6 class="mt-3 mb-0">Recent Results</h6>
                                    <div class="mt-2">
                                        <form method="post" action="/load_more" style="display:inline-block">
                                            <button class="btn btn-sm btn-outline-primary">Load more</button>
                                        </form>
                                        <form method="post" action="/clear" onsubmit="return confirm('Clear all saved results?');" style="display:inline-block; margin-left:8px;">
                                            <button class="btn btn-sm btn-outline-danger">Clear</button>
                                        </form>
                                    </div>
                                </div>
                <div class="table-responsive">
                    <table class="table table-sm table-striped align-middle">
                        <thead>
                            <tr>
                                <th>Seed</th>
                                <th>BTC</th>
                                <th>ETH</th>
                                <th>SOL</th>
                            </tr>
                        </thead>
                        <tbody>
                        {% for row in results %}
                            {% set btc = row[1] %}
                            {% set eth = row[2] %}
                            {% set sol = row[3] %}
                            <tr>
                                <td><button class="btn btn-outline-secondary btn-sm" onclick="copyToClipboard('{{ row[0] }}')">Copy</button></td>
                                <td><div class="d-flex align-items-center"><span class="me-2">{{ get_balance(btc, 'bitcoin') }}</span><button class="btn btn-outline-secondary btn-sm" onclick="copyToClipboard('{{ btc }}')">Copy</button></div></td>
                                <td><div class="d-flex align-items-center"><span class="me-2">{{ get_balance(eth, 'ethereum') }}</span><button class="btn btn-outline-secondary btn-sm" onclick="copyToClipboard('{{ eth }}')">Copy</button></div></td>
                                <td><div class="d-flex align-items-center"><span class="me-2">{{ get_balance(sol, 'solana') }}</span><button class="btn btn-outline-secondary btn-sm" onclick="copyToClipboard('{{ sol }}')">Copy</button></div></td>
                            </tr>
                        {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <div class="tab-pane fade" id="stats" role="tabpanel">
            <div class="card p-4 shadow-sm">
                <h6>Statistics</h6>
                <div class="row">
                    <div class="col-md-4">
                        <div class="small-muted">Total checked (last 1m)</div>
                        <div><b>{{ stats.total_checked_per_minute }}</b></div>
                    </div>
                    <div class="col-md-4">
                        <div class="small-muted">Auto-gen rate</div>
                        <div><b>{{ stats.auto_gen_rate }} /s</b></div>
                    </div>
                    <div class="col-md-4">
                        <div class="small-muted">Save-only-if-balance</div>
                        <div><b>{{ 'Yes' if stats.save_if_balance else 'No' }}</b></div>
                    </div>
                </div>
                <div class="mt-3 small-muted">Last checked: {{ stats.last_checked or 'N/A' }}</div>
            </div>
        </div>
    </div>

    <!-- Settings Modal -->
    <div class="modal fade" id="settingsModal" tabindex="-1" aria-labelledby="settingsModalLabel" aria-hidden="true">
        <div class="modal-dialog">
            <div class="modal-content">
                <form method="post" action="/settings">
                    <div class="modal-header">
                        <h5 class="modal-title" id="settingsModalLabel">Settings</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <div class="mb-3">
                            <label for="auto_generate" class="form-label">Auto-generate wallets (max 30/sec)</label>
                            <input type="number" min="0" max="30" class="form-control" id="auto_generate" name="auto_generate" value="{{ settings.auto_generate }}">
                        </div>
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" id="save_if_balance" name="save_if_balance" value="1" {% if settings.save_if_balance %}checked{% endif %}>
                            <label class="form-check-label" for="save_if_balance">Only save if any balance &gt; 0</label>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                        <button type="submit" class="btn btn-primary">Save</button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
    <script>
    function copyToClipboard(text) {
        navigator.clipboard.writeText(text).then(()=>{}, ()=>{alert('Failed to copy')});
    }
        // show result modal after manual generate
        (function(){
            var show = {{ 'true' if show_modal else 'false' }};
            if(show){
                var m = new bootstrap.Modal(document.getElementById('resultModal'));
                m.show();
            }
        })();
    </script>
</div>
</body>
</html>
'''

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['password'] == PASSWORD:
            session['logged_in'] = True
            return redirect('/wallet')
        else:
            return render_template_string(LOGIN_TEMPLATE, error="Invalid password")
    return render_template_string(LOGIN_TEMPLATE, error=None)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


@app.route('/wallet', methods=['GET', 'POST'])
def wallet():
    if not session.get('logged_in'):
        return redirect('/')
    data_store.init_db()
    # Load settings from DB (persisted)
    db_settings = data_store.get_settings()
    app.config['AUTO_GEN_RATE'] = db_settings.get('auto_generate', 0)
    app.config['SAVE_IF_BALANCE'] = db_settings.get('save_if_balance', False)
    # ensure session limit exists
    session.setdefault('limit', 20)
    settings = {
        'auto_generate': db_settings.get('auto_generate', session.get('auto_generate', 0)),
        'save_if_balance': db_settings.get('save_if_balance', session.get('save_if_balance', False))
    }
    result = None
    show_modal = False
    def should_save(btc, eth, sol):
        if not settings['save_if_balance']:
            return True
        try:
            return float(btc) > 0 or float(eth) > 0 or float(sol) > 0
        except Exception:
            return False
    def fix_balance(val):
        return '0.0' if val in ['N/A', None, '', 'error'] else val
    if request.method == 'POST':
        count = int(settings['auto_generate']) if settings['auto_generate'] else 1
        import time
        generated = 0
        start = time.time()
        while generated < count:
            mnemo = Mnemonic('english')
            mnemonic = mnemo.generate(strength=128)
            seed_bytes = Bip39SeedGenerator(mnemonic).Generate()
            btc_ctx = Bip86.FromSeed(seed_bytes, Bip86Coins.BITCOIN)
            btc_ctx = btc_ctx.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
            btc_addr = btc_ctx.PublicKey().ToAddress()
            eth_ctx = Bip44.FromSeed(seed_bytes, Bip44Coins.ETHEREUM).DeriveDefaultPath()
            eth_addr = eth_ctx.PublicKey().ToAddress()
            sol_ctx = Bip44.FromSeed(seed_bytes, Bip44Coins.SOLANA).Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT)
            sol_addr = sol_ctx.PublicKey().ToAddress()
            # Query Ankr API for balances
            ANKR_URL = "https://rpc.ankr.com/multichain"
            payload = {
                "jsonrpc": "2.0",
                "method": "ankr_getAccountBalance",
                "params": {
                    "walletAddress": [btc_addr, eth_addr, sol_addr],
                    "blockchain": ["bitcoin", "ethereum", "solana"]
                },
                "id": 1
            }
            try:
                r = requests.post(ANKR_URL, json=payload, timeout=10)
                data = r.json()
                balances = {c['blockchain']: c['balance'] for c in data.get('result', {}).get('assets', [])}
            except Exception as e:
                balances = {"bitcoin": "error", "ethereum": "error", "solana": "error"}
            btc_bal = fix_balance(balances.get('bitcoin', 'N/A'))
            eth_bal = fix_balance(balances.get('ethereum', 'N/A'))
            sol_bal = fix_balance(balances.get('solana', 'N/A'))
            if should_save(btc_bal, eth_bal, sol_bal):
                data_store.save_result(mnemonic, btc_addr, eth_addr, sol_addr)
            # record check regardless of save setting
            try:
                data_store.save_check(mnemonic, btc_addr, eth_addr, sol_addr, saved=should_save(btc_bal, eth_bal, sol_bal))
            except Exception:
                pass
            # Only show the last generated result
            result = {
                'mnemonic': mnemonic,
                'btc': btc_addr,
                'eth': eth_addr,
                'sol': sol_addr,
                'btc_balance': btc_bal,
                'eth_balance': eth_bal,
                'sol_balance': sol_bal,
            }
            generated += 1
            # Throttle to max 30/sec
            if count > 1:
                elapsed = time.time() - start
                if generated / max(elapsed, 0.01) > 30:
                    time.sleep(1.0 / 30)
    results = data_store.get_results(limit=session.get('limit', 20))
    # compute stats (labelled Total Checked)
    try:
        conn = sqlite3.connect('results.db')
        cur = conn.cursor()
        # use checks table for 'checked' stats so save-if-balance doesn't affect counts
        cur.execute('SELECT COUNT(*) FROM checks')
        total_checks = cur.fetchone()[0]
        cur.execute('SELECT created_at FROM checks ORDER BY id DESC LIMIT 1')
        last = cur.fetchone()
        last_checked = last[0] if last else None
        # count in last minute
        try:
            cur.execute("SELECT COUNT(*) FROM checks WHERE created_at >= datetime('now', '-1 minute')")
            per_min = cur.fetchone()[0]
        except Exception:
            per_min = 0
    except Exception:
        total_checks = 0
        last_checked = None
    finally:
        try:
            conn.close()
        except Exception:
            pass
    stats = type('S', (), {})()
    stats.total_checked_per_minute = per_min if 'per_min' in locals() else 0
    stats.auto_gen_rate = app.config.get('AUTO_GEN_RATE', 0)
    stats.save_if_balance = app.config.get('SAVE_IF_BALANCE', False)
    stats.last_checked = last_checked
    def get_balance(addr, chain):
        if result:
            if chain == 'bitcoin' and result['btc'] == addr:
                return result['btc_balance']
            if chain == 'ethereum' and result['eth'] == addr:
                return result['eth_balance']
            if chain == 'solana' and result['sol'] == addr:
                return result['sol_balance']
        return '0.0'
    # show modal when user manually generated via POST
    show_modal = (request.method == 'POST')
    return render_template_string(WALLET_TEMPLATE, result=result, results=results, get_balance=get_balance, settings=settings, stats=stats, show_modal=show_modal)


@app.route('/settings', methods=['POST'])
def settings():
    auto_generate = int(request.form.get('auto_generate', 0))
    save_if_balance = bool(request.form.get('save_if_balance'))
    auto_generate = min(max(auto_generate, 0), 30)
    # persist settings to DB
    data_store.save_settings(auto_generate, save_if_balance)
    session['auto_generate'] = auto_generate
    session['save_if_balance'] = save_if_balance
    # Set server-global settings so background auto-gen uses them
    app.config['AUTO_GEN_RATE'] = auto_generate
    app.config['SAVE_IF_BALANCE'] = save_if_balance
    return redirect('/wallet')


@app.route('/load_more', methods=['POST'])
def load_more():
    session['limit'] = min(session.get('limit', 20) + 20, 1000)
    return redirect('/wallet')


@app.route('/clear', methods=['POST'])
def clear_results_route():
    data_store.clear_results()
    return redirect('/wallet')


def auto_gen_loop():
    """Background loop to auto-generate wallets at configured rate."""
    while True:
        rate = app.config.get('AUTO_GEN_RATE', 0) or 0
        save_if = app.config.get('SAVE_IF_BALANCE', False)
        if rate <= 0:
            time.sleep(0.5)
            continue
        interval = 1.0 / max(min(int(rate), 30), 1)
        try:
            mnemo = Mnemonic('english')
            mnemonic = mnemo.generate(strength=128)
            seed_bytes = Bip39SeedGenerator(mnemonic).Generate()
            btc_ctx = Bip86.FromSeed(seed_bytes, Bip86Coins.BITCOIN)
            btc_ctx = btc_ctx.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
            btc_addr = btc_ctx.PublicKey().ToAddress()
            eth_ctx = Bip44.FromSeed(seed_bytes, Bip44Coins.ETHEREUM).DeriveDefaultPath()
            eth_addr = eth_ctx.PublicKey().ToAddress()
            sol_ctx = Bip44.FromSeed(seed_bytes, Bip44Coins.SOLANA).Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT)
            sol_addr = sol_ctx.PublicKey().ToAddress()
            # Query Ankr API
            ANKR_URL = "https://rpc.ankr.com/multichain"
            payload = {
                "jsonrpc": "2.0",
                "method": "ankr_getAccountBalance",
                "params": {
                    "walletAddress": [btc_addr, eth_addr, sol_addr],
                    "blockchain": ["bitcoin", "ethereum", "solana"]
                },
                "id": 1
            }
            try:
                r = requests.post(ANKR_URL, json=payload, timeout=10)
                data = r.json()
                balances = {c['blockchain']: c['balance'] for c in data.get('result', {}).get('assets', [])}
            except Exception:
                balances = {"bitcoin": "0.0", "ethereum": "0.0", "solana": "0.0"}
            def fix_balance(val):
                return '0.0' if val in ['N/A', None, '', 'error'] else val
            btc_bal = fix_balance(balances.get('bitcoin', 'N/A'))
            eth_bal = fix_balance(balances.get('ethereum', 'N/A'))
            sol_bal = fix_balance(balances.get('solana', 'N/A'))
            should_save = True
            if save_if:
                try:
                    should_save = (float(btc_bal) > 0) or (float(eth_bal) > 0) or (float(sol_bal) > 0)
                except Exception:
                    should_save = False
            if should_save:
                data_store.save_result(mnemonic, btc_addr, eth_addr, sol_addr)
            # record check regardless
            try:
                data_store.save_check(mnemonic, btc_addr, eth_addr, sol_addr, saved=should_save)
            except Exception:
                pass
        except Exception:
            pass
        time.sleep(interval)


def start_auto_gen_thread():
    t = threading.Thread(target=auto_gen_loop, daemon=True)
    t.start()
    return t


if __name__ == '__main__':
    print(f"Starting Flask app on port {PORT}")
    # Start background auto-gen thread
    start_auto_gen_thread()
    app.run(host='0.0.0.0', port=PORT)
