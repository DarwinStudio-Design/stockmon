# 📈 Stock Monitor Bot

Monitoraggio automatico RIOT/CLSK/MARA con notifiche Telegram push.

## 🚀 Deploy su Railway (5 minuti)

### Step 1: Crea Bot Telegram

1. Apri Telegram e cerca **@BotFather**
2. Invia `/newbot`
3. Scegli un nome (es: "Stock Monitor")
4. Scegli username (es: `mio_stock_bot`)
5. **Salva il TOKEN** che ricevi

Per ottenere il tuo CHAT_ID:
1. Cerca **@userinfobot** su Telegram
2. Invia `/start`
3. **Salva il tuo ID numerico**

### Step 2: Deploy su Railway

1. Vai su [railway.app](https://railway.app) e accedi con GitHub
2. Clicca **"New Project"** → **"Deploy from GitHub repo"**
3. Seleziona questo repository (o carica i file)
4. Railway rileva automaticamente Python e deploya

### Step 3: Configura Variabili Ambiente

Nel progetto Railway:
1. Vai in **Variables**
2. Aggiungi:

```
TELEGRAM_TOKEN=il_tuo_token_bot
TELEGRAM_CHAT_ID=il_tuo_chat_id
```

### Step 4: Configura Cron Job

Per check automatici ogni 15 minuti:

1. Nel progetto Railway, vai in **Settings** → **Cron**
2. Aggiungi:
   - **Schedule**: `*/15 * * * *` (ogni 15 min)
   - **Endpoint**: `POST /cron/check`

Oppure usa un servizio esterno gratuito come [cron-job.org](https://cron-job.org):
- URL: `https://tuo-progetto.up.railway.app/cron/check`
- Metodo: POST
- Intervallo: 15 minuti

## 📱 Uso

### Dashboard Web
Apri `https://tuo-progetto.up.railway.app` dal telefono e aggiungila alla Home.

### Endpoints API

| Endpoint | Metodo | Descrizione |
|----------|--------|-------------|
| `/` | GET | Dashboard web |
| `/health` | GET | Health check |
| `/status` | GET | Stato completo |
| `/prices` | GET | Prezzi live |
| `/check` | POST | Trigger check manuale |
| `/alerts` | GET | Storico alerts |
| `/test-telegram` | POST | Test notifica |
| `/cron/check` | POST | Check (per cron) |
| `/position/enter` | POST | Registra posizione |
| `/position/exit` | POST | Chiudi posizione |

### Registrare una Posizione

```bash
curl -X POST "https://tuo-app.up.railway.app/position/enter?ticker=RIOT&entry_price=12.50&stop_loss=10.60&target=16.25"
```

## 🔔 Tipi di Alert

- **🟢 ENTRY**: Breakout confermato (prezzo > high 5d + movimento > 3%)
- **🔴 EXIT**: Stop loss o target raggiunto
- **⚡ ALERT**: Movimento > 7% giornaliero
- **👀 WATCH**: Vicino a livelli chiave
- **⚠️ WARNING**: Drawdown in posizione

## ⚙️ Personalizzazione

### Modificare Ticker Monitorati

In `main.py`, cambia:
```python
TICKERS = ["RIOT", "CLSK", "MARA"]
```

### Modificare Soglie Segnali

Nella funzione `analyze_signal()`:
- Breakout: `price > high_5d and change > 3`
- Alert big move: `change > 7` o `change < -7`
- Stop loss default: `price * 0.85` (-15%)
- Target default: `price * 1.30` (+30%)

## 💰 Costi

| Servizio | Costo |
|----------|-------|
| Railway | €0 (free tier: 500 ore/mese) |
| Telegram | €0 |
| Yahoo Finance | €0 |
| **Totale** | **€0** |

## 🛡️ Sicurezza

- Token Telegram in variabili ambiente (non nel codice)
- Nessun trading automatico (solo segnali)
- Rate limiting base su API

## 📋 Troubleshooting

**Bot non invia notifiche:**
- Verifica TELEGRAM_TOKEN e CHAT_ID nelle variabili Railway
- Usa `/test-telegram` per testare

**Prezzi non si aggiornano:**
- Yahoo Finance ha limiti rate. Aspetta qualche minuto.
- Verifica che i ticker esistano su Yahoo Finance

**Check non parte:**
- Verifica che il cron sia configurato correttamente
- Il bot salta i check fuori orario mercato (14:00-21:00 UTC, lun-ven)

## 📄 License

MIT - Usa a tuo rischio. Non è consulenza finanziaria.
