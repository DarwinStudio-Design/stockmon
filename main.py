"""
Stock Monitor Bot v3.0 - Multi-User Config-Driven
==================================================
Ogni utente ha la propria watchlist separata.
Registrazione via Telegram /start.
"""

import os
import re
import yaml
import httpx
import secrets
import yfinance as yf
from datetime import datetime
from typing import Optional, List, Dict
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse

# ============== CONFIG ==============

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
USERS_FILE = Path("users.yaml")

# ============== USER MANAGER ==============

class UserManager:
    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.data = self._load()

    def _load(self) -> dict:
        if self.filepath.exists():
            with open(self.filepath, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {"users": {}}
        return {"users": {}}

    def save(self):
        with open(self.filepath, 'w', encoding='utf-8') as f:
            yaml.dump(self.data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    def get_all_users(self) -> Dict[str, dict]:
        return self.data.get("users", {})

    def get_user_by_token(self, token: str) -> Optional[dict]:
        return self.data.get("users", {}).get(token)

    def get_user_by_chat_id(self, chat_id: int) -> Optional[tuple]:
        """Ritorna (token, user_data) o None"""
        for token, user in self.data.get("users", {}).items():
            if user.get("chat_id") == chat_id:
                return (token, user)
        return None

    def create_user(self, chat_id: int, username: str = "") -> str:
        """Crea nuovo utente e ritorna il token"""
        # Controlla se esiste già
        existing = self.get_user_by_chat_id(chat_id)
        if existing:
            return existing[0]  # Ritorna token esistente

        token = secrets.token_urlsafe(8)  # 11 caratteri
        self.data.setdefault("users", {})[token] = {
            "chat_id": chat_id,
            "username": username,
            "created": datetime.now().isoformat(),
            "watchlist": [],
            "positions": [],
            "history": []
        }
        self.save()
        return token

    def get_watchlist(self, token: str) -> List[dict]:
        user = self.get_user_by_token(token)
        return user.get("watchlist", []) if user else []

    def get_tickers(self, token: str) -> List[str]:
        return [w["ticker"] for w in self.get_watchlist(token)]

    def set_watchlist(self, token: str, watchlist: List[dict]):
        if token in self.data.get("users", {}):
            self.data["users"][token]["watchlist"] = watchlist
            self.save()

    def clear_watchlist(self, token: str):
        self.set_watchlist(token, [])

    def get_stock_config(self, token: str, ticker: str) -> Optional[dict]:
        for stock in self.get_watchlist(token):
            if stock["ticker"].upper() == ticker.upper():
                return stock
        return None

    def get_positions(self, token: str) -> List[dict]:
        user = self.get_user_by_token(token)
        return user.get("positions", []) if user else []

    def add_position(self, token: str, position: dict):
        if token in self.data.get("users", {}):
            self.data["users"][token].setdefault("positions", []).append(position)
            self.save()

    def get_open_position(self, token: str, ticker: str) -> Optional[dict]:
        for pos in self.get_positions(token):
            if pos["ticker"].upper() == ticker.upper() and pos.get("status") == "OPEN":
                return pos
        return None

    def close_position(self, token: str, ticker: str, exit_price: float, reason: str):
        user = self.get_user_by_token(token)
        if not user:
            return
        for pos in user.get("positions", []):
            if pos["ticker"].upper() == ticker.upper() and pos.get("status") == "OPEN":
                pos["status"] = reason
                pos["exit_price"] = exit_price
                pos["exit_date"] = datetime.now().isoformat()
                pos["pnl_pct"] = round((exit_price / pos["entry_price"] - 1) * 100, 2)
                user.setdefault("history", []).append(pos.copy())
        user["positions"] = [p for p in user.get("positions", []) if p.get("status") == "OPEN"]
        self.save()

    def get_history(self, token: str) -> List[dict]:
        user = self.get_user_by_token(token)
        return user.get("history", []) if user else []

    def get_chat_id(self, token: str) -> Optional[int]:
        user = self.get_user_by_token(token)
        return user.get("chat_id") if user else None

um = UserManager(USERS_FILE)

# ============== TELEGRAM ==============

async def send_telegram(message: str, chat_id: int = None) -> bool:
    if not TELEGRAM_TOKEN:
        print(f"[TG] Token mancante")
        return False
    if not chat_id:
        print(f"[TG] Chat ID mancante")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }, timeout=10)
            return r.status_code == 200
    except Exception as e:
        print(f"[TG] Errore: {e}")
        return False

# ============== MARKET DATA ==============

def fetch_stock_data(ticker: str) -> dict:
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d")

        if hist.empty:
            return {"error": f"Nessun dato per {ticker}", "ticker": ticker}

        current = float(hist['Close'].iloc[-1])
        prev_close = float(hist['Close'].iloc[-2]) if len(hist) > 1 else current
        daily_change = ((current - prev_close) / prev_close) * 100

        return {
            "ticker": ticker,
            "price": round(current, 2),
            "prev_close": round(prev_close, 2),
            "daily_change_pct": round(daily_change, 2),
            "volume": int(hist['Volume'].iloc[-1]),
            "high_5d": round(float(hist['High'].max()), 2),
            "low_5d": round(float(hist['Low'].min()), 2)
        }
    except Exception as e:
        return {"error": str(e), "ticker": ticker}

# ============== SIGNAL ENGINE ==============

def check_entry_signal(data: dict, config: dict) -> dict:
    rules = config.get("entry_rules", {})
    price = data["price"]
    change = data["daily_change_pct"]
    volume = data["volume"]

    checks = []
    passed = True

    if rules.get("breakout_above", 0) > 0:
        ok = price > rules["breakout_above"]
        checks.append(f"Breakout >${rules['breakout_above']}: {'✅' if ok else '❌'}")
        passed = passed and ok

    if rules.get("min_daily_change_pct", 0) > 0:
        ok = change >= rules["min_daily_change_pct"]
        checks.append(f"Change >={rules['min_daily_change_pct']}%: {'✅' if ok else '❌'}")
        passed = passed and ok

    if rules.get("min_volume", 0) > 0:
        ok = volume >= rules["min_volume"]
        checks.append(f"Volume >={rules['min_volume']:,}: {'✅' if ok else '❌'}")
        passed = passed and ok

    return {"signal": "ENTRY" if passed else "NO_ENTRY", "checks": checks, "passed": passed}

def check_exit_signal(data: dict, config: dict, position: dict) -> dict:
    rules = config.get("exit_rules", {})
    price = data["price"]
    entry_price = position["entry_price"]
    entry_date = datetime.fromisoformat(position["entry_date"])
    days_held = (datetime.now() - entry_date).days
    pnl_pct = (price / entry_price - 1) * 100

    if rules.get("stop_loss_pct", 0) > 0 and pnl_pct <= -rules["stop_loss_pct"]:
        return {"signal": "EXIT", "reason": "STOP_LOSS", "pnl_pct": round(pnl_pct, 2), "message": f"🛑 STOP LOSS: {pnl_pct:.1f}%"}

    if rules.get("target_pct", 0) > 0 and pnl_pct >= rules["target_pct"]:
        return {"signal": "EXIT", "reason": "TARGET", "pnl_pct": round(pnl_pct, 2), "message": f"🎯 TARGET: +{pnl_pct:.1f}%"}

    if rules.get("max_hold_days", 0) > 0 and days_held >= rules["max_hold_days"]:
        return {"signal": "EXIT", "reason": "MAX_DAYS", "pnl_pct": round(pnl_pct, 2), "message": f"⏰ TIMEOUT: {pnl_pct:+.1f}%"}

    return {"signal": "HOLD", "pnl_pct": round(pnl_pct, 2)}

def check_alerts(data: dict, config: dict) -> List[str]:
    alerts_cfg = config.get("alerts", {})
    price = data["price"]
    change = data["daily_change_pct"]
    alerts = []

    if alerts_cfg.get("price_above", 0) > 0 and price > alerts_cfg["price_above"]:
        alerts.append(f"📈 Sopra ${alerts_cfg['price_above']}")
    if alerts_cfg.get("price_below", 0) > 0 and price < alerts_cfg["price_below"]:
        alerts.append(f"📉 Sotto ${alerts_cfg['price_below']}")
    if alerts_cfg.get("daily_change_above", 0) > 0 and change > alerts_cfg["daily_change_above"]:
        alerts.append(f"🚀 Pump +{change:.1f}%")
    if alerts_cfg.get("daily_change_below", 0) < 0 and change < alerts_cfg["daily_change_below"]:
        alerts.append(f"💥 Dump {change:.1f}%")

    return alerts

# ============== CHECK PER SINGOLO UTENTE ==============

async def check_user_markets(token: str) -> dict:
    """Controlla i mercati per un singolo utente"""
    results = []
    alerts_sent = 0
    chat_id = um.get_chat_id(token)

    for config in um.get_watchlist(token):
        ticker = config["ticker"]
        data = fetch_stock_data(ticker)

        if "error" in data:
            continue

        position = um.get_open_position(token, ticker)

        if position:
            exit_sig = check_exit_signal(data, config, position)
            if exit_sig["signal"] == "EXIT":
                msg = f"🔴 <b>EXIT</b> - {ticker}\n\n{exit_sig['message']}\n\nEntry: ${position['entry_price']} → ${data['price']}"
                if await send_telegram(msg, chat_id): alerts_sent += 1
                um.close_position(token, ticker, data["price"], exit_sig["reason"])
                results.append({"ticker": ticker, "action": "EXIT"})
            else:
                results.append({"ticker": ticker, "action": "HOLD", "pnl": exit_sig["pnl_pct"]})
        else:
            entry_sig = check_entry_signal(data, config)
            if entry_sig["passed"]:
                rules = config.get("exit_rules", {})
                stop = round(data["price"] * (1 - rules.get("stop_loss_pct", 15) / 100), 2)
                target = round(data["price"] * (1 + rules.get("target_pct", 30) / 100), 2)

                msg = f"""🟢 <b>ENTRY SIGNAL</b> - {ticker}

💰 ${data['price']} ({data['daily_change_pct']:+.1f}%)
📋 {config.get('thesis', '')}

✅ {' | '.join(entry_sig['checks'])}

Entry: ${data['price']}
Stop: ${stop} | Target: ${target}"""
                if await send_telegram(msg, chat_id): alerts_sent += 1
                results.append({"ticker": ticker, "action": "ENTRY_SIGNAL"})
            else:
                alerts = check_alerts(data, config)
                if alerts:
                    msg = f"⚡ <b>{ticker}</b> ${data['price']}\n" + "\n".join(alerts)
                    if await send_telegram(msg, chat_id): alerts_sent += 1
                results.append({"ticker": ticker, "action": "WATCH"})

    return {"timestamp": datetime.now().isoformat(), "alerts_sent": alerts_sent, "results": results}

# ============== CHECK TUTTI GLI UTENTI ==============

async def check_all_users() -> dict:
    """Controlla i mercati per tutti gli utenti"""
    print(f"\n[CRON CHECK] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    total_alerts = 0
    users_checked = 0

    for token, user in um.get_all_users().items():
        if um.get_watchlist(token):
            print(f"  [User {token[:6]}...] {len(um.get_watchlist(token))} tickers")
            result = await check_user_markets(token)
            total_alerts += result["alerts_sent"]
            users_checked += 1

    return {"users_checked": users_checked, "total_alerts": total_alerts}

# ============== FASTAPI ==============

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[STARTUP] Stock Monitor v3.0 Multi-User")
    print(f"[STARTUP] {len(um.get_all_users())} utenti registrati")
    yield

app = FastAPI(title="Stock Monitor", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ============== ENDPOINT PUBBLICI ==============

@app.get("/health")
async def health():
    return {"status": "ok", "users": len(um.get_all_users())}

@app.get("/")
async def root():
    return {"message": "Stock Monitor v3.0", "docs": "Usa Telegram per registrarti: /start"}

# ============== CRON ==============

@app.post("/cron/check")
async def cron():
    now = datetime.utcnow()
    if now.weekday() >= 5 or not (14 <= now.hour < 21):
        return {"status": "skipped", "reason": "Mercato chiuso"}
    return await check_all_users()

# ============== TELEGRAM WEBHOOK ==============

@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        message = data.get("message", {})
        text = message.get("text", "")
        chat_id = message.get("chat", {}).get("id")
        username = message.get("from", {}).get("username", "")

        if not text or not chat_id:
            return {"ok": True}

        # Comando /start - Registrazione
        if text.strip().lower() == "/start":
            token = um.create_user(chat_id, username)
            base_url = os.getenv("RAILWAY_PUBLIC_DOMAIN", "localhost:8000")
            dashboard_url = f"https://{base_url}/d/{token}"

            msg = f"""🎉 <b>Benvenuto in Stock Monitor!</b>

Il tuo link dashboard personale:
<code>{dashboard_url}</code>

<b>Comandi:</b>
/status - Vedi la tua watchlist
/check - Forza controllo mercati
/clear - Svuota watchlist

Oppure incolla direttamente uno YAML generato da AI."""
            await send_telegram(msg, chat_id)
            return {"ok": True}

        # Trova l'utente dal chat_id
        user_info = um.get_user_by_chat_id(chat_id)
        if not user_info:
            await send_telegram("⚠️ Non sei registrato. Invia /start per registrarti.", chat_id)
            return {"ok": True}

        token, user = user_info

        # Comando /status
        if text.strip().lower() == "/status":
            tickers = um.get_tickers(token)
            positions = um.get_positions(token)
            msg = f"📊 <b>STATUS</b>\n\nWatchlist: {', '.join(tickers) if tickers else 'vuota'}\nPosizioni: {len(positions)}"
            await send_telegram(msg, chat_id)
            return {"ok": True}

        # Comando /check
        if text.strip().lower() == "/check":
            result = await check_user_markets(token)
            await send_telegram(f"✅ Check completato. Alert inviati: {result['alerts_sent']}", chat_id)
            return {"ok": True}

        # Comando /clear
        if text.strip().lower() == "/clear":
            um.clear_watchlist(token)
            await send_telegram("🗑 Watchlist svuotata", chat_id)
            return {"ok": True}

        # Comando /link - Mostra link dashboard
        if text.strip().lower() == "/link":
            base_url = os.getenv("RAILWAY_PUBLIC_DOMAIN", "localhost:8000")
            dashboard_url = f"https://{base_url}/d/{token}"
            await send_telegram(f"🔗 La tua dashboard:\n<code>{dashboard_url}</code>", chat_id)
            return {"ok": True}

        # Se contiene "watchlist:" probabilmente è YAML
        if "watchlist:" in text.lower():
            try:
                yaml_text = clean_yaml_input(text)
                parsed = yaml.safe_load(yaml_text)

                if "watchlist" in parsed:
                    watchlist = parsed["watchlist"]
                    for stock in watchlist:
                        stock["ticker"] = str(stock["ticker"]).strip().upper()
                    um.set_watchlist(token, watchlist)
                    tickers = um.get_tickers(token)
                    await send_telegram(f"✅ <b>CONFIG APPLICATA!</b>\n\nNuova watchlist: {', '.join(tickers)}", chat_id)
                else:
                    await send_telegram("❌ YAML non valido: manca 'watchlist'", chat_id)
            except Exception as e:
                await send_telegram(f"❌ Errore parsing YAML: {e}", chat_id)
            return {"ok": True}

        # Messaggio non riconosciuto
        await send_telegram("Comandi: /start, /status, /check, /clear, /link\n\nOppure incolla uno YAML.", chat_id)

    except Exception as e:
        print(f"[Webhook] Errore: {e}")

    return {"ok": True}

@app.get("/telegram/setup")
async def telegram_setup():
    base_url = os.getenv("RAILWAY_PUBLIC_DOMAIN", "TUO-DOMINIO.up.railway.app")
    webhook_url = f"https://{base_url}/telegram/webhook"
    setup_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={webhook_url}"

    return {
        "istruzioni": "Apri questo URL nel browser per attivare il webhook:",
        "setup_url": setup_url if TELEGRAM_TOKEN else "TELEGRAM_TOKEN non configurato",
        "webhook_url": webhook_url
    }

# ============== API PER DASHBOARD (con token) ==============

def clean_yaml_input(text: str) -> str:
    text = re.sub(r'```ya?ml?\n?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'```\n?', '', text)
    match = re.search(r'^watchlist:', text, re.MULTILINE)
    if match:
        text = text[match.start():]
    return text.strip()

@app.get("/api/{token}/status")
async def api_status(token: str):
    user = um.get_user_by_token(token)
    if not user:
        raise HTTPException(404, "Token non valido")

    data = {}
    for config in um.get_watchlist(token):
        ticker = config["ticker"]
        data[ticker] = {
            "market": fetch_stock_data(ticker),
            "config": config,
            "position": um.get_open_position(token, ticker)
        }
    return {"watchlist": data, "positions": um.get_positions(token), "history": um.get_history(token)[-10:]}

@app.get("/api/{token}/config/yaml")
async def api_get_yaml(token: str):
    user = um.get_user_by_token(token)
    if not user:
        raise HTTPException(404, "Token non valido")
    return {"yaml": yaml.dump({"watchlist": um.get_watchlist(token)}, default_flow_style=False, allow_unicode=True)}

@app.post("/api/{token}/config/yaml")
async def api_set_yaml(token: str, request: Request):
    user = um.get_user_by_token(token)
    if not user:
        raise HTTPException(404, "Token non valido")

    body = await request.body()
    try:
        raw_text = body.decode('utf-8')
        cleaned = clean_yaml_input(raw_text)
        parsed = yaml.safe_load(cleaned)

        if not parsed or "watchlist" not in parsed:
            raise HTTPException(400, "YAML deve contenere 'watchlist:'")

        watchlist = parsed["watchlist"]
        if not isinstance(watchlist, list):
            raise HTTPException(400, "watchlist deve essere una lista")

        for stock in watchlist:
            if "ticker" not in stock:
                raise HTTPException(400, "Ogni stock deve avere 'ticker'")
            stock["ticker"] = str(stock["ticker"]).strip().upper()

        um.set_watchlist(token, watchlist)
        tickers = um.get_tickers(token)
        chat_id = um.get_chat_id(token)
        if chat_id:
            await send_telegram(f"📋 <b>NUOVA CONFIG</b>\n\n{', '.join(tickers)}", chat_id)
        return {"status": "ok", "tickers": tickers}
    except yaml.YAMLError as e:
        raise HTTPException(400, f"YAML non valido: {e}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Errore: {e}")

@app.post("/api/{token}/config/clear")
async def api_clear(token: str):
    user = um.get_user_by_token(token)
    if not user:
        raise HTTPException(404, "Token non valido")
    um.clear_watchlist(token)
    return {"status": "ok"}

@app.post("/api/{token}/check")
async def api_check(token: str):
    user = um.get_user_by_token(token)
    if not user:
        raise HTTPException(404, "Token non valido")
    return await check_user_markets(token)

@app.post("/api/{token}/test")
async def api_test(token: str):
    chat_id = um.get_chat_id(token)
    if not chat_id:
        raise HTTPException(404, "Token non valido")
    return {"success": await send_telegram(f"🧪 Test OK - {datetime.now().strftime('%H:%M:%S')}", chat_id)}

@app.post("/api/{token}/position/enter")
async def api_enter(token: str, ticker: str, price: Optional[float] = None):
    user = um.get_user_by_token(token)
    if not user:
        raise HTTPException(404, "Token non valido")

    config = um.get_stock_config(token, ticker)
    if not config:
        raise HTTPException(404, f"{ticker} non in watchlist")
    if um.get_open_position(token, ticker):
        raise HTTPException(400, "Già in posizione")

    if not price:
        data = fetch_stock_data(ticker)
        if "error" in data:
            raise HTTPException(500, data["error"])
        price = data["price"]

    rules = config.get("exit_rules", {})
    position = {
        "ticker": ticker,
        "entry_price": price,
        "entry_date": datetime.now().isoformat(),
        "stop_loss": round(price * (1 - rules.get("stop_loss_pct", 15) / 100), 2),
        "target": round(price * (1 + rules.get("target_pct", 30) / 100), 2),
        "status": "OPEN"
    }
    um.add_position(token, position)

    chat_id = um.get_chat_id(token)
    if chat_id:
        await send_telegram(f"📝 <b>ENTRATO</b> {ticker} @ ${price}", chat_id)
    return {"status": "ok", "position": position}

@app.post("/api/{token}/position/exit")
async def api_exit(token: str, ticker: str):
    user = um.get_user_by_token(token)
    if not user:
        raise HTTPException(404, "Token non valido")

    position = um.get_open_position(token, ticker)
    if not position:
        raise HTTPException(404, "Nessuna posizione")

    data = fetch_stock_data(ticker)
    price = data.get("price", position["entry_price"])
    pnl = (price / position["entry_price"] - 1) * 100
    um.close_position(token, ticker, price, "MANUAL")

    chat_id = um.get_chat_id(token)
    if chat_id:
        await send_telegram(f"📝 <b>USCITO</b> {ticker} @ ${price}\nP&L: {pnl:+.1f}%", chat_id)
    return {"status": "ok", "pnl_pct": round(pnl, 2)}

# ============== DASHBOARD ==============

@app.get("/d/{token}", response_class=HTMLResponse)
async def dashboard(token: str):
    user = um.get_user_by_token(token)
    if not user:
        return HTMLResponse("<h1>Token non valido</h1><p>Invia /start al bot Telegram per registrarti.</p>", status_code=404)

    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="apple-mobile-web-app-capable" content="yes"><meta name="theme-color" content="#0f172a">
<title>Stock Monitor</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh;padding:16px;padding-bottom:200px}}
.header{{text-align:center;padding:20px 0;margin-bottom:20px}}
.header h1{{font-size:22px;margin-bottom:4px}}
.sub{{font-size:12px;color:#64748b}}
.section{{margin-bottom:24px}}
.section-title{{font-size:13px;color:#64748b;margin-bottom:12px;text-transform:uppercase}}
.card{{background:#1e293b;border-radius:16px;padding:16px;margin-bottom:12px}}
.card-header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}}
.ticker{{font-size:20px;font-weight:700}}
.status{{font-size:11px;padding:4px 10px;border-radius:12px;font-weight:600}}
.status-watch{{background:#fbbf24;color:#0f172a}}
.status-open{{background:#22c55e}}
.price-row{{display:flex;justify-content:space-between;align-items:baseline}}
.price{{font-size:28px;font-weight:700}}
.change{{font-size:16px;font-weight:600}}
.positive{{color:#22c55e}}.negative{{color:#ef4444}}
.thesis{{font-size:13px;color:#94a3b8;margin-top:12px;padding-top:12px;border-top:1px solid #334155}}
.levels{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px}}
.level{{background:#0f172a;padding:8px;border-radius:8px;font-size:12px}}
.level-label{{color:#64748b}}.level-value{{font-weight:600;margin-top:2px}}
.pnl{{font-size:24px;font-weight:700;text-align:center;padding:12px}}
.actions{{position:fixed;bottom:0;left:0;right:0;background:rgba(15,23,42,0.95);backdrop-filter:blur(10px);padding:12px 16px;display:flex;flex-direction:column;gap:8px}}
.row{{display:flex;gap:8px}}
.btn{{flex:1;padding:14px;border:none;border-radius:12px;font-size:14px;font-weight:600;cursor:pointer}}
.btn:disabled{{opacity:0.5}}
.btn-primary{{background:#3b82f6;color:white}}
.btn-secondary{{background:#334155;color:white}}
.btn-config{{background:linear-gradient(135deg,#8b5cf6,#6366f1);color:white}}
.btn-prompt{{background:linear-gradient(135deg,#f59e0b,#d97706);color:white}}
.empty{{text-align:center;padding:40px;color:#64748b}}
.modal{{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.9);padding:16px;z-index:100;overflow-y:auto}}
.modal.active{{display:block}}
.modal textarea{{width:100%;height:250px;background:#0f172a;border:1px solid #334155;color:#e2e8f0;padding:12px;border-radius:8px;font-family:monospace;font-size:11px}}
.modal-btns{{display:flex;gap:8px;margin-top:12px}}
.modal select,.modal input{{width:100%;background:#0f172a;border:1px solid #334155;color:#e2e8f0;padding:10px;border-radius:8px;margin-bottom:8px}}
.copied{{background:#22c55e !important}}
.help-text{{font-size:12px;color:#64748b;margin:12px 0}}
</style>
</head>
<body>
<div class="header"><h1>📈 Stock Monitor</h1><div class="sub">La tua dashboard personale</div></div>
<div id="app" class="empty">Caricamento...</div>

<div class="actions">
<div class="row">
<button class="btn btn-prompt" onclick="showPrompt()">📝 Genera Prompt</button>
<button class="btn btn-config" onclick="showCfg()">📋 Incolla YAML</button>
</div>
<div class="row">
<button class="btn btn-secondary" onclick="doCheck()" id="ckBtn">🔄 Check</button>
<button class="btn btn-secondary" onclick="doTest()">🔔 Test</button>
</div>
</div>

<!-- Modal Prompt -->
<div id="promptModal" class="modal">
<div class="card">
<h3 style="margin-bottom:12px">📝 Genera Prompt per AI</h3>
<select id="riskLevel">
<option value="medio">Rischio Medio</option>
<option value="alto" selected>Rischio Alto</option>
<option value="estremo">Rischio Estremo</option>
</select>
<select id="marketCap" multiple style="height:80px">
<option value="large">Large Cap (>$10B)</option>
<option value="mid">Mid Cap ($2B-$10B)</option>
<option value="small" selected>Small Cap ($300M-$2B)</option>
<option value="penny">Penny Stock (<$5)</option>
</select>
<div class="help-text" style="margin:4px 0;font-size:11px">Ctrl+click per selezione multipla</div>
<input type="text" id="sectorFocus" placeholder="Settore (opzionale): crypto, biotech, tech...">
<input type="number" id="numStocks" value="2" min="1" max="5" placeholder="Numero stock (1-5)">
<div class="help-text">1. Clicca "Copia Prompt"<br>2. Incollalo su ChatGPT/Claude/Gemini/Grok<br>3. Copia la risposta YAML<br>4. Torna qui e clicca "📋 Incolla YAML"</div>
<textarea id="promptText" readonly></textarea>
<div class="modal-btns">
<button class="btn btn-secondary" onclick="hidePrompt()">Chiudi</button>
<button class="btn btn-primary" id="copyPromptBtn" onclick="copyPrompt()">📋 Copia Prompt</button>
</div>
</div>
</div>

<!-- Modal Config -->
<div id="cfgModal" class="modal">
<div class="card">
<h3 style="margin-bottom:12px">📋 Incolla YAML dall'AI</h3>
<div class="help-text">Incolla qui la risposta YAML generata da ChatGPT/Claude/Gemini/Grok</div>
<textarea id="yamlIn" placeholder="watchlist:
  - ticker: RIOT
    name: Riot Platforms
    thesis: Bitcoin mining play
    entry_rules:
      breakout_above: 12.50
    ..."></textarea>
<div class="modal-btns">
<button class="btn btn-secondary" onclick="hideCfg()">Annulla</button>
<button class="btn btn-secondary" onclick="pasteFromClipboard()">📋 Incolla Clipboard</button>
<button class="btn btn-primary" onclick="saveCfg()">💾 Applica</button>
</div>
</div>
</div>

<script>
const TOKEN = "{token}";
const API = "/api/" + TOKEN;

const PROMPT_TEMPLATE = `Genera YAML per monitoraggio stock. Rispondi SOLO con YAML valido, senza spiegazioni.

PARAMETRI RICHIESTI:
- Numero titoli: {{numStocks}}
- Rischio: {{riskLevel}}
- Settore: {{sector}}
- Market Cap: {{marketCap}}

COPIA ESATTAMENTE QUESTO FORMATO (sostituisci solo i valori):

watchlist:
  - ticker: "AAPL"
    name: "Apple Inc"
    thesis: "Motivo breve"
    entry_rules:
      breakout_above: 150.00
      min_daily_change_pct: 3.0
      min_volume: 1000000
    exit_rules:
      stop_loss_pct: 15
      target_pct: 30
      max_hold_days: 30
    alerts:
      daily_change_above: 7
      daily_change_below: -7

IMPORTANTE:
- ticker: simbolo NYSE/NASDAQ valido tra virgolette
- breakout_above: prezzo numerico (es: 150.00)
- Tutti i numeri SENZA virgolette
- Indentazione: 2 spazi
- Ripeti il blocco "- ticker:" per ogni titolo

Genera {{numStocks}} titoli.`;

function getMarketCapSelection() {{
    const select = document.getElementById('marketCap');
    const selected = Array.from(select.selectedOptions).map(o => o.value);
    if (selected.length === 0) return 'qualsiasi';
    const labels = {{large:'Large Cap (>$10B)', mid:'Mid Cap ($2-10B)', small:'Small Cap ($300M-2B)', penny:'Penny (<$5)'}};
    return selected.map(v => labels[v] || v).join(', ');
}}

function generatePrompt() {{
    const risk = document.getElementById('riskLevel').value;
    const sector = document.getElementById('sectorFocus').value || 'qualsiasi';
    const num = document.getElementById('numStocks').value;
    const mcap = getMarketCapSelection();
    return PROMPT_TEMPLATE
        .replace(/{{riskLevel}}/g, risk.toUpperCase())
        .replace(/{{numStocks}}/g, num)
        .replace('{{sector}}', sector)
        .replace('{{marketCap}}', mcap);
}}

function showPrompt() {{
    document.getElementById('promptText').value = generatePrompt();
    document.getElementById('promptModal').classList.add('active');
}}
function hidePrompt() {{ document.getElementById('promptModal').classList.remove('active'); }}

async function copyPrompt() {{
    const text = generatePrompt();
    try {{
        await navigator.clipboard.writeText(text);
        const btn = document.getElementById('copyPromptBtn');
        btn.textContent = '✅ Copiato!';
        btn.classList.add('copied');
        setTimeout(() => {{
            btn.textContent = '📋 Copia Prompt';
            btn.classList.remove('copied');
        }}, 2000);
    }} catch(e) {{
        alert('Errore copia. Seleziona manualmente il testo.');
    }}
}}

document.getElementById('riskLevel').onchange = () => document.getElementById('promptText').value = generatePrompt();
document.getElementById('sectorFocus').oninput = () => document.getElementById('promptText').value = generatePrompt();
document.getElementById('numStocks').onchange = () => document.getElementById('promptText').value = generatePrompt();

async function load(){{try{{const r=await fetch(API+'/status'),d=await r.json();render(d)}}catch(e){{document.getElementById('app').innerHTML='<div class="empty">Errore caricamento</div>'}}}}

function render(d){{let h='';const pos=d.positions||[],wl=Object.entries(d.watchlist||{{}});
if(pos.length){{h+='<div class="section"><div class="section-title">📊 Posizioni</div>';
for(const p of pos){{const m=d.watchlist[p.ticker]?.market||{{}},pnl=m.price?((m.price/p.entry_price-1)*100):0;
h+=`<div class="card"><div class="card-header"><span class="ticker">${{p.ticker}}</span><span class="status status-open">OPEN</span></div>
<div class="pnl ${{pnl>=0?'positive':'negative'}}">${{pnl>=0?'+':''}}${{pnl.toFixed(1)}}%</div>
<div class="levels"><div class="level"><div class="level-label">Entry</div><div class="level-value">${{p.entry_price}}</div></div>
<div class="level"><div class="level-label">Now</div><div class="level-value">${{m.price||'?'}}</div></div>
<div class="level"><div class="level-label">Stop</div><div class="level-value" style="color:#ef4444">${{p.stop_loss}}</div></div>
<div class="level"><div class="level-label">Target</div><div class="level-value" style="color:#22c55e">${{p.target}}</div></div></div>
<button class="btn btn-secondary" style="width:100%;margin-top:12px" onclick="doExit('${{p.ticker}}')">Chiudi</button></div>`}}h+='</div>'}}
const watch=wl.filter(([t])=>!pos.find(p=>p.ticker===t));
if(watch.length){{h+='<div class="section"><div class="section-title">👀 Watchlist</div>';
for(const[t,i]of watch){{const m=i.market||{{}},c=i.config||{{}};
h+=`<div class="card"><div class="card-header"><span class="ticker">${{t}}</span><span class="status status-watch">WATCH</span></div>
<div class="price-row"><span class="price">$${{(m.price||0).toFixed(2)}}</span>
<span class="change ${{(m.daily_change_pct||0)>=0?'positive':'negative'}}">${{(m.daily_change_pct||0)>=0?'+':''}}${{(m.daily_change_pct||0).toFixed(1)}}%</span></div>
<div class="levels"><div class="level"><div class="level-label">Entry sopra</div><div class="level-value">$${{c.entry_rules?.breakout_above||'?'}}</div></div>
<div class="level"><div class="level-label">Stop</div><div class="level-value">-${{c.exit_rules?.stop_loss_pct||15}}%</div></div></div>
<div class="thesis">💡 ${{c.thesis||'N/A'}}</div>
<button class="btn btn-primary" style="width:100%;margin-top:12px" onclick="doEnter('${{t}}')">Entra</button></div>`}}h+='</div>'}}
if(!h)h='<div class="empty">Watchlist vuota<br><br>1. Clicca "📝 Genera Prompt"<br>2. Copialo su ChatGPT/Claude<br>3. Incolla la risposta YAML</div>';
document.getElementById('app').innerHTML=h}}

function showCfg(){{document.getElementById('cfgModal').classList.add('active');pasteFromClipboard()}}
function hideCfg(){{document.getElementById('cfgModal').classList.remove('active')}}
async function pasteFromClipboard(){{
try{{const text=await navigator.clipboard.readText();if(text&&(text.includes('watchlist')||text.includes('ticker'))){{document.getElementById('yamlIn').value=text}}}}catch(e){{console.log('Clipboard non disponibile')}}}}
function cleanYaml(y){{return y.replace(/```yaml\\n?/gi,'').replace(/```\\n?/g,'').replace(/^[\\s\\S]*?(watchlist:)/m,'$1').trim()}}
async function saveCfg(){{let y=document.getElementById('yamlIn').value;y=cleanYaml(y);
try{{const r=await fetch(API+'/config/yaml',{{method:'POST',headers:{{'Content-Type':'text/plain'}},body:y}}),d=await r.json();
if(d.status==='ok'){{alert('✅ Applicato: '+d.tickers.join(', '));hideCfg();load()}}else alert('❌ '+(d.detail||JSON.stringify(d)))}}catch(e){{alert('❌ '+e.message)}}}}
async function doCheck(){{const b=document.getElementById('ckBtn');b.disabled=true;b.textContent='⏳';await fetch(API+'/check',{{method:'POST'}});await load();b.disabled=false;b.textContent='🔄 Check'}}
async function doTest(){{const r=await fetch(API+'/test',{{method:'POST'}}),d=await r.json();alert(d.success?'✅ Telegram OK':'❌ Errore')}}
async function doEnter(t){{if(!confirm('ENTRY '+t+'?'))return;await fetch(API+'/position/enter?ticker='+t,{{method:'POST'}});load()}}
async function doExit(t){{if(!confirm('EXIT '+t+'?'))return;await fetch(API+'/position/exit?ticker='+t,{{method:'POST'}});load()}}
load();setInterval(load,60000);
</script></body></html>"""

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "127.0.0.1")
    uvicorn.run(app, host=host, port=int(os.getenv("PORT", 8000)))
