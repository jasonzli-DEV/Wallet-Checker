import sqlite3
from contextlib import closing

def init_db():
    with closing(sqlite3.connect('results.db')) as conn:
        with conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mnemonic TEXT,
                    btc TEXT,
                    eth TEXT,
                    sol TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mnemonic TEXT,
                    btc TEXT,
                    eth TEXT,
                    sol TEXT,
                    saved INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

def save_result(mnemonic, btc, eth, sol):
    with closing(sqlite3.connect('results.db')) as conn:
        with conn:
            conn.execute(
                'INSERT INTO results (mnemonic, btc, eth, sol) VALUES (?, ?, ?, ?)',
                (mnemonic, btc, eth, sol)
            )


def save_check(mnemonic, btc, eth, sol, saved=False):
    with closing(sqlite3.connect('results.db')) as conn:
        with conn:
            conn.execute(
                'INSERT INTO checks (mnemonic, btc, eth, sol, saved) VALUES (?, ?, ?, ?, ?)',
                (mnemonic, btc, eth, sol, 1 if saved else 0)
            )

def get_results(limit=20):
    with closing(sqlite3.connect('results.db')) as conn:
        cur = conn.cursor()
        cur.execute('SELECT mnemonic, btc, eth, sol, created_at FROM results ORDER BY id DESC LIMIT ?', (limit,))
        return cur.fetchall()


def save_settings(auto_generate, save_if_balance):
    with closing(sqlite3.connect('results.db')) as conn:
        with conn:
            conn.execute('REPLACE INTO settings (key, value) VALUES (?, ?)', ('auto_generate', str(int(auto_generate))))
            conn.execute('REPLACE INTO settings (key, value) VALUES (?, ?)', ('save_if_balance', '1' if save_if_balance else '0'))


def get_settings():
    with closing(sqlite3.connect('results.db')) as conn:
        cur = conn.cursor()
        cur.execute('SELECT key, value FROM settings')
        rows = {k: v for k, v in cur.fetchall()}
        auto = int(rows.get('auto_generate', '0'))
        save = rows.get('save_if_balance', '0') == '1'
        return {'auto_generate': auto, 'save_if_balance': save}


def clear_results():
    with closing(sqlite3.connect('results.db')) as conn:
        with conn:
            conn.execute('DELETE FROM results')

if __name__ == '__main__':
    init_db()
