"""
Flask app factory for PKI Cash — one actor per process, RNS transport.

Usage: called from run.py, not directly.
"""

import json
import os
import queue
import threading
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, jsonify, session, Response,
)

from src.issuer import Issuer
from src.engine import StateEngine, InvalidSignatureError, UntrustedIssuerError, UnknownCoinError
from src.wallet import Wallet
from src.coin import Coin


def _load_json(path, default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default


def _save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def create_app(role, transport, data_dir, wallet_id=None):
    app = Flask(__name__,
                template_folder=os.path.join(os.path.dirname(__file__), "templates"),
                static_folder=os.path.join(os.path.dirname(__file__), "static"))
    app.secret_key = os.urandom(32)

    os.makedirs(data_dir, exist_ok=True)

    # ── local SSE (browser <-> own Flask only) ──────────────

    sse_clients: list[queue.Queue] = []
    sse_lock = threading.Lock()

    def notify_local(event_data: dict):
        with sse_lock:
            dead = []
            for q in sse_clients:
                try:
                    q.put_nowait(event_data)
                except queue.Full:
                    dead.append(q)
            for q in dead:
                sse_clients.remove(q)

    def _sse_stream():
        def stream():
            q = queue.Queue(maxsize=50)
            with sse_lock:
                sse_clients.append(q)
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
                    if q in sse_clients:
                        sse_clients.remove(q)
        return stream

    # ── common API routes ───────────────────────────────────

    @app.route("/api/events")
    def api_events():
        return Response(
            _sse_stream()(),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.route("/api/announces")
    def api_announces():
        return jsonify(transport.get_announces())

    @app.route("/api/inbox")
    def api_inbox():
        return jsonify(transport.peek_inbox())

    @app.route("/api/message-log")
    def api_message_log():
        return jsonify(transport.get_message_log())

    @app.route("/api/announce", methods=["POST"])
    def api_do_announce():
        data = request.get_json(silent=True) or {}
        transport.announce(
            name=data.get("name", ""),
            pk_transaction=data.get("pk_transaction", ""),
        )
        return jsonify({"ok": True, "dest_hash": transport.dest_hash_hex})

    @app.route("/api/send", methods=["POST"])
    def api_send():
        data = request.get_json(silent=True) or {}
        try:
            transport.send(
                dest_hash_hex=data["dest_hash"],
                target_role=data["target_role"],
                msg_type=data["msg_type"],
                payload=data.get("payload", {}),
            )
            return jsonify({"ok": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/transport-info")
    def api_transport_info():
        return jsonify({
            "role": role,
            "dest_hash": transport.dest_hash_hex,
            "wallet_id": wallet_id,
        })

    @app.route("/api/add-contact", methods=["POST"])
    def api_add_contact():
        name = request.form.get("contact_name", "").strip()
        address = request.form.get("contact_address", "").strip()
        pk = request.form.get("contact_pk", "").strip()
        if not name:
            name = address[:16] if address else "onbekend"
        try:
            if role == "engine":
                edata = _get_engine_data(data_dir)
                edata.setdefault("contacts", []).append({"name": name, "address": address, "pk": pk})
                _save_engine_data(data_dir, edata)
            elif role == "bank":
                bdata = _get_bank_data(data_dir)
                bdata.setdefault("contacts", []).append({"name": name, "address": address, "pk": pk})
                _save_bank_data(data_dir, bdata)
            elif role == "wallet":
                w = _get_wallet(data_dir)
                w.add_contact(name, address, pk)
            flash(f"Contact '{name}' toegevoegd!", "success")
        except Exception as exc:
            flash(f"Fout: {exc}", "error")
        return redirect(request.referrer or "/")

    # ── role-specific routes ────────────────────────────────

    if role == "engine":
        _register_engine_routes(app, transport, data_dir, notify_local)
    elif role == "bank":
        _register_bank_routes(app, transport, data_dir, notify_local)
    elif role == "wallet":
        _register_wallet_routes(app, transport, data_dir, wallet_id, notify_local)

    # ── RNS message handler ─────────────────────────────────

    def handle_rns_message(msg):
        msg_type = msg.get("type", "")
        payload = msg.get("payload", {})
        from_hash = msg.get("from_hash", "")
        from_role = msg.get("from_role", "")

        if role == "engine":
            _engine_handle_message(app, transport, data_dir, notify_local,
                                   msg_type, payload, from_hash, from_role)
        elif role == "bank":
            _bank_handle_message(app, transport, data_dir, notify_local,
                                  msg_type, payload, from_hash, from_role)
        elif role == "wallet":
            _wallet_handle_message(app, transport, data_dir, wallet_id, notify_local,
                                    msg_type, payload, from_hash, from_role)

    transport.on_message(handle_rns_message)
    transport.on_announce(lambda info: notify_local({"type": "announce", **info}))

    return app


# ════════════════════════════════════════════════════════════
#  ENGINE
# ════════════════════════════════════════════════════════════

def _get_engine(data_dir):
    db_path = os.path.join(data_dir, "engine.db")
    key_path = os.path.join(data_dir, "engine.key")
    if os.path.exists(key_path):
        return StateEngine.load_key(key_path, db_path=db_path)
    eng = StateEngine(db_path=db_path)
    eng.save_key(key_path)
    return eng


def _get_engine_data(data_dir):
    return _load_json(
        os.path.join(data_dir, "engine_data.json"),
        {"contacts": [], "issuer_names": {}},
    )


def _save_engine_data(data_dir, data):
    _save_json(os.path.join(data_dir, "engine_data.json"), data)


def _register_engine_routes(app, transport, data_dir, notify_local):
    engine_instance = [None]

    def eng():
        if engine_instance[0] is None:
            engine_instance[0] = _get_engine(data_dir)
        return engine_instance[0]

    @app.route("/")
    def engine_page():
        key_path = os.path.join(data_dir, "engine.key")
        pk = None
        issuers = []
        coins = []
        edata = _get_engine_data(data_dir)

        if os.path.exists(key_path):
            e = eng()
            pk = e.pk_hex
            raw_issuers = e.list_issuers()
            names = edata.get("issuer_names", {})
            issuers = [{"pk": p, "name": names.get(p, "")} for p in raw_issuers]
            coins = [type("C", (), r)() for r in e.list_coins()]

        inline_msg = session.pop("engine_msg", None)

        return render_template("engine.html",
            show_nav=False,
            active_page="engine",
            pk_engine=pk,
            engine_address=transport.dest_hash_hex,
            engine_contact=f"{transport.dest_hash_hex}|{pk}" if pk else "",
            issuers=issuers,
            coins=coins,
            contacts=edata.get("contacts", []),
            inline_msg=inline_msg,
            dest_hash=transport.dest_hash_hex,
            announces=transport.get_announces(),
        )

    @app.route("/engine/generate-key", methods=["POST"])
    def engine_generate_key():
        e = eng()
        transport.announce(name="State Engine", pk_transaction=e.pk_hex)
        return redirect(url_for("engine_page"))

    @app.route("/engine/register-issuer", methods=["POST"])
    def engine_register_issuer():
        e = eng()
        try:
            issuer_name = request.form.get("issuer_name", "").strip()
            address = request.form.get("issuer_address", "").strip()
            pk_issuer = request.form["issuer_pk"].strip()
            e.register_issuer(pk_issuer)

            edata = _get_engine_data(data_dir)
            if issuer_name:
                edata.setdefault("issuer_names", {})[pk_issuer] = issuer_name
            if request.form.get("save_contact") and issuer_name:
                existing = {c["pk"] for c in edata.get("contacts", [])}
                if pk_issuer not in existing:
                    edata.setdefault("contacts", []).append({
                        "name": issuer_name, "address": address, "pk": pk_issuer,
                    })
            _save_engine_data(data_dir, edata)

            notify_local({"type": "issuer_registered", "pk": pk_issuer[:16]})

            if address:
                try:
                    transport.send(address, "bank", "issuer_confirmed", {
                        "pk_engine": e.pk_hex,
                        "engine_dest": transport.dest_hash_hex,
                    })
                except Exception:
                    pass

            session["engine_msg"] = f"Issuer '{issuer_name or pk_issuer[:16]}' geregistreerd!"
        except Exception as exc:
            flash(f"Fout: {exc}", "error")
        return redirect(url_for("engine_page"))

    @app.route("/engine/add-contact", methods=["POST"])
    def engine_add_contact():
        edata = _get_engine_data(data_dir)
        try:
            name = request.form["contact_name"].strip()
            address = request.form["contact_address"].strip()
            pk = request.form.get("contact_pk", "").strip()
            edata.setdefault("contacts", []).append({"name": name, "address": address, "pk": pk})
            _save_engine_data(data_dir, edata)
            flash(f"Contact '{name}' toegevoegd!", "success")
        except Exception as exc:
            flash(f"Fout: {exc}", "error")
        return redirect(url_for("engine_page"))

    @app.route("/engine/edit-contact/<int:idx>", methods=["POST"])
    def engine_edit_contact(idx):
        edata = _get_engine_data(data_dir)
        contacts = edata.get("contacts", [])
        if 0 <= idx < len(contacts):
            contacts[idx] = {
                "name": request.form["contact_name"].strip(),
                "address": request.form["contact_address"].strip(),
                "pk": request.form.get("contact_pk", "").strip(),
            }
            _save_engine_data(data_dir, edata)
        return redirect(url_for("engine_page"))

    @app.route("/engine/delete-contact/<int:idx>", methods=["POST"])
    def engine_delete_contact(idx):
        edata = _get_engine_data(data_dir)
        contacts = edata.get("contacts", [])
        if 0 <= idx < len(contacts):
            contacts.pop(idx)
            _save_engine_data(data_dir, edata)
        return redirect(url_for("engine_page"))


def _engine_handle_message(app, transport, data_dir, notify_local,
                            msg_type, payload, from_hash, from_role):
    """Process incoming RNS messages for engine."""
    if msg_type == "register_issuer":
        pk_issuer = payload.get("pk_issuer", "")
        issuer_name = payload.get("bank_name", "")
        if not pk_issuer:
            return

        e = _get_engine(data_dir)
        try:
            e.register_issuer(pk_issuer)
        except Exception:
            pass

        edata = _get_engine_data(data_dir)
        if issuer_name:
            edata.setdefault("issuer_names", {})[pk_issuer] = issuer_name
        existing = {c.get("pk") for c in edata.get("contacts", [])}
        if pk_issuer not in existing:
            edata.setdefault("contacts", []).append({
                "name": issuer_name or from_hash[:16],
                "address": from_hash,
                "pk": pk_issuer,
            })
        _save_engine_data(data_dir, edata)

        notify_local({"type": "issuer_registered", "pk": pk_issuer[:16]})

        try:
            transport.send(from_hash, from_role, "issuer_confirmed", {
                "pk_engine": e.pk_hex,
                "engine_dest": transport.dest_hash_hex,
            })
        except Exception:
            pass

    elif msg_type == "register_coin":
        coin_data = payload.get("coin")
        recipient_dest = payload.get("recipient_dest", "")
        if not coin_data:
            return

        e = _get_engine(data_dir)
        coin = Coin.from_dict(coin_data)
        try:
            e.register_coin(coin, recipient_dest)
        except Exception:
            return

        notify_local({"type": "coin_registered", "coin_id": coin.coin_id})

        deliveries = e.get_pending_deliveries(recipient_dest)
        for d in deliveries:
            try:
                transport.send(recipient_dest, "wallet", "coin_delivery", d)
            except Exception:
                pass

    elif msg_type == "transaction":
        coin_id = payload.get("coin_id", "")
        pk_next = payload.get("pk_next", "")
        recipient_dest = payload.get("recipient_dest", "")
        signature = payload.get("signature", "")
        if not coin_id:
            return

        e = _get_engine(data_dir)
        try:
            confirmation = e.process_transaction({
                "coin_id": coin_id,
                "pk_next": pk_next,
                "recipient_address": recipient_dest,
                "signature": signature,
            })
        except Exception:
            return

        notify_local({"type": "transaction", "coin_id": coin_id})

        try:
            transport.send(from_hash, from_role, "tx_confirmed", {
                "coin_id": coin_id, "status": "confirmed",
            })
        except Exception:
            pass

        deliveries = e.get_pending_deliveries(recipient_dest)
        for d in deliveries:
            try:
                transport.send(recipient_dest, "wallet", "coin_transfer", d)
            except Exception:
                pass


# ════════════════════════════════════════════════════════════
#  BANK
# ════════════════════════════════════════════════════════════

def _get_bank_data(data_dir):
    return _load_json(
        os.path.join(data_dir, "bank.json"),
        {"issued_coins": [], "contacts": [], "registered_at_engine": False,
         "engine_address": None, "engine_pk": None},
    )


def _save_bank_data(data_dir, data):
    _save_json(os.path.join(data_dir, "bank.json"), data)


def _get_issuer(data_dir):
    key_path = os.path.join(data_dir, "issuer.key")
    if os.path.exists(key_path):
        return Issuer.load_key(key_path)
    iss = Issuer()
    iss.save_key(key_path)
    return iss


def _register_bank_routes(app, transport, data_dir, notify_local):
    issuer_instance = [None]

    def iss():
        if issuer_instance[0] is None:
            issuer_instance[0] = _get_issuer(data_dir)
        return issuer_instance[0]

    @app.route("/")
    def bank_page():
        key_path = os.path.join(data_dir, "issuer.key")
        pk = None
        bank_contact = None
        bdata = _get_bank_data(data_dir)

        if os.path.exists(key_path):
            pk = iss().pk_hex
            bank_contact = f"{transport.dest_hash_hex}|{pk}"

        inline_msg = session.pop("bank_msg", None)

        return render_template("bank.html",
            show_nav=False,
            active_page="bank",
            pk_issuer=pk,
            bank_address=transport.dest_hash_hex,
            bank_pk=pk,
            bank_contact=bank_contact or "",
            issued_coins=bdata["issued_coins"],
            contacts=bdata["contacts"],
            registered_at_engine=bdata.get("registered_at_engine", False),
            engine_address=bdata.get("engine_address"),
            engine_pk=bdata.get("engine_pk"),
            inline_msg=inline_msg,
            dest_hash=transport.dest_hash_hex,
            announces=transport.get_announces(),
        )

    @app.route("/bank/generate-key", methods=["POST"])
    def bank_generate_key():
        i = iss()
        transport.announce(name="Bank", pk_transaction=i.pk_hex)
        return redirect(url_for("bank_page"))

    @app.route("/bank/issue-coin", methods=["POST"])
    def bank_issue_coin():
        i = iss()
        try:
            waarde = int(request.form["waarde"])
            engine_dest = request.form["engine_address"].strip()
            pk_engine = request.form["engine_pk"].strip()
            recipient_dest = request.form["recipient_address"].strip()
            pk_owner = request.form["recipient_pk"].strip()

            coin = i.issue_coin(waarde, pk_owner, engine_dest, pk_engine)

            bdata = _get_bank_data(data_dir)
            bdata["issued_coins"].append({
                "timestamp": _now(),
                "coin_id": coin.coin_id,
                "waarde": waarde,
                "recipient": recipient_dest[:16] + "…",
                "coin_json": coin.to_dict(),
            })

            if request.form.get("save_contacts"):
                existing = {c["address"] for c in bdata["contacts"]}
                engine_name = request.form.get("engine_name", "").strip() or engine_dest[:16]
                recip_name = request.form.get("recipient_name", "").strip() or recipient_dest[:16]
                if engine_dest not in existing:
                    bdata["contacts"].append({"name": engine_name, "address": engine_dest, "pk": pk_engine})
                if recipient_dest not in existing:
                    bdata["contacts"].append({"name": recip_name, "address": recipient_dest, "pk": pk_owner})

            _save_bank_data(data_dir, bdata)

            transport.send(engine_dest, "engine", "register_coin", {
                "coin": coin.to_dict(),
                "recipient_dest": recipient_dest,
            })

            session["bank_msg"] = f"Coin (waarde {waarde}) verstuurd naar engine voor registratie"
        except Exception as exc:
            flash(f"Fout: {exc}", "error")
        return redirect(url_for("bank_page"))

    @app.route("/bank/register-at-engine", methods=["POST"])
    def bank_register_at_engine():
        i = iss()
        data = request.get_json(silent=True) or {}
        engine_dest = data.get("engine_dest", "")
        if not engine_dest:
            return jsonify({"error": "engine_dest vereist"}), 400
        try:
            transport.send(engine_dest, "engine", "register_issuer", {
                "pk_issuer": i.pk_hex,
                "bank_name": "Bank",
            })
            return jsonify({"ok": True})
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.route("/bank/add-contact", methods=["POST"])
    def bank_add_contact():
        bdata = _get_bank_data(data_dir)
        name = request.form["contact_name"].strip()
        address = request.form["contact_address"].strip()
        pk = request.form.get("contact_pk", "").strip()
        bdata["contacts"].append({"name": name, "address": address, "pk": pk})
        _save_bank_data(data_dir, bdata)
        flash(f"Contact '{name}' toegevoegd!", "success")
        return redirect(url_for("bank_page"))

    @app.route("/bank/edit-contact/<int:idx>", methods=["POST"])
    def bank_edit_contact(idx):
        bdata = _get_bank_data(data_dir)
        if 0 <= idx < len(bdata["contacts"]):
            bdata["contacts"][idx] = {
                "name": request.form["contact_name"].strip(),
                "address": request.form["contact_address"].strip(),
                "pk": request.form.get("contact_pk", "").strip(),
            }
            _save_bank_data(data_dir, bdata)
        return redirect(url_for("bank_page"))

    @app.route("/bank/delete-contact/<int:idx>", methods=["POST"])
    def bank_delete_contact(idx):
        bdata = _get_bank_data(data_dir)
        if 0 <= idx < len(bdata["contacts"]):
            bdata["contacts"].pop(idx)
            _save_bank_data(data_dir, bdata)
        return redirect(url_for("bank_page"))

    @app.route("/bank/confirm-engine-registration", methods=["POST"])
    def bank_confirm_engine_registration():
        data = request.get_json(silent=True) or {}
        engine_address = data.get("engine_address", "")
        engine_pk = data.get("engine_pk", "")
        if not engine_pk:
            return jsonify({"error": "missing fields"}), 400
        bdata = _get_bank_data(data_dir)
        bdata["registered_at_engine"] = True
        bdata["engine_address"] = engine_address
        bdata["engine_pk"] = engine_pk
        existing = {c["address"] for c in bdata["contacts"]}
        if engine_address and engine_address not in existing:
            bdata["contacts"].append({"name": "State Engine", "address": engine_address, "pk": engine_pk})
        _save_bank_data(data_dir, bdata)
        return jsonify({"ok": True})


def _bank_handle_message(app, transport, data_dir, notify_local,
                          msg_type, payload, from_hash, from_role):
    """Process incoming RNS messages for bank."""
    if msg_type == "issuer_confirmed":
        pk_engine = payload.get("pk_engine", "")
        engine_dest = payload.get("engine_dest", from_hash)

        bdata = _get_bank_data(data_dir)
        bdata["registered_at_engine"] = True
        bdata["engine_address"] = engine_dest
        bdata["engine_pk"] = pk_engine
        existing = {c["address"] for c in bdata["contacts"]}
        if engine_dest not in existing:
            bdata["contacts"].append({
                "name": "State Engine", "address": engine_dest, "pk": pk_engine,
            })
        _save_bank_data(data_dir, bdata)

        notify_local({
            "type": "issuer_registered",
            "engine_address": engine_dest,
            "engine_pk": pk_engine,
        })


# ════════════════════════════════════════════════════════════
#  WALLET
# ════════════════════════════════════════════════════════════

def _get_wallet(data_dir):
    return Wallet(os.path.join(data_dir, "wallet.json"))


def _register_wallet_routes(app, transport, data_dir, wallet_id, notify_local):

    @app.route("/")
    def wallet_page():
        w = _get_wallet(data_dir)
        generated_pk = session.pop(f"generated_pk", None)
        wallet_contact = f"{transport.dest_hash_hex}|{generated_pk}" if generated_pk else transport.dest_hash_hex
        inline_msg = session.pop("wallet_msg", None)

        return render_template("wallet.html",
            show_nav=False,
            active_page=f"wallet_{wallet_id}",
            wallet_id=wallet_id,
            wallet_address=transport.dest_hash_hex,
            wallet_pk=generated_pk,
            coins=w.list_coins(),
            balance=w.get_balance(),
            transactions=w.get_transaction_log(),
            contacts=w.get_contacts(),
            wallet_contact=wallet_contact,
            inline_msg=inline_msg,
            dest_hash=transport.dest_hash_hex,
            announces=transport.get_announces(),
        )

    @app.route("/wallet/<wallet_id>/request-payment", methods=["POST"])
    def wallet_request_payment(wallet_id):
        w = _get_wallet(data_dir)
        pk = w.generate_receive_keypair()
        session["generated_pk"] = pk
        return redirect(url_for("wallet_page"))

    @app.route("/wallet/<wallet_id>/pay", methods=["POST"])
    def wallet_pay(wallet_id):
        w = _get_wallet(data_dir)
        try:
            coin_id = request.form["coin_id"]
            recipient_dest = request.form["recipient_address"].strip()
            recipient_name = request.form.get("recipient_name", "").strip()
            pk_next = request.form["recipient_pk"].strip()

            engine_dest = None
            coin_entry = w._data["coins"].get(coin_id)
            if coin_entry:
                coin_data = coin_entry["coin"]
                engine_dest = coin_data.get("state_engine_endpoint", "")
                if engine_dest.startswith("http"):
                    announces = transport.get_announces()
                    for dh, info in announces.items():
                        if info.get("role", "").startswith("engine"):
                            engine_dest = dh
                            break

            tx = w.create_transaction(coin_id, pk_next, recipient_dest)

            if engine_dest:
                transport.send(engine_dest, "engine", "transaction", {
                    "coin_id": coin_id,
                    "pk_next": pk_next,
                    "recipient_dest": recipient_dest,
                    "signature": tx["signature"],
                })

            w.confirm_send(coin_id, recipient_dest)

            if request.form.get("save_contact"):
                contact_name = recipient_name or recipient_dest[:16]
                existing = {c["address"] for c in w.get_contacts()}
                if recipient_dest not in existing:
                    w.add_contact(contact_name, recipient_dest, "")

            session["wallet_msg"] = f"Coin verstuurd naar {recipient_name or recipient_dest[:16]}"
        except Exception as exc:
            flash(f"Fout: {exc}", "error")
        return redirect(url_for("wallet_page"))

    @app.route("/wallet/<wallet_id>/add-contact", methods=["POST"])
    def wallet_add_contact(wallet_id):
        w = _get_wallet(data_dir)
        name = request.form["contact_name"].strip()
        address = request.form["contact_address"].strip()
        w.add_contact(name, address, "")
        flash(f"Contact '{name}' toegevoegd!", "success")
        return redirect(url_for("wallet_page"))

    @app.route("/wallet/<wallet_id>/edit-contact/<int:idx>", methods=["POST"])
    def wallet_edit_contact(wallet_id, idx):
        w = _get_wallet(data_dir)
        name = request.form["contact_name"].strip()
        address = request.form["contact_address"].strip()
        pk = request.form.get("contact_pk", "").strip()
        w.update_contact(idx, name, address, pk)
        return redirect(url_for("wallet_page"))

    @app.route("/wallet/<wallet_id>/delete-contact/<int:idx>", methods=["POST"])
    def wallet_delete_contact(wallet_id, idx):
        w = _get_wallet(data_dir)
        w.delete_contact(idx)
        return redirect(url_for("wallet_page"))

    @app.route("/wallet/<wallet_id>/set-address", methods=["POST"])
    def wallet_set_address(wallet_id):
        return redirect(url_for("wallet_page"))


def _wallet_handle_message(app, transport, data_dir, wallet_id, notify_local,
                            msg_type, payload, from_hash, from_role):
    """Process incoming RNS messages for wallet."""
    if msg_type in ("coin_delivery", "coin_transfer"):
        w = _get_wallet(data_dir)
        try:
            w.receive_from_engine(payload)
            coin_data = payload.get("coin", {})
            notify_local({
                "type": "coin_received",
                "coin_id": coin_data.get("coin_id", ""),
                "waarde": coin_data.get("waarde", "?"),
                "status": payload.get("confirmation", {}).get("status", ""),
            })
        except Exception:
            pass

    elif msg_type == "tx_confirmed":
        notify_local({
            "type": "tx_confirmed",
            "coin_id": payload.get("coin_id", ""),
            "status": payload.get("status", ""),
        })
