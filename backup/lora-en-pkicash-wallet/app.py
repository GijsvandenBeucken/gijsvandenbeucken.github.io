import json
import os
import queue
import threading
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, Response

from src.issuer import Issuer
from src.engine import StateEngine, InvalidSignatureError, UntrustedIssuerError, UnknownCoinError
from src.wallet import Wallet
from src.coin import Coin

app = Flask(__name__)
app.secret_key = os.urandom(32)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

issuer_instance = None
engine_instance = None
wallets = {}

sse_wallet_clients: dict[str, list[queue.Queue]] = {}
sse_engine_clients: list[queue.Queue] = []
sse_bank_clients: list[queue.Queue] = []
sse_lock = threading.Lock()


def _load_json(path, default):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return default


def _save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def get_bank_data():
    path = os.path.join(DATA_DIR, "bank.json")
    return _load_json(path, {"address": "", "issued_coins": [], "contacts": [], "registered_at_engine": False, "engine_address": None, "engine_pk": None})


def save_bank_data(data):
    _save_json(os.path.join(DATA_DIR, "bank.json"), data)


def get_engine_data():
    path = os.path.join(DATA_DIR, "engine_data.json")
    return _load_json(path, {"address": "", "contacts": [], "issuer_names": {}})


def save_engine_data(data):
    _save_json(os.path.join(DATA_DIR, "engine_data.json"), data)


def format_contact(address: str, pk_hex: str) -> str:
    return f"{address}|{pk_hex}"


def _sse_notify(clients_list, event_data):
    with sse_lock:
        dead = []
        for q in clients_list:
            try:
                q.put_nowait(event_data)
            except queue.Full:
                dead.append(q)
        for q in dead:
            clients_list.remove(q)


def notify_wallet(wallet_address: str, event_data: dict):
    with sse_lock:
        clients = sse_wallet_clients.get(wallet_address, [])
        dead = []
        for q in clients:
            try:
                q.put_nowait(event_data)
            except queue.Full:
                dead.append(q)
        for q in dead:
            clients.remove(q)


def notify_engine(event_data: dict):
    _sse_notify(sse_engine_clients, event_data)


def notify_bank(event_data: dict):
    _sse_notify(sse_bank_clients, event_data)


def get_engine():
    global engine_instance
    if engine_instance is None:
        db_path = os.path.join(DATA_DIR, "engine.db")
        key_path = os.path.join(DATA_DIR, "engine.key")
        if os.path.exists(key_path):
            engine_instance = StateEngine.load_key(key_path, db_path=db_path)
        else:
            engine_instance = StateEngine(db_path=db_path)
            engine_instance.save_key(key_path)
    return engine_instance


def get_wallet(wallet_id):
    if wallet_id not in wallets:
        wallet_path = os.path.join(DATA_DIR, f"wallet_{wallet_id}.json")
        wallets[wallet_id] = Wallet(wallet_path)
    return wallets[wallet_id]


def _find_wallet_id_by_address(address):
    for wid in ['a', 'b']:
        w = get_wallet(wid)
        if w.address == address:
            return wid
    return None


def get_issuer():
    global issuer_instance
    if issuer_instance is None:
        key_path = os.path.join(DATA_DIR, "issuer.key")
        if os.path.exists(key_path):
            issuer_instance = Issuer.load_key(key_path)
        else:
            issuer_instance = Issuer()
            issuer_instance.save_key(key_path)
    return issuer_instance


def deliver_pending(wallet_id):
    key_path = os.path.join(DATA_DIR, "engine.key")
    if not os.path.exists(key_path):
        return
    w = get_wallet(wallet_id)
    if not w.address:
        return
    eng = get_engine()
    deliveries = eng.get_pending_deliveries(w.address)
    for d in deliveries:
        try:
            w.receive_from_engine(d)
            notify_wallet(w.address, {
                "type": "coin_received",
                "coin_id": d["coin"]["coin_id"],
                "waarde": d["coin"].get("waarde", "?"),
                "status": d["confirmation"]["status"],
            })
        except Exception:
            pass


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _sse_stream(clients_list_or_dict, key=None):
    def stream():
        q = queue.Queue(maxsize=50)
        with sse_lock:
            if key is not None:
                clients_list_or_dict.setdefault(key, []).append(q)
            else:
                clients_list_or_dict.append(q)
        try:
            yield f"data: {json.dumps({'type': 'connected'})}\n\n"
            while True:
                try:
                    event = q.get(timeout=30)
                    yield f"data: {json.dumps(event)}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        except GeneratorExit:
            pass
        finally:
            with sse_lock:
                target = clients_list_or_dict.get(key, []) if key else clients_list_or_dict
                if q in target:
                    target.remove(q)
    return stream


# --- Index ---

@app.route("/")
def index():
    return render_template("index.html", show_nav=False)


# --- Bank ---

@app.route("/bank")
def bank_page():
    demo = request.args.get("demo")
    key_path = os.path.join(DATA_DIR, "issuer.key")
    pk = None
    bank_contact = None
    bank_data = get_bank_data()

    bank_address = bank_data.get("address", "")
    if os.path.exists(key_path):
        pk = get_issuer().pk_hex
        bank_contact = format_contact(bank_address, pk) if bank_address else pk

    inline_msg = session.pop("bank_msg", None)

    return render_template("bank.html",
        show_nav=bool(demo),
        active_page="bank",
        pk_issuer=pk,
        bank_address=bank_address,
        bank_pk=pk,
        bank_contact=bank_contact,
        issued_coins=bank_data["issued_coins"],
        contacts=bank_data["contacts"],
        registered_at_engine=bank_data.get("registered_at_engine", False),
        engine_address=bank_data.get("engine_address"),
        engine_pk=bank_data.get("engine_pk"),
        inline_msg=inline_msg,
    )


@app.route("/bank/set-address", methods=["POST"])
def bank_set_address():
    bank_data = get_bank_data()
    bank_data["address"] = request.form.get("address", "").strip()
    save_bank_data(bank_data)
    return redirect(url_for("bank_page", demo=request.args.get("demo")))


@app.route("/bank/generate-key", methods=["POST"])
def bank_generate_key():
    get_issuer()
    return redirect(url_for("bank_page", demo=request.args.get("demo")))


@app.route("/bank/issue-coin", methods=["POST"])
def bank_issue_coin():
    iss = get_issuer()
    eng = get_engine()
    try:
        waarde = int(request.form["waarde"])
        engine_address = request.form["engine_address"].strip()
        pk_engine = request.form["engine_pk"].strip()
        recipient_address = request.form["recipient_address"].strip()
        pk_owner = request.form["recipient_pk"].strip()

        coin = iss.issue_coin(waarde, pk_owner, f"http://{engine_address}", pk_engine)
        eng.register_coin(coin, recipient_address)

        bank_data = get_bank_data()
        bank_data["issued_coins"].append({
            "timestamp": now_str(),
            "coin_id": coin.coin_id,
            "waarde": waarde,
            "recipient": recipient_address,
            "coin_json": coin.to_dict(),
        })

        if request.form.get("save_contacts"):
            existing_addrs = {c["address"] for c in bank_data["contacts"]}
            engine_name = request.form.get("engine_name", "").strip() or engine_address
            recipient_name = request.form.get("recipient_name", "").strip() or recipient_address
            if engine_address not in existing_addrs:
                bank_data["contacts"].append({"name": engine_name, "address": engine_address, "pk": pk_engine})
            if recipient_address not in existing_addrs:
                bank_data["contacts"].append({"name": recipient_name, "address": recipient_address, "pk": pk_owner})

        save_bank_data(bank_data)

        wid = _find_wallet_id_by_address(recipient_address)
        if wid:
            deliver_pending(wid)

        notify_engine({"type": "coin_registered", "coin_id": coin.coin_id})

        session["bank_msg"] = f"Coin uitgegeven aan {recipient_address}! Waarde: {waarde}"
    except Exception as e:
        flash(f"Fout: {e}", "error")

    return redirect(url_for("bank_page", demo=request.args.get("demo")))


@app.route("/bank/add-contact", methods=["POST"])
def bank_add_contact():
    bank_data = get_bank_data()
    try:
        name = request.form["contact_name"].strip()
        address = request.form["contact_address"].strip()
        pk = request.form.get("contact_pk", "").strip()
        bank_data["contacts"].append({"name": name, "address": address, "pk": pk})
        save_bank_data(bank_data)
        flash(f"Contact '{name}' toegevoegd!", "success")
    except Exception as e:
        flash(f"Fout: {e}", "error")
    return redirect(url_for("bank_page", demo=request.args.get("demo")))


@app.route("/bank/edit-contact/<int:idx>", methods=["POST"])
def bank_edit_contact(idx):
    bank_data = get_bank_data()
    if 0 <= idx < len(bank_data["contacts"]):
        bank_data["contacts"][idx] = {
            "name": request.form["contact_name"].strip(),
            "address": request.form["contact_address"].strip(),
            "pk": request.form.get("contact_pk", "").strip(),
        }
        save_bank_data(bank_data)
        flash("Contact bijgewerkt.", "success")
    return redirect(url_for("bank_page", demo=request.args.get("demo")))


@app.route("/bank/delete-contact/<int:idx>", methods=["POST"])
def bank_delete_contact(idx):
    bank_data = get_bank_data()
    if 0 <= idx < len(bank_data["contacts"]):
        name = bank_data["contacts"][idx]["name"]
        bank_data["contacts"].pop(idx)
        save_bank_data(bank_data)
        flash(f"Contact '{name}' verwijderd.", "info")
    return redirect(url_for("bank_page", demo=request.args.get("demo")))


@app.route("/bank/confirm-engine-registration", methods=["POST"])
def bank_confirm_engine_registration():
    """Called by bank's browser when it receives an SSE confirmation from engine."""
    data = request.get_json(silent=True) or {}
    engine_address = data.get("engine_address", "")
    engine_pk = data.get("engine_pk", "")
    if not engine_address or not engine_pk:
        return jsonify({"error": "missing fields"}), 400

    bank_data = get_bank_data()
    bank_data["registered_at_engine"] = True
    bank_data["engine_address"] = engine_address
    bank_data["engine_pk"] = engine_pk
    existing_addrs = {c["address"] for c in bank_data["contacts"]}
    if engine_address not in existing_addrs:
        bank_data["contacts"].append({"name": "State Engine", "address": engine_address, "pk": engine_pk})
    save_bank_data(bank_data)
    return jsonify({"ok": True})


# --- Engine ---

@app.route("/engine")
def engine_page():
    demo = request.args.get("demo")
    key_path = os.path.join(DATA_DIR, "engine.key")
    pk = None
    engine_contact = None
    issuers = []
    coins = []
    engine_data = get_engine_data()

    engine_address = engine_data.get("address", "")
    if os.path.exists(key_path):
        eng = get_engine()
        pk = eng.pk_hex
        engine_contact = format_contact(engine_address, pk) if engine_address else pk
        raw_issuers = eng.list_issuers()
        issuer_names = engine_data.get("issuer_names", {})
        issuers = [{"pk": p, "name": issuer_names.get(p, "")} for p in raw_issuers]
        coin_rows = eng.list_coins()
        coins = [type("C", (), r)() for r in coin_rows]

    inline_msg = session.pop("engine_msg", None)

    return render_template("engine.html",
        show_nav=bool(demo),
        active_page="engine",
        pk_engine=pk,
        engine_address=engine_address,
        engine_contact=engine_contact,
        issuers=issuers,
        coins=coins,
        contacts=engine_data.get("contacts", []),
        inline_msg=inline_msg,
    )


@app.route("/engine/set-address", methods=["POST"])
def engine_set_address():
    engine_data = get_engine_data()
    engine_data["address"] = request.form.get("address", "").strip()
    save_engine_data(engine_data)
    return redirect(url_for("engine_page", demo=request.args.get("demo")))


@app.route("/engine/generate-key", methods=["POST"])
def engine_generate_key():
    get_engine()
    return redirect(url_for("engine_page", demo=request.args.get("demo")))


@app.route("/engine/register-issuer", methods=["POST"])
def engine_register_issuer():
    eng = get_engine()
    try:
        issuer_name = request.form.get("issuer_name", "").strip()
        address = request.form.get("issuer_address", "").strip()
        pk_issuer = request.form["issuer_pk"].strip()
        eng.register_issuer(pk_issuer)

        engine_data = get_engine_data()
        if issuer_name:
            engine_data.setdefault("issuer_names", {})[pk_issuer] = issuer_name

        if request.form.get("save_contact") and issuer_name:
            existing = {c["pk"] for c in engine_data.get("contacts", [])}
            if pk_issuer not in existing:
                engine_data.setdefault("contacts", []).append({"name": issuer_name, "address": address, "pk": pk_issuer})

        save_engine_data(engine_data)

        eng_addr = engine_data.get("address", "")
        notify_engine({"type": "issuer_registered", "pk": pk_issuer[:16]})

        notify_bank({
            "type": "issuer_registered",
            "engine_address": eng_addr,
            "engine_pk": eng.pk_hex,
        })

        session["engine_msg"] = f"Issuer '{issuer_name or pk_issuer[:16]}' geregistreerd!"
    except Exception as e:
        flash(f"Fout: {e}", "error")
    return redirect(url_for("engine_page", demo=request.args.get("demo")))


@app.route("/api/engine/register-issuer", methods=["POST"])
def api_engine_register_issuer():
    """API endpoint: bank stuurt registratieverzoek naar engine (simuleert LoRa)."""
    eng = get_engine()
    data = request.get_json(silent=True) or {}
    issuer_name = data.get("issuer_name", "")
    issuer_address = data.get("issuer_address", "")
    pk_issuer = data.get("issuer_pk", "")
    if not pk_issuer:
        return jsonify({"error": "issuer_pk is verplicht"}), 400
    try:
        eng.register_issuer(pk_issuer)

        engine_data = get_engine_data()
        if issuer_name:
            engine_data.setdefault("issuer_names", {})[pk_issuer] = issuer_name
        existing = {c["pk"] for c in engine_data.get("contacts", [])}
        if pk_issuer not in existing:
            engine_data.setdefault("contacts", []).append({
                "name": issuer_name or issuer_address,
                "address": issuer_address,
                "pk": pk_issuer,
            })
        save_engine_data(engine_data)

        eng_addr = engine_data.get("address", "")
        notify_engine({"type": "issuer_registered", "pk": pk_issuer[:16]})

        notify_bank({
            "type": "issuer_registered",
            "engine_address": eng_addr,
            "engine_pk": eng.pk_hex,
        })

        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/engine/add-contact", methods=["POST"])
def engine_add_contact():
    engine_data = get_engine_data()
    try:
        name = request.form["contact_name"].strip()
        address = request.form["contact_address"].strip()
        pk = request.form.get("contact_pk", "").strip()
        engine_data.setdefault("contacts", []).append({"name": name, "address": address, "pk": pk})
        save_engine_data(engine_data)
        flash(f"Contact '{name}' toegevoegd!", "success")
    except Exception as e:
        flash(f"Fout: {e}", "error")
    return redirect(url_for("engine_page", demo=request.args.get("demo")))


@app.route("/engine/edit-contact/<int:idx>", methods=["POST"])
def engine_edit_contact(idx):
    engine_data = get_engine_data()
    contacts = engine_data.get("contacts", [])
    if 0 <= idx < len(contacts):
        contacts[idx] = {
            "name": request.form["contact_name"].strip(),
            "address": request.form["contact_address"].strip(),
            "pk": request.form.get("contact_pk", "").strip(),
        }
        save_engine_data(engine_data)
        flash("Contact bijgewerkt.", "success")
    return redirect(url_for("engine_page", demo=request.args.get("demo")))


@app.route("/engine/delete-contact/<int:idx>", methods=["POST"])
def engine_delete_contact(idx):
    engine_data = get_engine_data()
    contacts = engine_data.get("contacts", [])
    if 0 <= idx < len(contacts):
        name = contacts[idx]["name"]
        contacts.pop(idx)
        save_engine_data(engine_data)
        flash(f"Contact '{name}' verwijderd.", "info")
    return redirect(url_for("engine_page", demo=request.args.get("demo")))


# --- Wallet ---

@app.route("/wallet/<wallet_id>")
def wallet_page(wallet_id):
    demo = request.args.get("demo")
    w = get_wallet(wallet_id)

    deliver_pending(wallet_id)

    generated_pk = session.pop(f"generated_pk_{wallet_id}", None)
    wallet_contact = format_contact(w.address, generated_pk) if generated_pk else w.address
    inline_msg = session.pop(f"wallet_msg_{wallet_id}", None)

    return render_template("wallet.html",
        show_nav=bool(demo),
        active_page=f"wallet_{wallet_id}",
        wallet_id=wallet_id,
        wallet_address=w.address,
        wallet_pk=generated_pk,
        coins=w.list_coins(),
        balance=w.get_balance(),
        transactions=w.get_transaction_log(),
        contacts=w.get_contacts(),
        wallet_contact=wallet_contact,
        inline_msg=inline_msg,
    )


@app.route("/wallet/<wallet_id>/request-payment", methods=["POST"])
def wallet_request_payment(wallet_id):
    w = get_wallet(wallet_id)
    addr = request.form.get("wallet_address", "").strip()
    if addr:
        w.set_address(addr)
    pk = w.generate_receive_keypair()
    session[f"generated_pk_{wallet_id}"] = pk
    return redirect(url_for("wallet_page", wallet_id=wallet_id, demo=request.args.get("demo")))


@app.route("/wallet/<wallet_id>/pay", methods=["POST"])
def wallet_pay(wallet_id):
    w = get_wallet(wallet_id)
    eng = get_engine()
    try:
        coin_id = request.form["coin_id"]
        recipient_address = request.form["recipient_address"].strip()
        recipient_name = request.form.get("recipient_name", "").strip()
        pk_next = request.form["recipient_pk"].strip()

        tx = w.create_transaction(coin_id, pk_next, recipient_address)
        eng.process_transaction(tx)
        w.confirm_send(coin_id, recipient_address)

        recipient_wid = _find_wallet_id_by_address(recipient_address)
        if recipient_wid:
            deliver_pending(recipient_wid)

        notify_engine({"type": "transaction", "coin_id": coin_id})

        if request.form.get("save_contact"):
            contact_name = recipient_name or recipient_address
            existing_addrs = {c["address"] for c in w.get_contacts()}
            if recipient_address not in existing_addrs:
                w.add_contact(contact_name, recipient_address, "")

        session[f"wallet_msg_{wallet_id}"] = f"Coin verstuurd naar {recipient_name or recipient_address}"
    except (InvalidSignatureError, UnknownCoinError) as e:
        flash(f"Transactie geweigerd: {e}", "error")
    except Exception as e:
        flash(f"Fout: {e}", "error")
    return redirect(url_for("wallet_page", wallet_id=wallet_id, demo=request.args.get("demo")))


@app.route("/wallet/<wallet_id>/add-contact", methods=["POST"])
def wallet_add_contact(wallet_id):
    w = get_wallet(wallet_id)
    try:
        name = request.form["contact_name"].strip()
        address = request.form["contact_address"].strip()
        w.add_contact(name, address, "")
        flash(f"Contact '{name}' toegevoegd!", "success")
    except Exception as e:
        flash(f"Fout: {e}", "error")
    return redirect(url_for("wallet_page", wallet_id=wallet_id, demo=request.args.get("demo")))


@app.route("/wallet/<wallet_id>/edit-contact/<int:idx>", methods=["POST"])
def wallet_edit_contact(wallet_id, idx):
    w = get_wallet(wallet_id)
    try:
        name = request.form["contact_name"].strip()
        address = request.form["contact_address"].strip()
        pk = request.form.get("contact_pk", "").strip()
        w.update_contact(idx, name, address, pk)
        flash("Contact bijgewerkt.", "success")
    except Exception as e:
        flash(f"Fout: {e}", "error")
    return redirect(url_for("wallet_page", wallet_id=wallet_id, demo=request.args.get("demo")))


@app.route("/wallet/<wallet_id>/set-address", methods=["POST"])
def wallet_set_address(wallet_id):
    w = get_wallet(wallet_id)
    addr = request.form.get("address", "").strip()
    if addr:
        w.set_address(addr)
        flash("Adres opgeslagen.", "success")
    return redirect(url_for("wallet_page", wallet_id=wallet_id, demo=request.args.get("demo")))


@app.route("/wallet/<wallet_id>/delete-contact/<int:idx>", methods=["POST"])
def wallet_delete_contact(wallet_id, idx):
    w = get_wallet(wallet_id)
    try:
        w.delete_contact(idx)
        flash("Contact verwijderd.", "info")
    except Exception:
        pass
    return redirect(url_for("wallet_page", wallet_id=wallet_id, demo=request.args.get("demo")))


# --- SSE endpoints ---

@app.route("/api/wallet/<wallet_id>/events")
def wallet_events(wallet_id):
    w = get_wallet(wallet_id)
    return Response(_sse_stream(sse_wallet_clients, key=w.address)(),
                    mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/engine/events")
def engine_events():
    return Response(_sse_stream(sse_engine_clients)(),
                    mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/bank/events")
def bank_events():
    return Response(_sse_stream(sse_bank_clients)(),
                    mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


if __name__ == "__main__":
    app.run(debug=True, port=5000, threaded=True)
