# 🤖 PROMPT UNIVERSALE - Stock Monitor Config Generator

Copia questo prompt e incollalo su **qualsiasi AI** (ChatGPT, Claude, Gemini, Copilot, Mistral, etc.)

---

## PROMPT DA COPIARE

```
Sei un analista finanziario. Devi generare una configurazione YAML per un bot di monitoraggio stock.

REGOLE OBBLIGATORIE:
1. Suggerisci da 1 a 3 titoli azionari quotati su mercati USA (NYSE/NASDAQ)
2. Solo ticker validi e liquidi (volume giornaliero > 500K)
3. Per ogni stock definisci regole NUMERICHE precise di entry e exit
4. Rispondi SOLO con il blocco YAML, niente altro testo prima o dopo

SCHEMA YAML OBBLIGATORIO (rispetta ESATTAMENTE questa struttura):

```yaml
watchlist:
  - ticker: "SIMBOLO"           # Ticker Yahoo Finance (es: AAPL, TSLA, RIOT)
    name: "Nome Azienda"
    
    # Contesto investimento
    thesis: "Motivo per cui monitorare questo titolo in 1-2 frasi"
    catalyst: "Evento specifico che può muovere il prezzo (earnings, FDA, merger, etc)"
    sector: "Settore (es: Tech, Biotech, Crypto Mining, Energy)"
    risk_level: "LOW|MEDIUM|HIGH|EXTREME"
    
    # REGOLE DI ENTRY - Quando comprare
    # Il bot segnala ENTRY quando TUTTE queste condizioni sono vere
    entry_rules:
      breakout_above: 0.00      # Prezzo deve superare questo livello (resistenza)
      min_daily_change_pct: 0.0 # Variazione giornaliera minima % (es: 2.0 = +2%)
      min_volume: 0             # Volume minimo (es: 1000000 = 1M)
    
    # REGOLE DI EXIT - Quando vendere
    exit_rules:
      stop_loss_pct: 15         # Percentuale massima di perdita (es: 15 = -15%)
      target_pct: 30            # Percentuale di profitto target (es: 30 = +30%)
      max_hold_days: 30         # Giorni massimi in posizione prima di uscire
    
    # ALERT AGGIUNTIVI - Notifiche su eventi importanti
    alerts:
      price_above: 0.00         # Notifica se prezzo supera (opzionale, 0 = disattivo)
      price_below: 0.00         # Notifica se prezzo scende sotto (opzionale)
      daily_change_above: 7     # Notifica se sale più di X% in un giorno
      daily_change_below: -7    # Notifica se scende più di X% in un giorno
```

PARAMETRI UTENTE:
- Orizzonte temporale: [INSERISCI: giorni/settimane]
- Tolleranza rischio: [INSERISCI: bassa/media/alta/estrema]
- Settore preferito: [INSERISCI: qualsiasi / tech / crypto / biotech / energy / etc]
- Capitale disponibile: [INSERISCI: importo o "non rilevante"]
- Note aggiuntive: [INSERISCI: qualsiasi preferenza]

ISTRUZIONI AGGIUNTIVE:
- I valori di breakout_above devono essere SOPRA il prezzo attuale (altrimenti non è un breakout)
- Lo stop_loss_pct ragionevole è tra 10-20% per stock volatili
- Il target_pct dovrebbe essere almeno 2x lo stop_loss (risk/reward 1:2 minimo)
- Il volume minimo garantisce liquidità per entrare/uscire facilmente

Genera SOLO il blocco YAML senza spiegazioni aggiuntive.
```

---

## ESEMPIO DI RISPOSTA ATTESA

Quando dai questo prompt all'AI con parametri tipo:
- Orizzonte: 2-4 settimane
- Rischio: alto
- Settore: crypto/mining
- Capitale: €500

L'AI dovrebbe rispondere SOLO con:

```yaml
watchlist:
  - ticker: "RIOT"
    name: "Riot Platforms Inc"
    thesis: "Principale miner Bitcoin USA, alta correlazione con BTC price"
    catalyst: "Bitcoin halving Aprile 2024, atteso rally pre/post evento"
    sector: "Crypto Mining"
    risk_level: "HIGH"
    entry_rules:
      breakout_above: 12.50
      min_daily_change_pct: 3.0
      min_volume: 5000000
    exit_rules:
      stop_loss_pct: 15
      target_pct: 35
      max_hold_days: 28
    alerts:
      price_above: 16.00
      price_below: 9.00
      daily_change_above: 8
      daily_change_below: -8

  - ticker: "MARA"
    name: "Marathon Digital Holdings"
    thesis: "Largest BTC miner per hash rate, high beta play su Bitcoin"
    catalyst: "Espansione capacità mining Q1, BTC momentum"
    sector: "Crypto Mining"
    risk_level: "EXTREME"
    entry_rules:
      breakout_above: 19.00
      min_daily_change_pct: 4.0
      min_volume: 8000000
    exit_rules:
      stop_loss_pct: 18
      target_pct: 45
      max_hold_days: 21
    alerts:
      price_above: 25.00
      price_below: 14.00
      daily_change_above: 10
      daily_change_below: -10
```

---

## COME USARE LA RISPOSTA

1. **Copia** il blocco YAML generato dall'AI
2. **Vai** sulla dashboard del bot → sezione "Config"
3. **Incolla** lo YAML
4. **Salva** - il bot inizia a monitorare

---

## NOTE SUI PARAMETRI

### entry_rules (quando il bot segnala BUY)

| Parametro | Significato | Esempio |
|-----------|-------------|---------|
| `breakout_above` | Prezzo deve superare questa soglia | 12.50 = compra sopra $12.50 |
| `min_daily_change_pct` | Movimento minimo giornaliero | 3.0 = almeno +3% oggi |
| `min_volume` | Volume minimo scambi | 5000000 = 5M shares |

### exit_rules (quando il bot segnala SELL)

| Parametro | Significato | Esempio |
|-----------|-------------|---------|
| `stop_loss_pct` | Max perdita tollerata | 15 = vendi se -15% da entry |
| `target_pct` | Profitto obiettivo | 30 = vendi se +30% da entry |
| `max_hold_days` | Timeout posizione | 30 = esci dopo 30 giorni |

### alerts (notifiche informative)

| Parametro | Significato |
|-----------|-------------|
| `price_above/below` | Alert se prezzo supera/scende sotto livello |
| `daily_change_above/below` | Alert se movimento giornaliero supera soglia |

---

## VARIANTI DEL PROMPT

### Per strategia CONSERVATIVA
Aggiungi: "Preferisci stop_loss_pct tra 8-12% e target_pct tra 15-25%"

### Per strategia AGGRESSIVA
Aggiungi: "Accetto stop_loss_pct fino a 25% se target_pct è almeno 50%"

### Per SWING TRADING (settimane)
Aggiungi: "max_hold_days tra 14-45, entry su breakout settimanali"

### Per DAY/MOMENTUM (giorni)
Aggiungi: "max_hold_days tra 3-7, min_daily_change_pct almeno 5%"
