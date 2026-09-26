import os
import requests
import pandas as pd
from flask import Flask, render_template, jsonify
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

API_TOKEN = os.getenv("COT_API_TOKEN")
LEGACY_URL = "https://publicreporting.cftc.gov/api/v3/views/6dca-aqww/query.json"
TFF_URL = "https://publicreporting.cftc.gov/api/v3/views/gpe5-46if/query.json"

ASSET_CONFIGS = {
    "USD": {"code": "098662", "name": "USD INDEX - ICE", "invert": True},
    "EUR": {"code": "099741", "name": "EURO FX", "invert": False},
    "GBP": {"code": "096742", "name": "BRITISH POUND", "invert": False},
    "JPY": {"code": "097741", "name": "JAPANESE YEN", "invert": False},
    "AUD": {"code": "232741", "name": "AUSTRALIAN DOLLAR", "invert": False},
    "CAD": {"code": "090741", "name": "CANADIAN DOLLAR", "invert": False},
    "CHF": {"code": "092741", "name": "SWISS FRANC", "invert": False},
    "NZD": {"code": "112741", "name": "NEW ZEALAND DOLLAR", "invert": False}
}

@app.route("/api/legacy-net/<symbol>")
def get_legacy_net(symbol):
    cfg = ASSET_CONFIGS.get(symbol.upper())
    if not cfg: return jsonify([])
    headers = {"Content-Type": "application/json", "X-App-Token": API_TOKEN if API_TOKEN else ""}
    soql_query = f"SELECT * WHERE `cftc_contract_market_code` = '{cfg['code']}' ORDER BY `report_date_as_yyyy_mm_dd` DESC"
    payload = {"query": soql_query, "page": {"pageNumber": 1, "pageSize": 55}, "includeSynthetic": False}
    try:
        res = requests.post(LEGACY_URL, headers=headers, json=payload)
        if res.status_code != 200: return jsonify([])
        df = pd.DataFrame(res.json()).iloc[::-1].reset_index(drop=True)
        out = []
        for _, row in df.iterrows():
            date_str = str(row.get('report_date_as_yyyy_mm_dd', ''))[:10]
            comm_net = float(row.get('comm_positions_long_all', 0) or 0) - float(row.get('comm_positions_short_all', 0) or 0)
            large_net = float(row.get('noncomm_positions_long_all', 0) or 0) - float(row.get('noncomm_positions_short_all', 0) or 0)
            small_net = float(row.get('nonrept_positions_long_all', 0) or 0) - float(row.get('nonrept_positions_short_all', 0) or 0)
            out.append({"date": date_str, "commercials": comm_net, "large_speculators": large_net, "small_traders": small_net})
        return jsonify(out)
    except Exception as e:
        print(e); return jsonify([])

@app.route("/api/tff-net/<symbol>")
def get_tff_net(symbol):
    cfg = ASSET_CONFIGS.get(symbol.upper())
    if not cfg: return jsonify([])
    headers = {"Content-Type": "application/json", "X-App-Token": API_TOKEN if API_TOKEN else ""}
    soql_query = f"SELECT * WHERE `cftc_contract_market_code` = '{cfg['code']}' ORDER BY `report_date_as_yyyy_mm_dd` DESC"
    payload = {"query": soql_query, "page": {"pageNumber": 1, "pageSize": 55}, "includeSynthetic": False}
    try:
        res = requests.post(TFF_URL, headers=headers, json=payload)
        if res.status_code != 200: return jsonify([])
        df = pd.DataFrame(res.json()).iloc[::-1].reset_index(drop=True)
        out = []
        for _, row in df.iterrows():
            date_str = str(row.get('report_date_as_yyyy_mm_dd', ''))[:10]
            dealers = float(row.get('dealer_positions_long_all', 0) or 0) - float(row.get('dealer_positions_short_all', 0) or 0)
            asset_mgrs = float(row.get('asset_mgr_positions_long', 0) or 0) - float(row.get('asset_mgr_positions_short', 0) or 0)
            leveraged = float(row.get('lev_money_positions_long', 0) or 0) - float(row.get('lev_money_positions_short', 0) or 0)
            other_rep = float(row.get('other_rept_positions_long', 0) or 0) - float(row.get('other_rept_positions_short', 0) or 0)
            out.append({"date": date_str, "dealers": dealers, "asset_managers": asset_mgrs, "leveraged_funds": leveraged, "other_reportables": other_rep})
        return jsonify(out)
    except Exception as e:
        print(e); return jsonify([])

@app.route("/api/cot-index/<symbol>")
def get_cot_index(symbol):
    cfg = ASSET_CONFIGS.get(symbol.upper())
    if not cfg: return jsonify([])
    headers = {"Content-Type": "application/json", "X-App-Token": API_TOKEN if API_TOKEN else ""}
    soql_query = f"SELECT * WHERE `cftc_contract_market_code` = '{cfg['code']}' ORDER BY `report_date_as_yyyy_mm_dd` DESC"
    payload = {"query": soql_query, "page": {"pageNumber": 1, "pageSize": 160}, "includeSynthetic": False}
    try:
        res = requests.post(LEGACY_URL, headers=headers, json=payload)
        if res.status_code != 200: return jsonify([])
        df = pd.DataFrame(res.json()).iloc[::-1].reset_index(drop=True)
        df['net'] = df.apply(lambda r: float(r.get('comm_positions_long_all', 0) or 0) - float(r.get('comm_positions_short_all', 0) or 0), axis=1)
        
        out = []
        for i in range(len(df)):
            date_str = str(df.loc[i, 'report_date_as_yyyy_mm_dd'])[:10]
            curr_net = df.loc[i, 'net']
            
            w6 = df.loc[max(0, i-26):i, 'net']
            min_6, max_6 = w6.min(), w6.max()
            idx_6 = round(((curr_net - min_6) / (max_6 - min_6)) * 100, 1) if max_6 != min_6 else 50.0
            
            w36 = df.loc[max(0, i-156):i, 'net']
            min_36, max_36 = w36.min(), w36.max()
            idx_36 = round(((curr_net - min_36) / (max_36 - min_36)) * 100, 1) if max_36 != min_36 else 50.0
            
            if i >= 12:
                out.append({"date": date_str, "index_6m": idx_6, "index_36m": idx_36})
        return jsonify(out)
    except Exception as e:
        print(e); return jsonify([])

@app.route("/api/cot-history/<symbol>")
def get_cot_history(symbol):
    cfg = ASSET_CONFIGS.get(symbol.upper())
    if not cfg: return jsonify([])
    headers = {"Content-Type": "application/json", "X-App-Token": API_TOKEN if API_TOKEN else ""}
    soql_query = f"SELECT * WHERE `cftc_contract_market_code` = '{cfg['code']}' ORDER BY `report_date_as_yyyy_mm_dd` DESC"
    payload = {"query": soql_query, "page": {"pageNumber": 1, "pageSize": 52}, "includeSynthetic": False}
    try:
        res = requests.post(LEGACY_URL, headers=headers, json=payload)
        if res.status_code != 200: return jsonify([])
        df = pd.DataFrame(res.json()).iloc[::-1].reset_index(drop=True)
        out = []
        for _, row in df.iterrows():
            date_str = str(row.get('report_date_as_yyyy_mm_dd', ''))[:10]
            longs = float(row.get('noncomm_positions_long_all', 0) or 0)
            shorts = float(row.get('noncomm_positions_short_all', 0) or 0)
            total = longs + shorts
            long_pct = round((longs / total) * 100, 1) if total > 0 else 50.0
            out.append({"date": date_str, "longs": longs, "shorts": shorts, "long_pct": long_pct})
        return jsonify(out)
    except Exception as e:
        print(e); return jsonify([])

@app.route("/api/latest-summary")
def get_latest_summary():
    summary_data = []
    headers = {"Content-Type": "application/json", "X-App-Token": API_TOKEN if API_TOKEN else ""}
    for symbol, cfg in ASSET_CONFIGS.items():
        soql_query = f"SELECT * WHERE `cftc_contract_market_code` = '{cfg['code']}' ORDER BY `report_date_as_yyyy_mm_dd` DESC"
        payload = {"query": soql_query, "page": {"pageNumber": 1, "pageSize": 1}, "includeSynthetic": False}
        try:
            response = requests.post(LEGACY_URL, headers=headers, json=payload)
            if response.status_code == 200 and response.json():
                row = response.json()[0]
                longs = float(row.get('noncomm_positions_long_all', 0) or 0)
                shorts = float(row.get('noncomm_positions_short_all', 0) or 0)
                total = longs + shorts
                long_pct = round((longs / total) * 100, 1) if total > 0 else 50.0
                summary_data.append({"symbol": symbol, "long_pct": long_pct, "short_pct": round(100.0 - long_pct, 1)})
        except Exception:
            pass
    summary_data.sort(key=lambda x: x['long_pct'])
    return jsonify(summary_data)

@app.route("/api/table/<table_type>/<symbol>")
def get_table_data(table_type, symbol):
    cfg = ASSET_CONFIGS.get(symbol.upper())
    if not cfg: return jsonify([])
    url = TFF_URL if table_type.lower() == 'tff' else LEGACY_URL
    headers = {"Content-Type": "application/json", "X-App-Token": API_TOKEN if API_TOKEN else ""}
    soql_query = f"SELECT * WHERE `cftc_contract_market_code` = '{cfg['code']}' ORDER BY `report_date_as_yyyy_mm_dd` DESC"
    payload = {"query": soql_query, "page": {"pageNumber": 1, "pageSize": 100}, "includeSynthetic": False}
    try:
        res = requests.post(url, headers=headers, json=payload)
        return jsonify(res.json() if res.status_code == 200 else [])
    except Exception:
        return jsonify([])

@app.route("/")
def index():
    return render_template("index.html", symbols=list(ASSET_CONFIGS.keys()))

if __name__ == "__main__":
    app.run(debug=True, port=5020)