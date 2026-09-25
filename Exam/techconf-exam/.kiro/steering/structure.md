---
inclusion: always
---

# TechConf — Organizzazione del codice (structure)

Questo file contiene le regole valide per **tutto il repository**. Le decisioni specifiche di un singolo servizio (tabelle SQLite, chiamate HTTP, gestione dello stato) stanno nel `design.md` di quel servizio.

---

## 1. Repository e confini dei servizi

**Scelta: monorepo con una cartella per servizio sotto `services/`.**

```
services/
  user-service/
  event-service/
  registration-service/
  feedback-service/
  notification-service/
```

La suite di collaudo è nel repo e `services.yaml` punta a percorsi relativi alla root; un monorepo evita configurazioni di URL tra repository diversi e semplifica clone, tag e consegna.

Ogni servizio è un package Python autonomo (`services/<nome>-service/app/`). Non esistono import tra `services/user-service/app` e `services/event-service/app`: se accade è un bug di architettura visibile subito (`ImportError` o `sys.path` sospetto). La comunicazione tra servizi è **solo HTTP**.

---

## 2. Codice condiviso e duplicazione

**Scelta: nessuna libreria condivisa tra servizi.** Ogni servizio duplica `error_response()`, la funzione di paginazione e i propri client HTTP.

Un package `shared/` introdurrebbe accoppiamento implicito: un cambiamento in `shared/errors.py` può rompere più servizi contemporaneamente ed è difficile da isolare in un esame con commit tracciati. Ogni servizio deve poter essere consegnato, testato e giudicato indipendentemente.

**Eccezione interna al servizio (non tra servizi):** un servizio con più dipendenze HTTP (es. `registration-service`, che chiama sia `user-service` sia `event-service`) può avere una piccola classe base client interna al proprio package (es. `app/clients/base_client.py`) per centralizzare timeout (2 s) ed error-mapping tra i client di quel singolo servizio:
- 404 remoto → 422 `REFERENCE_NOT_FOUND`
- timeout / connessione rifiutata / 5xx → 503 `DEPENDENCY_UNAVAILABLE`

Questa classe non è mai condivisa tra servizi diversi: vive solo dentro `services/<nome>-service/app/clients/`. Lo scopo è evitare copia-incolla della logica di error-mapping tra client dello stesso servizio, che altrimenti rischia drift e fa fallire silenziosamente i test di resilienza (IT-E08, IT-R10, IT-F05, IT-N02).

**Validazione input:** nessuna libreria di schema esterna (pydantic, marshmallow, cerberus o simili). Le uniche dipendenze runtime ammesse sono `flask` e `requests`. La validazione dei campi (lunghezze, enum, formati, obbligatorietà) è scritta a mano in `routes.py` o `service.py`, servizio per servizio.

---

## 3. Struttura interna di un servizio

```
services/user-service/
  app/
    __init__.py        # factory Flask, legge config, crea il repository
    __main__.py        # entrypoint: crea l'app e chiama app.run(host="0.0.0.0", port=PORT)
    config.py          # tutte le variabili d'ambiente in un posto
    routes.py          # solo HTTP: parsing, validazione input, serializzazione output
    service.py         # regole di business REQ-*-B*: qui vivono i controlli
    repository/
      base.py          # interfaccia AbstractRepository
      memory.py
      json_repo.py
      sqlite_repo.py
    clients/
      user_client.py   # chiamate HTTP verso altri servizi (solo dove servono)
  tests/
    test_routes.py
    test_service.py
    test_repository.py
  requirements.txt
```

**Dove vivono le regole `REQ-*-B*`:** in `service.py`. Le route non decidono nulla di business; il repository non sa nulla di business. Un requisito ha un unico posto nel codice.

**Isolamento del backend di persistenza:** `service.py` riceve un oggetto `repository` che implementa l'interfaccia definita in `repository/base.py` (`AbstractRepository`). La factory in `__init__.py` legge `STORAGE_BACKEND` e costruisce l'implementazione giusta. `service.py` non importa mai `memory.py`, `json_repo.py` o `sqlite_repo.py` direttamente: dipende solo dall'interfaccia.

**Isolamento delle chiamate esterne:** ogni client HTTP è in `clients/<nome>_client.py`. Nei test unitari si mocka il client (con `responses` o monkeypatching), non Flask o requests direttamente.

**Entrypoint obbligatorio:** ogni servizio ha `app/__main__.py`, così il comando di avvio è sempre `python -m app` per tutti i servizi, senza eccezioni. Il bind è su `host="0.0.0.0"` (mai `127.0.0.1` di default), perché la suite di collaudo avvia i servizi come sottoprocessi e li interroga dall'esterno.

---

## 4. Configurazione e avvio

`config.py` è l'**unico punto** di lettura delle variabili d'ambiente in ogni servizio:

```python
# app/config.py
import os

PORT                    = int(os.environ.get("PORT", 5001))
USER_SERVICE_URL        = os.environ.get("USER_SERVICE_URL",         "http://localhost:5001")
EVENT_SERVICE_URL       = os.environ.get("EVENT_SERVICE_URL",        "http://localhost:5002")
REGISTRATION_SERVICE_URL= os.environ.get("REGISTRATION_SERVICE_URL", "http://localhost:5003")
FEEDBACK_SERVICE_URL    = os.environ.get("FEEDBACK_SERVICE_URL",     "http://localhost:5004")
NOTIFICATION_SERVICE_URL= os.environ.get("NOTIFICATION_SERVICE_URL", "http://localhost:5005")
STORAGE_BACKEND         = os.environ.get("STORAGE_BACKEND", "memory")
DATA_DIR                = os.environ.get("DATA_DIR", "./data")
```

`__init__.py` importa solo da `config.py`. Nessun `os.environ.get` sparso in `routes.py` o `service.py`.

**Avvio uniforme:** il comando è identico per tutti i servizi in `services.yaml`:
```yaml
command: python -m app
```
eseguito dalla `cwd` del servizio. `app/__main__.py` legge `PORT` da `config.py` e fa il bind su `0.0.0.0`.

**Dipendenze Python:** un `requirements.txt` per servizio, nessun virtualenv condiviso. Installazione con `pip install -r requirements.txt` dalla cartella del servizio. Questo permette a servizi diversi di avere versioni diverse della stessa libreria senza conflitti.

---

## 5. Test

Test vicino al codice, dentro la cartella di ciascun servizio:

```
services/user-service/
  tests/
    test_routes.py       # unit: Flask test client, HTTP mockato con responses
    test_service.py      # unit: logica business, repository mockato
    test_repository.py   # unit: tutti e 3 i backend con tmp_path
    test_contract.py     # contract: assert_matches_contract per ogni endpoint
    test_integration.py  # integration: avvia il servizio reale su porta libera
```

**Avvio dei servizi nei test di integrazione propri:** fixture pytest che lancia `subprocess.Popen(["python", "-m", "app"], ...)` con una porta libera trovata via `socket`, attende che `GET /health` risponda 200 (polling con timeout), poi chiama `Popen.terminate()` nel teardown.

**Comando per singolo servizio:**
```bash
pytest tests/ --cov=app
```
eseguito dalla cartella del servizio.

**Comando per l'intera piattaforma:** script `run_all_tests.sh` in root che itera ogni cartella di servizio e lancia un processo `pytest` separato al suo interno. Non un unico `pytest services/*/tests --cov` lanciato dalla root: ogni servizio espone un package chiamato `app`, e importarli tutti nello stesso processo pytest rischia collisioni in `sys.modules["app"]` e coverage attribuita al servizio sbagliato. Un processo pytest separato per servizio evita il problema alla radice.

---

## 6. Spec e tracciabilità

**Una spec Kiro per servizio:**

```
.kiro/specs/
  user-service/
    requirements.md
    design.md
    tasks.md
  event-service/
    ...
  registration-service/
    ...
```

**Percorso dalla spec al codice — sempre 4 passi:**

1. `REQ-REG-B05` in `requirements.md`
2. → task corrispondente in `tasks.md` con `_Requirements: REQ-REG-B05_`
3. → codice in `service.py` con commento `# REQ-REG-B05`
4. → test in `test_service.py` con `@pytest.mark.req("REQ-REG-B05")`

**Differenza tra `structure.md` e `design.md`:** questo file (`structure.md`) contiene regole valide per tutto il repository — organizzazione delle cartelle, politica di duplicazione, modalità di avvio. Il `design.md` di ogni servizio contiene le decisioni specifiche di quel servizio: quali tabelle SQLite, quali chiamate HTTP effettua, come gestisce il proprio stato.

---

## 7. Dati e Git

`data/` è escluso da git. Ogni servizio scrive in `services/<nome>-service/data/` (o nel `DATA_DIR` iniettato dall'esterno dall'ambiente di collaudo). File SQLite e JSON non finiscono mai nel repository.

**Struttura dei commit — sempre in questo ordine per ciascun servizio:**

```
spec(user-service): requirements
spec(user-service): design
spec(user-service): tasks
feat(user-service): health endpoint [T-01]
feat(user-service): POST /api/v1/users [T-02]
...
fix(user-service): email case-insensitive comparison (closes #1)
```

Ogni commit è atomico rispetto al task che rappresenta. I commit `spec(*)` precedono sempre qualsiasi `feat(*)` per lo stesso servizio — verificabile con:

```bash
git log --oneline -- .kiro/specs/<servizio>/
git log --oneline -- services/<servizio>/app/
```
