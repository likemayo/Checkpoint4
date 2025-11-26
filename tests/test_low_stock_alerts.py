import os
import sqlite3
import pytest

from src.product_repo import AProductRepo
from src.app import create_app

def get_conn():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

def seed_products(conn):
    conn.execute('''CREATE TABLE product (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        price_cents INTEGER NOT NULL,
        stock INTEGER NOT NULL,
        active INTEGER NOT NULL DEFAULT 1,
        flash_sale_active INTEGER DEFAULT 0,
        flash_sale_price_cents INTEGER
    )''')
    # Active products varying stock
    conn.execute("INSERT INTO product(name, price_cents, stock, active) VALUES(?,?,?,1)", ("AAA", 100, 10))
    conn.execute("INSERT INTO product(name, price_cents, stock, active) VALUES(?,?,?,1)", ("BBB", 200, 5))
    conn.execute("INSERT INTO product(name, price_cents, stock, active) VALUES(?,?,?,1)", ("CCC", 300, 2))
    # Inactive low stock should be ignored
    conn.execute("INSERT INTO product(name, price_cents, stock, active) VALUES(?,?,?,0)", ("ZZZ", 400, 1))
    conn.commit()

def test_get_low_stock_products():
    conn = get_conn()
    seed_products(conn)
    repo = AProductRepo(conn)
    low = repo.get_low_stock_products(5)
    names = [p['name'] for p in low]
    assert 'BBB' in names
    assert 'CCC' in names
    assert 'AAA' not in names  # stock above threshold
    assert 'ZZZ' not in names  # inactive
    # Ordered ascending by stock
    stocks = [p['stock'] for p in low]
    assert stocks == sorted(stocks)
    conn.close()

def test_app_config_low_stock_threshold_env(monkeypatch):
    monkeypatch.setenv('LOW_STOCK_THRESHOLD', '12')
    app = create_app()
    assert app.config['LOW_STOCK_THRESHOLD'] == 12
