Project Briefing: Crisis Betalingssysteem (PKI Cash)
====================================================

Concept
-------
Een offline-first digitaal betalingssysteem voor crisisscenarios zonder internet,
gebaseerd op PKI cryptografie en een lokale state engine. Communicatie verloopt
via Reticulum Network Stack (RNS) — nu over TCP (localhost), later over LoRa radio.

Filosofie achter het ontwerp
----------------------------
Een munt is geen bestand met waarde. Een munt is een exclusief vermogen om een
geldige state-overgang te ondertekenen. Eigendom is geen bezit van een object,
maar controle over een private key die op dit moment geldig is voor precies één
coin. Dit onderscheid is belangrijk voor alle ontwerpkeuzes die volgen.


Wat een munt is
---------------
Een munt is een klein JSON bestandje:

  {
    "coin_id": "<uuid>",
    "waarde": 10,
    "PK_current": "<publieke sleutel huidige eigenaar>",
    "PK_issuer": "<publieke sleutel uitgever>",
    "issuer_signature": "<handtekening van uitgever over coin_id + waarde + PK_current>",
    "state_engine_endpoint": "<dest hash van de state engine>",
    "PK_engine": "<publieke sleutel van de state engine>"
  }

De waarde in issuer_signature is het resultaat van: sign met SK_issuer over
(coin_id | waarde | PK_current). De private key SK_issuer zit NIET in de coin —
alleen het resultaat (de signature hex bytes). Verificatie gaat met PK_issuer
(publieke sleutel) die al in de coin staat.
Zonder geldige issuer_signature is de coin waardeloos.


Twee sleuteltypen
-----------------
Elke actor heeft twee soorten sleutels:

| Type            | Bron                     | Doel                                                  |
| --------------- | ------------------------ | ----------------------------------------------------- |
| PK_identity     | RNS.Identity()           | Transport: routing, announcements, berichtverificatie |
| PK_transactie   | PyNaCl Ed25519 (bestaand)| Coins: issuer signatures, eigendomsoverdracht         |

- PK_identity wordt automatisch beheerd door RNS (opgeslagen in data/<actor>/identity)
- PK_transactie = bestaande logica (issuer.key, engine.key, wallet ephemere keys)
- Destination hash = automatisch afgeleid door RNS uit identity + "pkicash" + role


Hoe het systeem werkt
---------------------

### Eigendom
Eigendom van een coin = je bezit SK_current, de private key die hoort bij
PK_current op de coin.

### Een transactie
1. Ontvanger genereert een nieuw keypair (PK_next, SK_next) en stuurt PK_next
   naar de betaler (= het "betaalverzoek")
2. Betaler maakt een transactiebericht: {coin_id, PK_next} gesigneerd met
   SK_current
3. Betaler stuurt dit via RNS naar de state engine
4. State engine verifieert en roteert PK_current naar PK_next
5. State engine stuurt coin via RNS naar de ontvanger

### Wat de state engine doet
1. Verifieert issuer_signature op de coin met bekende PK_issuer
2. Verifieert transactie signature met PK_current
3. Roteert PK_current naar PK_next bij geldige transactie
4. Stuurt gesigneerde bevestiging via RNS terug
5. Double spend: geeft error bij hergebruik van oude PK

De state engine bewaart alleen: coin_id → PK_current
Geen geschiedenis, geen identiteit, geen saldo's.

### Transactie formaat
  {
    "coin_id": "<uuid>",
    "PK_next": "<publieke sleutel ontvanger>",
    "recipient_address": "<dest hash van ontvanger wallet>",
    "signature": "<handtekening van eigenaar over coin_id + PK_next>"
  }

De waarde in signature is het resultaat van: sign met SK_current over
(coin_id | PK_next). De private key SK_current zit NIET in het bericht —
alleen het resultaat (de signature hex bytes). Verificatie door de state engine
gaat met PK_current die de engine al kent.


Vertrouwensmodel
----------------
Een valuta wordt gedefinieerd door PK_issuer (niet door een naam). Coins zonder
geldige issuer_signature van een vertrouwde PK_issuer worden geweigerd.

In een crisissituatie zijn er drie bronnen van vertrouwen:
- Vooraf ingebed vertrouwen (QR codes, papier, vooraf geconfigureerde wallets)
- Sociaal vertrouwen (lokale afspraak over geaccepteerde issuers)
- Economisch vertrouwen (inwisselbaarheid bij bekende punten)


Architectuur
------------
Elke actor (engine, bank, wallet) draait als eigen Python-proces:

  ┌──────────────────────────────────┐
  │      Actor Proces (bijv. Bank)   │
  │                                  │
  │   Flask Web UI ←→ Gedeelde State │
  │   (localhost:port)    │          │
  │                       │          │
  │   RNS Transport  ←→──┘          │
  │   (achtergrond-thread)           │
  └──────────────┬───────────────────┘
                 │
        Reticulum Netwerk
        (TCP nu, LoRa straks)

- Flask: lokale webserver voor browser UI
- RNS: achtergrond-thread voor peer-to-peer communicatie
- Gedeelde state: inbox, announces, coins/transacties
- SSE (Server-Sent Events): alleen lokaal (browser ↔ eigen Flask)

### RNS Communicatie

Announce:
- Bij opstart: actor maakt RNS Identity aan (of laadt bestaande)
- Maakt Destination: RNS.Destination(identity, IN, SINGLE, "pkicash", role)
- role = "engine", "bank", of "wallet"
- app_data bij announce bevat: {name, role, pk_transaction}
- Alle actors ontvangen announces en tonen ze in de UI

Berichttypen (via RNS Link + zlib-compressed JSON):

| Type                    | Van    | Naar              | Inhoud                                    |
| ----------------------- | ------ | ----------------- | ----------------------------------------- |
| register_issuer         | Bank   | Engine            | {pk_issuer, bank_name}                    |
| issuer_confirmed        | Engine | Bank              | {pk_engine, engine_dest}                  |
| issuer_declined         | Engine | Bank              | {reason}                                  |
| engine_register_request | Engine | Bank              | {pk_engine, engine_name, engine_dest}     |
| bank_register_response  | Bank   | Engine            | {pk_issuer, bank_name}                    |
| bank_register_declined  | Bank   | Engine            | {reason}                                  |
| coin_request            | Wallet | Bank              | {amount, wallet_dest, public_keys}        |
| coin_request_declined   | Bank   | Wallet            | {reason}                                  |
| register_coin           | Bank   | Engine            | {coin_json, recipient_dest}               |
| coin_delivery           | Engine | Wallet            | {coin_json, engine_confirmation}          |
| transaction             | Wallet | Engine            | {coin_id, pk_next, sig, recipient_dest}   |
| tx_confirmed            | Engine | Wallet(zender)    | {coin_id, status}                         |
| coin_transfer           | Engine | Wallet(ontvanger) | {updated_coin, confirmation}              |
| payment_request         | Wallet | Wallet            | {address, pk, amount}                     |
| payment_response        | Wallet | Wallet            | {pk, address, original_request}           |

Inbox:
- Inkomende RNS packets worden via callback in een thread-safe lijst geplaatst
- Flask UI pollt via SSE (lokaal, browser ↔ eigen Flask)


Dataflow diagram
----------------
```mermaid
sequenceDiagram
    participant Issuer as Bank (Issuer)
    participant Engine as StateEngine
    participant WalletA
    participant WalletB

    rect rgba(200,200,200,0.15)
    Note over Issuer,Engine: Setup (via RNS)
    Issuer->>Engine: register_issuer(PK_issuer)
    Engine->>Issuer: issuer_confirmed(PK_engine)
    end

    rect rgba(200,200,200,0.15)
    Note over Issuer,WalletA: Coin uitgifte (via RNS)
    WalletA->>WalletA: generate keypair (SK_A, PK_A)
    WalletA-->>Issuer: PK_A + dest_hash (via announce of copy-paste)
    Issuer->>Issuer: create coin (PK_current=PK_A), sign
    Issuer->>Engine: register_coin(coin, recipient_dest)
    Engine->>WalletA: coin_delivery(coin + engine confirmation)
    WalletA->>WalletA: verify engine signature, store coin
    end

    rect rgba(200,200,200,0.15)
    Note over WalletA,WalletB: Betaling (via RNS)
    WalletB->>WalletB: generate keypair (SK_next, PK_next)
    WalletB-->>WalletA: PK_next + dest_hash (via announce of copy-paste)
    WalletA->>WalletA: sign met SK_A over (coin_id | PK_next)
    WalletA->>Engine: transaction(coin_id, PK_next, recipient_dest, sig)
    Engine->>Engine: verify signature + rotate PK_current
    Engine->>WalletA: tx_confirmed(coin_id, status)
    Engine->>WalletB: coin_transfer(updated coin + confirmation)
    WalletB->>WalletB: verify engine signature, store coin
    end
```

Toelichting:
- Alle communicatie gaat via RNS (Reticulum Network Stack)
- --> (stippellijn) zijn handmatige acties (copy-paste announce info)
- Private keys (SK) verlaten NOOIT het apparaat waarop ze zijn aangemaakt


Interactiepatronen (Goedkeuringsflows)
---------------------------------------

Alle cross-actor interacties volgen een universeel verzoek-goedkeuring patroon:

```mermaid
sequenceDiagram
    participant Verzoeker
    participant Ontvanger
    Verzoeker->>Ontvanger: request (type + payload)
    Note over Ontvanger: Toont in UI als "pending"
    alt Goedgekeurd
        Ontvanger->>Verzoeker: approved (+ resultaat)
        Note over Verzoeker: Verwerkt resultaat
    else Afgewezen
        Ontvanger->>Verzoeker: declined (+ reden)
        Note over Verzoeker: Toont melding
    end
```

### Bank → Engine: Issuer registratie

De bank stuurt een registratieverzoek. De engine-operator moet goedkeuren.

```mermaid
sequenceDiagram
    participant Bank
    participant Engine
    Bank->>Engine: register_issuer (pk_issuer, bank_name)
    Note over Engine: Opslaan als pending request
    alt Operator keurt goed
        Engine->>Engine: register_issuer() in DB
        Engine->>Bank: issuer_confirmed (pk_engine, engine_dest)
    else Operator wijst af
        Engine->>Bank: issuer_declined (reden)
    end
```

### Engine → Bank: Registratieverzoek

De engine kan een bank vragen "wil je mij als engine gebruiken?"

```mermaid
sequenceDiagram
    participant Engine
    participant Bank
    Engine->>Bank: engine_register_request (pk_engine, engine_name)
    Note over Bank: Opslaan als pending request
    alt Operator keurt goed
        Bank->>Engine: bank_register_response (pk_issuer, bank_name)
        Note over Engine: register_issuer() in DB
    else Operator wijst af
        Bank->>Engine: bank_register_declined (reden)
    end
```

### Wallet → Bank: Coin-aanvraag

Een wallet kan coins aanvragen bij een bank.

```mermaid
sequenceDiagram
    participant Wallet
    participant Bank
    participant Engine
    Wallet->>Wallet: Genereer N keypairs
    Wallet->>Bank: coin_request (amount, wallet_dest, public_keys)
    Note over Bank: Opslaan als pending request
    alt Operator keurt goed
        loop Voor elke public key
            Bank->>Bank: issue_coin(waarde=1, pk_owner)
            Bank->>Engine: register_coin (coin, recipient_dest)
            Engine->>Wallet: coin_delivery (coin + confirmation)
        end
    else Operator wijst af
        Bank->>Wallet: coin_request_declined (reden)
    end
```


Architectuur & Bestanden
------------------------

### Projectstructuur
  lora-en-pkicash-wallet/
  ├── run.py                    # Startscript: --role engine/bank/wallet of --demo
  ├── app_actor.py              # Flask app factory per actor-rol
  ├── app.py                    # Legacy: oude single-server versie (deprecated)
  ├── opzet.md                  # Dit bestand (project briefing)
  ├── requirements.txt          # Python dependencies (flask, pynacl, rns)
  ├── src/
  │   ├── transport.py          # RNS wrapper: identity, destination, announce, send/receive
  │   ├── crypto_utils.py       # Ed25519 keypair, sign, verify (PyNaCl)
  │   ├── coin.py               # Coin dataclass + issuer signature verificatie
  │   ├── issuer.py             # Bank/Issuer: keypair, coin creatie, signing
  │   ├── engine.py             # StateEngine: SQLite, registratie, rotatie, deliveries
  │   └── wallet.py             # Wallet: coins, keypairs, transactielog, contacten
  ├── templates/
  │   ├── base.html             # Basis layout, SSE, announce overlay, globale JS
  │   ├── index.html            # Legacy rolselectie pagina
  │   ├── engine.html           # State Engine UI
  │   ├── bank.html             # Bank/Issuer UI
  │   └── wallet.html           # Wallet UI
  ├── static/
  │   └── style.css             # Alle styling
  ├── tests/
  │   ├── test_issuer.py        # Unit tests Issuer
  │   ├── test_engine.py        # Unit tests StateEngine
  │   ├── test_wallet.py        # Unit tests Wallet
  │   └── test_integration.py   # End-to-end flow test
  └── data/                     # Runtime data (niet in git)
      ├── engine/               # Engine data directory
      │   ├── identity          # RNS identity (PK_identity)
      │   ├── engine.key        # PyNaCl SK (PK_transactie)
      │   ├── engine.db         # SQLite (coin_id → PK_current)
      │   ├── engine_data.json  # Contacten + issuer namen
      │   └── announces.json    # Ontdekte actoren
      ├── bank/                 # Bank data directory
      │   ├── identity          # RNS identity
      │   ├── issuer.key        # PyNaCl SK (issuer signing)
      │   ├── bank.json         # Uitgegeven coins, contacten, registraties
      │   └── announces.json    # Ontdekte actoren
      └── wallet_<id>/          # Per wallet data directory
          ├── identity          # RNS identity
          ├── wallet.json       # Coins, keypairs, transactielog, contacten
          └── announces.json    # Ontdekte actoren

### Opstarten
  python run.py --role engine --port 5000
  python run.py --role bank   --port 5001
  python run.py --role wallet --id a --port 5002
  python run.py --role wallet --id b --port 5003

Of demo-modus (alle vier tegelijk):
  python run.py --demo


### Core logica (src/)
- transport.py    — RNS wrapper: identity management, destination, announce,
                    send/receive via Links, thread-safe inbox, persistent announces
- crypto_utils.py — Ed25519 keypair generatie, signing, verificatie (PyNaCl)
- coin.py         — Coin dataclass met serialisatie en issuer-signature verificatie
- issuer.py       — Issuer: genereert keypair, maakt coins aan, signeert ze
- engine.py       — StateEngine: SQLite DB, issuer registratie, coin registratie,
                    transactie verificatie en PK-rotatie, pending deliveries
- wallet.py       — Wallet: keypair management per coin, transactielogboek,
                    contactenlijst, coin ontvangst/versturen, persistentie via JSON

### Web applicatie
- run.py          — Startscript met rolkeuze. Start RNS transport + Flask per actor.
- app_actor.py    — Flask app factory. Per rol (engine/bank/wallet) worden alleen
                    de relevante routes geregistreerd. RNS transport wordt gedeeld
                    met Flask via gedeelde state.
- templates/      — Jinja2 templates:
    - base.html   — Basis layout, lokale SSE verbinding, announce overlay,
                    globale JS functies (overlay, menu, contactpicker, copy)
    - engine.html — State Engine UI: activatie, issuer registratie, coins, contacten
    - bank.html   — Bank UI: activatie, coin uitgeven, engine registratie, contacten
    - wallet.html — Wallet UI: saldo, transacties, betalen/ontvangen, contacten
- static/style.css — Banking-app stijl, cards, overlays, activatie wizard


### Demo vs. productie

|               | Demo (1 machine)              | Productie (4 laptops)                |
| ------------- | ----------------------------- | ------------------------------------ |
| Processen     | 4 processen, elk eigen port   | 1 proces per laptop                  |
| RNS interface | AutoInterface (localhost TCP)  | LoRa interface via serial            |
| Config        | Automatisch (RNS default)     | Reticulum config met LoRa parameters |
| Browser       | 4 tabs, elk naar eigen port   | 1 tab op localhost:5000              |


UI Design Patterns
------------------
- Header: actor naam + kopieer-icoon (kopieert dest_hash|PK naar klembord)
- Menu (rechtsboven): secties wisselen (overzicht, contacten, mijn gegevens, netwerk)
- Netwerk overlay: toon ontdekte actoren (via RNS announces), announce knop,
  opslaan als contact
- Inline meldingen: succes-berichten verdwijnen na 3 seconden
- Contacten: uitklapbare kaarten met naam/adres als header, bewerkbare velden
- Overlays: voor acties (coin uitgeven, issuer registreren, betaalverzoek, betalen)
- Adresboek picker: icoon naast velden, dropdown met contacten
- Auto-split bij plakken: "dest_hash|pk" wordt automatisch gesplitst
- SSE: lokaal (browser ↔ eigen Flask), voor RNS berichten en announces


Technische keuzes
-----------------
- Taal: Python 3.10+
- Cryptografie: PyNaCl (libsodium), Ed25519 voor signing, UUID4 voor coin_id
- Transport: Reticulum Network Stack (RNS) voor peer-to-peer communicatie
- Web framework: Flask (per actor, lokale webserver)
- Database state engine: SQLite
- Frontend: Vanilla HTML/CSS/JS, Lucide icons (CDN)
- Data persistentie: JSON bestanden (wallet, bank, engine contacten)
- Communicatie: RNS over AutoInterface (TCP), later LoRa (Heltec V3, SX1262, 868MHz)


Bewuste beperkingen
-------------------
- Offline transacties: als de state engine niet bereikbaar is kunnen geen
  transacties plaatsvinden (vergelijkbaar met pinbetaling zonder netwerk)
- Verlies private key: coin is onherroepelijk verloren (net als fysiek cash)
- State engine als vertrouwenspunt: wie de engine beheert heeft macht.
  Meerdere engines als backup is een latere uitbreiding
- PK_issuer en PK_engine moeten vooraf verspreid zijn (via announce of handmatig)


Roadmap
-------
1. ✓ Core: Issuer, StateEngine, Wallet, Coin klassen
2. ✓ Web UI: Flask applicatie met banking-app stijl
3. ✓ Contactbeheer: adresboek per actor, bewerkbaar, picker in formulieren
4. ✓ SSE: real-time updates (nu lokaal per actor)
5. ✓ Reticulum transport: elke actor als eigen proces met RNS communicatie
6. ✓ Announce systeem: actoren ontdekken elkaar via RNS announces
7. ✓ RNS berichten: registratie, coin uitgifte, transacties via RNS
8. ✓ Goedkeuringspatroon: alle interacties via request → approve/decline → action
9. □ LoRa integratie: Reticulum config met LoRa radio interface
10. □ Meerdere state engines / redundantie
