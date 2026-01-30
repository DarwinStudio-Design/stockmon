# 📈 Stock Monitor - Config Driven

Bot di monitoraggio che legge configurazioni YAML generate da **qualsiasi AI**.

## 🔄 Come Funziona

```
1. Copi il PROMPT_UNIVERSALE.md
2. Lo incolli su ChatGPT / Claude / Gemini / qualsiasi LLM
3. L'AI ti restituisce uno YAML con stock + regole
4. Incolli lo YAML nel bot
5. Il bot monitora e ti notifica su Telegram
```

**Il bot è "stupido"** - non ragiona, esegue solo le regole che gli dai.

## 🚀 Deploy

### 1. Bot Telegram
- @BotFather → `/newbot` → salva **TOKEN**
- @userinfobot → `/start` → salva **CHAT_ID**

### 2. Railway
1. [railway.app](https://railway.app) → Login GitHub
2. New Project → Deploy from GitHub
3. Variables:
```
TELEGRAM_TOKEN=...
TELEGRAM_CHAT_ID=...
```

### 3. Cron Job
[cron-job.org](https://cron-job.org) → POST ogni 15 min:
```
https://tuo-app.up.railway.app/cron/check
```

## 📋 Generare Config con AI

Vedi **PROMPT_UNIVERSALE.md** - copia il prompt e incollalo su qualsiasi AI.

L'AI restituirà YAML tipo:
```yaml
watchlist:
  - ticker: "RIOT"
    thesis: "Bitcoin mining play"
    entry_rules:
      breakout_above: 12.50
      min_daily_change_pct: 3.0
    exit_rules:
      stop_loss_pct: 15
      target_pct: 30
```

## 📱 Dashboard

1. Apri `https://tuo-app.up.railway.app`
2. Clicca **"📋 Config YAML"**
3. Incolla lo YAML generato dall'AI
4. **Salva**

## 🔔 Notifiche

| Emoji | Tipo | Quando |
|-------|------|--------|
| 🟢 | ENTRY | Tutte le condizioni entry soddisfatte |
| 🔴 | EXIT | Stop loss / Target / Timeout |
| ⚡ | ALERT | Movimento anomalo |

## 💰 Costi

Tutto gratuito (Railway free tier, Telegram gratuito, Yahoo Finance gratuito).
