---
inclusion: always
---

# TechConf — Product Overview

## Scopo

TechConf è una piattaforma a microservizi per la gestione delle iscrizioni a conferenze tecnologiche (cloud, AI, security). Consente a organizzatori, speaker e partecipanti di gestire l'intero ciclo di vita di una conferenza: dalla creazione dell'evento alla raccolta di feedback, passando per iscrizioni e notifiche.

## Attori

| Ruolo | Descrizione |
|---|---|
| `attendee` | Partecipante generico; si iscrive agli eventi, lascia feedback |
| `speaker` | Relatore; si iscrive agli eventi come speaker |
| `organizer` | Organizzatore; crea e gestisce gli eventi |

Un utente ha esattamente un ruolo. Il ruolo di default è `attendee`.

## Microservizi

La piattaforma è composta da 5 microservizi indipendenti che comunicano via HTTP:

| # | Servizio | Responsabilità | Tipo |
|---|---|---|---|
| 1 | **user-service** `:5001` | Anagrafica utenti (CRUD, unicità email, filtro per ruolo) | Obbligatorio |
| 2 | **event-service** `:5002` | Conferenze con ciclo di vita e capienza; valida l'organizzatore su user-service | Obbligatorio |
| 3 | **registration-service** `:5003` | Iscrizioni utenti-eventi con controllo capienza; valida utente ed evento | Obbligatorio |
| 4 | **feedback-service** `:5004` | Valutazioni degli iscritti agli eventi; valida l'iscrizione su registration-service | Opzionale |
| 5 | **notification-service** `:5005` | Notifiche singole e broadcast agli iscritti confermati | Opzionale |

## Dominio

### Utenti
Ogni utente ha nome, cognome, email (univoca, case-insensitive), azienda opzionale e ruolo. L'email è sempre salvata in minuscolo.

### Eventi
Un evento ha titolo, descrizione, organizzatore (deve essere un utente con `role = organizer`), sede, città, date di inizio e fine, capienza massima, prezzo e stato.

Ciclo di vita degli eventi:

```
draft ──► published ──► cancelled
  │                         ▲
  └─────────────────────────┘
```

Transizioni ammesse: `draft→published`, `draft→cancelled`, `published→cancelled`.
La transizione `published→draft` non è consentita.

### Iscrizioni
Un'iscrizione collega un utente a un evento `published`. Le regole chiave:
- L'utente non può iscriversi due volte allo stesso evento (tra iscrizioni `confirmed`).
- Le iscrizioni `confirmed` non possono superare la capienza dell'evento.
- L'importo (`amount`) è copiato da `event.price` al momento dell'iscrizione e non è mai fornito dal client.
- L'unica transizione di stato permessa è `confirmed → cancelled`; cancellare un'iscrizione libera un posto.

### Feedback
Un feedback è una valutazione (1–5 stelle, commento opzionale) lasciata da un utente che ha un'iscrizione `confirmed` a quell'evento. Un solo feedback per coppia `(user_id, event_id)`.

### Notifiche
Una notifica è un messaggio (email, SMS o push) inviato a un utente. Il `broadcast` crea una notifica per ogni iscritto `confirmed` a un evento. Il ciclo di vita è `queued → sent | failed`; `sent` e `failed` sono stati finali.

## Relazioni tra servizi

```
user-service  ◄── event-service
user-service  ◄── registration-service
event-service ◄── registration-service
registration-service ◄── feedback-service
event-service        ◄── feedback-service
user-service         ◄── notification-service
registration-service ◄── notification-service
```

A ──► B significa "A chiama le API di B per validare o leggere dati".
