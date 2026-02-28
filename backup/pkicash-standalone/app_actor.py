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
    app.config["ACTOR_ROLE"] = role

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
        name = data.get("name", "")
        pk_tx = data.get("pk_transaction", "")

        if not pk_tx or not name:
            if role == "engine":
                try:
                    e = _get_engine(data_dir)
                    if not pk_tx:
                        pk_tx = e.pk_hex
                    if not name:
                        edata = _get_engine_data(data_dir)
                        name = edata.get("actor_name", "State Engine")
                except Exception:
                    pass
            elif role == "bank":
                try:
                    i = _get_issuer(data_dir)
                    if not pk_tx:
                        pk_tx = i.pk_hex
                    if not name:
                        bdata = _get_bank_data(data_dir)
                        name = bdata.get("actor_name", "Bank")
                except Exception:
                    pass
            elif role == "wallet":
                if not name:
                    w = _get_wallet(data_dir)
                    default_name = f"Wallet {wallet_id.upper()}" if wallet_id else "Wallet"
                    name = w._data.get("actor_name", default_name)
                pk_tx = ""

        transport.announce(name=name, pk_transaction=pk_tx)
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

    @app.route("/api/set-name", methods=["POST"])
    def api_set_name():
        new_name = (request.form.get("actor_name") or "").strip()
        if not new_name:
            flash("Naam mag niet leeg zijn.", "error")
            return redirect(request.referrer or "/")
        if role == "engine":
            edata = _get_engine_data(data_dir)
            edata["actor_name"] = new_name
            _save_engine_data(data_dir, edata)
        elif role == "bank":
            bdata = _get_bank_data(data_dir)
            bdata["actor_name"] = new_name
            _save_bank_data(data_dir, bdata)
        elif role == "wallet":
            w = _get_wallet(data_dir)
            w._data["actor_name"] = new_name
            w._save()
        flash(f"Naam opgeslagen: {new_name}", "success")
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
        print(f"[RNS MSG] role={role} type={msg_type} from={from_role}", flush=True)

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
        {"contacts": [], "issuer_names": {}, "incoming_requests": []},
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
            coins = e.list_coins()

        inline_msg = session.pop("engine_msg", None)
        all_requests = edata.get("incoming_requests", [])
        pending_requests = [r for r in all_requests if r.get("status") == "pending"]
        actor_name = edata.get("actor_name", "State Engine")

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
            incoming_requests=all_requests,
            pending_count=len(pending_requests),
            actor_name=actor_name,
            announce_name=actor_name,
            announce_pk=pk or "",
            role=app.config["ACTOR_ROLE"],
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
                    transport.send(address, "bank", "engine_register_request", {
                        "pk_engine": e.pk_hex,
                        "engine_name": "State Engine",
                        "engine_dest": transport.dest_hash_hex,
                    })
                except Exception:
                    pass

            session["engine_msg"] = f"Issuer '{issuer_name or pk_issuer[:16]}' geregistreerd! Wacht op goedkeuring van bank."
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

    @app.route("/engine/approve-request/<int:idx>", methods=["POST"])
    def engine_approve_request(idx):
        edata = _get_engine_data(data_dir)
        reqs = edata.get("incoming_requests", [])
        if idx < 0 or idx >= len(reqs):
            flash("Verzoek niet gevonden", "error")
            return redirect(url_for("engine_page"))
        req = reqs[idx]
        if req.get("status") != "pending":
            flash("Verzoek is al afgehandeld", "error")
            return redirect(url_for("engine_page"))

        pk_issuer = req["payload"].get("pk_issuer", "")
        issuer_name = req["payload"].get("bank_name", "")
        e = eng()
        try:
            e.register_issuer(pk_issuer)
        except Exception:
            pass

        if issuer_name:
            edata.setdefault("issuer_names", {})[pk_issuer] = issuer_name
        existing = {c.get("pk") for c in edata.get("contacts", [])}
        if pk_issuer not in existing:
            edata.setdefault("contacts", []).append({
                "name": issuer_name or req["from_hash"][:16],
                "address": req["from_hash"],
                "pk": pk_issuer,
            })

        req["status"] = "approved"
        _save_engine_data(data_dir, edata)
        notify_local({"type": "issuer_registered", "pk": pk_issuer[:16]})

        try:
            transport.send(req["from_hash"], req["from_role"], "issuer_confirmed", {
                "pk_engine": e.pk_hex,
                "engine_dest": transport.dest_hash_hex,
            })
        except Exception:
            pass

        session["engine_msg"] = f"Issuer '{issuer_name or pk_issuer[:16]}' goedgekeurd!"
        return redirect(url_for("engine_page"))

    @app.route("/engine/decline-request/<int:idx>", methods=["POST"])
    def engine_decline_request(idx):
        edata = _get_engine_data(data_dir)
        reqs = edata.get("incoming_requests", [])
        if idx < 0 or idx >= len(reqs):
            flash("Verzoek niet gevonden", "error")
            return redirect(url_for("engine_page"))
        req = reqs[idx]
        if req.get("status") != "pending":
            flash("Verzoek is al afgehandeld", "error")
            return redirect(url_for("engine_page"))

        req["status"] = "declined"
        _save_engine_data(data_dir, edata)

        try:
            transport.send(req["from_hash"], req["from_role"], "issuer_declined", {
                "reason": "Afgewezen door engine operator",
            })
        except Exception:
            pass

        session["engine_msg"] = "Verzoek afgewezen"
        return redirect(url_for("engine_page"))

    @app.route("/engine/request-bank-registration", methods=["POST"])
    def engine_request_bank_registration():
        e = eng()
        data = request.get_json(silent=True) or {}
        bank_dest = data.get("bank_dest", "")
        if not bank_dest:
            return jsonify({"error": "bank_dest vereist"}), 400
        try:
            transport.send(bank_dest, "bank", "engine_register_request", {
                "pk_engine": e.pk_hex,
                "engine_name": "State Engine",
                "engine_dest": transport.dest_hash_hex,
            })
            return jsonify({"ok": True})
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500


def _engine_handle_message(app, transport, data_dir, notify_local,
                            msg_type, payload, from_hash, from_role):
    """Process incoming RNS messages for engine."""
    if msg_type == "register_issuer":
        pk_issuer = payload.get("pk_issuer", "")
        if not pk_issuer:
            return

        edata = _get_engine_data(data_dir)
        edata.setdefault("incoming_requests", []).append({
            "request_type": "register_issuer",
            "from_hash": from_hash,
            "from_role": from_role,
            "payload": payload,
            "ts": datetime.now().isoformat(),
            "status": "pending",
        })
        _save_engine_data(data_dir, edata)
        notify_local({"type": "new_request", "request_type": "register_issuer"})

    elif msg_type == "bank_register_response":
        pk_issuer = payload.get("pk_issuer", "")
        bank_name = payload.get("bank_name", "")
        if not pk_issuer:
            return
        e = _get_engine(data_dir)
        try:
            e.register_issuer(pk_issuer)
        except Exception:
            pass
        edata = _get_engine_data(data_dir)
        if bank_name:
            edata.setdefault("issuer_names", {})[pk_issuer] = bank_name
        existing = {c.get("pk") for c in edata.get("contacts", [])}
        if pk_issuer not in existing:
            edata.setdefault("contacts", []).append({
                "name": bank_name or from_hash[:16],
                "address": from_hash,
                "pk": pk_issuer,
            })
        _save_engine_data(data_dir, edata)
        notify_local({"type": "issuer_registered", "pk": pk_issuer[:16]})

    elif msg_type == "bank_register_declined":
        notify_local({"type": "request_declined", "reason": payload.get("reason", "")})

    elif msg_type == "register_coin":
        print(f"[ENGINE] register_coin ONTVANGEN van {from_hash[:16]}", flush=True)
        coin_data = payload.get("coin")
        recipient_dest = payload.get("recipient_dest", "")
        description = payload.get("description")
        pk_next = payload.get("pk_next", "")
        transfer_signature = payload.get("transfer_signature", "")
        print(f"[ENGINE] data check: coin={bool(coin_data)}, recipient={recipient_dest[:16] if recipient_dest else 'LEEG'}, pk_next={bool(pk_next)}, sig={bool(transfer_signature)}", flush=True)
        if not coin_data or not pk_next or not transfer_signature:
            print("[ENGINE] AFGEBROKEN - ontbrekende data!", flush=True)
            return

        e = _get_engine(data_dir)
        coin = Coin.from_dict(coin_data)
        print(f"[ENGINE] coin parsed: {coin.coin_id[:16]}... issuer={coin.pk_issuer[:16]}...", flush=True)
        print(f"[ENGINE] trusted issuers: {e.list_issuers()}", flush=True)
        try:
            e.register_coin(coin, recipient_dest, pk_next, transfer_signature)
            print(f"[ENGINE] register_coin GELUKT!", flush=True)
        except Exception as exc:
            print(f"[ENGINE] register_coin MISLUKT: {exc}", flush=True)
            import traceback
            print(traceback.format_exc(), flush=True)
            return

        notify_local({"type": "coin_registered", "coin_id": coin.coin_id})

        deliveries = e.get_pending_deliveries(recipient_dest)
        print(f"[ENGINE] {len(deliveries)} pending deliveries voor {recipient_dest[:16]}", flush=True)

        def _deliver_coins(deliveries, recipient_dest, description, from_hash):
            for d in deliveries:
                if description:
                    d["description"] = description
                d["sender_dest"] = from_hash
                try:
                    print(f"[ENGINE] coin_delivery sturen naar {recipient_dest[:16]}...", flush=True)
                    transport.send(recipient_dest, "wallet", "coin_delivery", d)
                    print(f"[ENGINE] coin_delivery VERSTUURD!", flush=True)
                except Exception as exc:
                    print(f"[ENGINE] coin_delivery MISLUKT: {exc}", flush=True)

        import threading
        threading.Thread(
            target=_deliver_coins,
            args=(deliveries, recipient_dest, description, from_hash),
            daemon=True,
        ).start()

    elif msg_type == "transaction":
        coin_id = payload.get("coin_id", "")
        pk_next = payload.get("pk_next", "")
        recipient_dest = payload.get("recipient_dest", "")
        signature = payload.get("signature", "")
        description = payload.get("description")
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
            if description:
                d["description"] = description
            d["sender_dest"] = from_hash
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
         "engine_address": None, "engine_pk": None, "incoming_requests": []},
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
        all_requests = bdata.get("incoming_requests", [])
        pending_requests = [r for r in all_requests if r.get("status") == "pending"]
        actor_name = bdata.get("actor_name", "Bank")

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
            incoming_requests=all_requests,
            pending_count=len(pending_requests),
            actor_name=actor_name,
            announce_name=actor_name,
            announce_pk=pk or "",
            role=app.config["ACTOR_ROLE"],
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

            coin, transfer_info = i.issue_coin(waarde, pk_owner, engine_dest, pk_engine)

            bdata = _get_bank_data(data_dir)
            bdata["issued_coins"].append({
                "timestamp": _now(),
                "coin_id": coin.coin_id,
                "waarde": waarde,
                "recipient": recipient_dest,
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
                "pk_next": transfer_info["pk_next"],
                "transfer_signature": transfer_info["transfer_signature"],
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

    @app.route("/bank/approve-request/<int:idx>", methods=["POST"])
    def bank_approve_request(idx):
        bdata = _get_bank_data(data_dir)
        reqs = bdata.get("incoming_requests", [])
        if idx < 0 or idx >= len(reqs):
            flash("Verzoek niet gevonden", "error")
            return redirect(url_for("bank_page"))
        req = reqs[idx]
        if req.get("status") != "pending":
            flash("Verzoek is al afgehandeld", "error")
            return redirect(url_for("bank_page"))

        if req["request_type"] == "engine_register":
            pk_engine = req["payload"].get("pk_engine", "")
            engine_dest = req["payload"].get("engine_dest", req["from_hash"])

            bdata["registered_at_engine"] = True
            bdata["engine_address"] = engine_dest
            bdata["engine_pk"] = pk_engine
            existing = {c["address"] for c in bdata["contacts"]}
            if engine_dest not in existing:
                bdata["contacts"].append({
                    "name": req["payload"].get("engine_name", "State Engine"),
                    "address": engine_dest,
                    "pk": pk_engine,
                })

            req["status"] = "approved"
            _save_bank_data(data_dir, bdata)

            i = iss()
            try:
                transport.send(req["from_hash"], "engine", "bank_register_response", {
                    "pk_issuer": i.pk_hex,
                    "bank_name": "Bank",
                })
            except Exception:
                pass

            session["bank_msg"] = "Engine registratie goedgekeurd!"

        elif req["request_type"] == "coin_request":
            i = iss()
            engine_dest = bdata.get("engine_address", "")
            engine_pk = bdata.get("engine_pk", "")
            if not engine_dest or not engine_pk:
                flash("Niet geregistreerd bij een engine — kan geen coins uitgeven", "error")
                return redirect(url_for("bank_page"))

            wallet_dest = req["payload"].get("wallet_dest", req["from_hash"])
            public_keys = req["payload"].get("public_keys", [])
            form_desc = request.form.get("description", "").strip()[:32]
            coin_description = form_desc or req["payload"].get("description") or None

            if not public_keys:
                flash("Geen publieke sleutels in verzoek", "error")
                return redirect(url_for("bank_page"))

            approve_amount = int(request.form.get("approve_amount", len(public_keys)))
            approve_amount = max(1, approve_amount)
            actual_amount = min(approve_amount, len(public_keys))
            selected_pks = public_keys[:actual_amount]
            if approve_amount > len(public_keys):
                flash(f"Wallet stuurde {len(public_keys)} PK(s), {actual_amount} coin(s) uitgegeven", "info")

            for pk_owner in selected_pks:
                coin, transfer_info = i.issue_coin(1, pk_owner, engine_dest, engine_pk)
                bdata["issued_coins"].append({
                    "timestamp": _now(),
                    "coin_id": coin.coin_id,
                    "waarde": 1,
                    "recipient": wallet_dest,
                    "coin_json": coin.to_dict(),
                })
                reg_payload = {
                    "coin": coin.to_dict(),
                    "recipient_dest": wallet_dest,
                    "pk_next": transfer_info["pk_next"],
                    "transfer_signature": transfer_info["transfer_signature"],
                }
                if coin_description:
                    reg_payload["description"] = coin_description
                try:
                    transport.send(engine_dest, "engine", "register_coin", reg_payload)
                except Exception as exc:
                    flash(f"Fout bij registreren coin: {exc}", "error")

            req["status"] = "approved"
            _save_bank_data(data_dir, bdata)
            session["bank_msg"] = f"{actual_amount} coin(s) uitgegeven aan wallet"

        return redirect(url_for("bank_page"))

    @app.route("/bank/decline-request/<int:idx>", methods=["POST"])
    def bank_decline_request(idx):
        bdata = _get_bank_data(data_dir)
        reqs = bdata.get("incoming_requests", [])
        if idx < 0 or idx >= len(reqs):
            flash("Verzoek niet gevonden", "error")
            return redirect(url_for("bank_page"))
        req = reqs[idx]
        if req.get("status") != "pending":
            flash("Verzoek is al afgehandeld", "error")
            return redirect(url_for("bank_page"))

        req["status"] = "declined"
        _save_bank_data(data_dir, bdata)

        decline_type = {
            "engine_register": "bank_register_declined",
            "coin_request": "coin_request_declined",
        }.get(req["request_type"], "")

        if decline_type:
            try:
                transport.send(req["from_hash"], req["from_role"], decline_type, {
                    "reason": "Afgewezen door bank operator",
                })
            except Exception:
                pass

        session["bank_msg"] = "Verzoek afgewezen"
        return redirect(url_for("bank_page"))


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

    elif msg_type == "engine_register_request":
        bdata = _get_bank_data(data_dir)
        bdata.setdefault("incoming_requests", []).append({
            "request_type": "engine_register",
            "from_hash": from_hash,
            "from_role": from_role,
            "payload": payload,
            "ts": datetime.now().isoformat(),
            "status": "pending",
        })
        _save_bank_data(data_dir, bdata)
        notify_local({"type": "new_request", "request_type": "engine_register"})

    elif msg_type == "issuer_declined":
        notify_local({"type": "request_declined", "reason": payload.get("reason", "")})

    elif msg_type == "coin_request":
        bdata = _get_bank_data(data_dir)
        bdata.setdefault("incoming_requests", []).append({
            "request_type": "coin_request",
            "from_hash": from_hash,
            "from_role": from_role,
            "payload": payload,
            "ts": datetime.now().isoformat(),
            "status": "pending",
        })
        _save_bank_data(data_dir, bdata)
        notify_local({"type": "new_request", "request_type": "coin_request"})


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

        incoming_requests = [
            {**r, "real_idx": i}
            for i, r in enumerate(w._data.get("incoming_requests", []))
            if r.get("status") == "pending"
        ]
        outgoing_coin_requests = w._data.get("outgoing_coin_requests", [])
        outgoing_payment_requests = w._data.get("outgoing_payment_requests", [])

        today = datetime.now().strftime("%Y-%m-%d")
        from datetime import timedelta
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        default_name = f"Wallet {wallet_id.upper()}" if wallet_id else "Wallet"
        actor_name = w._data.get("actor_name", default_name)
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
            incoming_requests=incoming_requests,
            outgoing_coin_requests=outgoing_coin_requests,
            outgoing_payment_requests=outgoing_payment_requests,
            today=today,
            yesterday=yesterday,
            actor_name=actor_name,
            announce_name=actor_name,
            announce_pk="",
            role=app.config["ACTOR_ROLE"],
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
            description = request.form.get("description", "").strip()[:32] or None

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

            tx_payload = {
                "coin_id": coin_id,
                "pk_next": pk_next,
                "recipient_dest": recipient_dest,
                "signature": tx["signature"],
            }
            if description:
                tx_payload["description"] = description

            if engine_dest:
                transport.send(engine_dest, "engine", "transaction", tx_payload)

            w.confirm_send(coin_id, recipient_dest, description=description)

            for req in w._data.get("incoming_requests", []):
                if req.get("status") == "pending" and req.get("from_hash") == recipient_dest:
                    req["status"] = "paid"
            w._save()

            if request.form.get("save_contact"):
                contact_name = recipient_name or recipient_dest[:16]
                existing = {c["address"] for c in w.get_contacts()}
                if recipient_dest not in existing:
                    w.add_contact(contact_name, recipient_dest, "")

            session["wallet_msg"] = f"Coin verstuurd naar {recipient_name or recipient_dest[:16]}"
        except Exception as exc:
            flash(f"Fout: {exc}", "error")
        return redirect(url_for("wallet_page"))

    @app.route("/wallet/<wallet_id>/approve-payment/<int:idx>", methods=["POST"])
    def wallet_approve_payment(wallet_id, idx):
        w = _get_wallet(data_dir)
        reqs = w._data.get("incoming_requests", [])
        if idx < 0 or idx >= len(reqs):
            flash("Verzoek niet gevonden", "error")
            return redirect(url_for("wallet_page"))

        req = reqs[idx]
        if req.get("status") != "pending":
            flash("Verzoek is al afgehandeld", "error")
            return redirect(url_for("wallet_page"))

        recipient_dest = req["from_hash"]
        public_keys = req.get("payload", {}).get("public_keys", [])
        single_pk = req.get("payload", {}).get("pk", "")
        if not public_keys and single_pk:
            public_keys = [single_pk]

        requested_amount = len(public_keys)
        approve_amount = int(request.form.get("approve_amount", requested_amount))
        approve_amount = max(1, min(approve_amount, requested_amount))
        description = request.form.get("description", "").strip()[:32] or req.get("payload", {}).get("description") or None

        available_coins = list(w._data.get("coins", {}).items())
        if not available_coins:
            flash("Geen coins beschikbaar om te betalen", "error")
            return redirect(url_for("wallet_page"))

        actual_amount = min(approve_amount, len(available_coins))
        selected_coins = available_coins[:actual_amount]
        selected_pks = public_keys[:actual_amount]

        sent = 0
        for (coin_id, coin_entry), pk_next in zip(selected_coins, selected_pks):
            coin_data = coin_entry["coin"]
            engine_dest = coin_data.get("state_engine_endpoint", "")
            if engine_dest.startswith("http"):
                for dh, info in transport.get_announces().items():
                    if info.get("role", "").startswith("engine"):
                        engine_dest = dh
                        break

            try:
                tx = w.create_transaction(coin_id, pk_next, recipient_dest)
                tx_payload = {
                    "coin_id": coin_id,
                    "pk_next": pk_next,
                    "recipient_dest": recipient_dest,
                    "signature": tx["signature"],
                }
                if description:
                    tx_payload["description"] = description
                if engine_dest:
                    transport.send(engine_dest, "engine", "transaction", tx_payload)
                w.confirm_send(coin_id, recipient_dest, description=description)
                sent += 1
            except Exception as exc:
                flash(f"Fout bij coin {coin_id[:8]}: {exc}", "error")

        req["status"] = "paid"
        w._save()

        if approve_amount > len(available_coins):
            flash(f"Slechts {actual_amount} coin(s) beschikbaar, {actual_amount} verstuurd", "info")
        session["wallet_msg"] = f"{sent} coin(s) verstuurd"
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

    @app.route("/wallet/<wallet_id>/request-coins", methods=["POST"])
    def wallet_request_coins(wallet_id):
        w = _get_wallet(data_dir)
        try:
            bank_dest = request.form["bank_address"].strip()
            if "|" in bank_dest:
                bank_dest = bank_dest.split("|")[0]
            amount = int(request.form["amount"])
            if amount < 1:
                raise ValueError("Aantal moet minimaal 1 zijn")

            public_keys = [w.generate_receive_keypair() for _ in range(amount)]

            transport.send(bank_dest, "bank", "coin_request", {
                "amount": amount,
                "wallet_dest": transport.dest_hash_hex,
                "public_keys": public_keys,
            })

            w._data.setdefault("outgoing_coin_requests", []).append({
                "bank_dest": bank_dest,
                "amount": amount,
                "public_keys": list(public_keys),
                "ts": _now(),
                "status": "pending",
            })
            w._save()

            session["wallet_msg"] = f"Coin-aanvraag ({amount}x) verstuurd naar bank"
        except Exception as exc:
            flash(f"Fout: {exc}", "error")
        return redirect(url_for("wallet_page"))

    @app.route("/wallet/<wallet_id>/send-coin-request", methods=["POST"])
    def wallet_send_coin_request(wallet_id):
        w = _get_wallet(data_dir)
        data = request.get_json(silent=True) or {}
        bank_dest = data.get("bank_dest", "")
        amount = int(data.get("amount", 1))
        if "|" in bank_dest:
            bank_dest = bank_dest.split("|")[0]
        if not bank_dest:
            return jsonify({"error": "bank_dest vereist"}), 400
        if amount < 1:
            return jsonify({"error": "Aantal moet minimaal 1 zijn"}), 400
        try:
            public_keys = [w.generate_receive_keypair() for _ in range(amount)]
            transport.send(bank_dest, "bank", "coin_request", {
                "amount": amount,
                "wallet_dest": transport.dest_hash_hex,
                "public_keys": public_keys,
            })
            w._data.setdefault("outgoing_coin_requests", []).append({
                "bank_dest": bank_dest,
                "amount": amount,
                "public_keys": list(public_keys),
                "ts": _now(),
                "status": "pending",
            })
            w._save()
            return jsonify({"ok": True})
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.route("/wallet/<wallet_id>/send-payment-request", methods=["POST"])
    def wallet_send_payment_request(wallet_id):
        w = _get_wallet(data_dir)
        data = request.get_json(silent=True) or {}
        dest_hash = data.get("dest_hash", "")
        amount = data.get("amount")
        description = (data.get("description") or "")[:32] or None
        if "|" in dest_hash:
            dest_hash = dest_hash.split("|")[0]
        if not dest_hash:
            return jsonify({"error": "dest_hash vereist"}), 400

        announces = transport.get_announces()
        target_info = announces.get(dest_hash, {})
        target_role = target_info.get("role", "")

        try:
            n = int(amount) if amount else 1
            if n < 1:
                n = 1

            if target_role == "bank":
                public_keys = [w.generate_receive_keypair() for _ in range(n)]
                cr_payload = {
                    "amount": n,
                    "wallet_dest": transport.dest_hash_hex,
                    "public_keys": public_keys,
                }
                if description:
                    cr_payload["description"] = description
                transport.send(dest_hash, "bank", "coin_request", cr_payload)
                w._data.setdefault("outgoing_coin_requests", []).append({
                    "bank_dest": dest_hash,
                    "amount": n,
                    "public_keys": list(public_keys),
                    "ts": _now(),
                    "status": "pending",
                    "description": description,
                })
                w._save()
            else:
                public_keys = [w.generate_receive_keypair() for _ in range(n)]
                pr_payload = {
                    "address": transport.dest_hash_hex,
                    "pk": public_keys[0],
                    "public_keys": public_keys,
                    "amount": n,
                }
                if description:
                    pr_payload["description"] = description
                transport.send(dest_hash, "wallet", "payment_request", pr_payload)
                w._data.setdefault("outgoing_payment_requests", []).append({
                    "dest": dest_hash,
                    "pk": public_keys[0],
                    "public_keys": list(public_keys),
                    "amount": n,
                    "ts": _now(),
                    "status": "pending",
                    "description": description,
                })
                w._save()

            return jsonify({"ok": True})
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.route("/wallet/<wallet_id>/accept-request/<int:idx>", methods=["POST"])
    def wallet_accept_request(wallet_id, idx):
        w = _get_wallet(data_dir)
        requests = w._data.get("incoming_requests", [])
        if idx < 0 or idx >= len(requests):
            flash("Verzoek niet gevonden", "error")
            return redirect(url_for("wallet_page"))

        req = requests[idx]
        pk_hex = w.generate_receive_keypair()

        try:
            transport.send(req["from_hash"], "wallet", "payment_response", {
                "pk": pk_hex,
                "address": transport.dest_hash_hex,
                "original_request": req.get("payload", {}),
            })
            req["status"] = "accepted"
            req["generated_pk"] = pk_hex
            w._save()
            session["wallet_msg"] = f"Betaalverzoek geaccepteerd, PK verzonden"
        except Exception as exc:
            flash(f"Fout bij verzenden: {exc}", "error")
        return redirect(url_for("wallet_page"))

    @app.route("/wallet/<wallet_id>/decline-request/<int:idx>", methods=["POST"])
    def wallet_decline_request(wallet_id, idx):
        w = _get_wallet(data_dir)
        reqs = w._data.get("incoming_requests", [])
        if 0 <= idx < len(reqs):
            req = reqs[idx]
            req["status"] = "declined"
            w._save()
            try:
                transport.send(req["from_hash"], "wallet", "payment_declined", {
                    "address": transport.dest_hash_hex,
                    "reason": "Geweigerd door ontvanger",
                })
            except Exception:
                pass
        return redirect(url_for("wallet_page"))


def _wallet_handle_message(app, transport, data_dir, wallet_id, notify_local,
                            msg_type, payload, from_hash, from_role):
    """Process incoming RNS messages for wallet."""
    if msg_type in ("coin_delivery", "coin_transfer"):
        w = _get_wallet(data_dir)
        try:
            w.receive_from_engine(payload)
            coin_data = payload.get("coin", {})
            pk_current = coin_data.get("pk_current", "")

            if pk_current:
                matched = False
                for req in w._data.get("outgoing_coin_requests", []):
                    if req.get("status") not in ("pending", "partial"):
                        continue
                    pks = req.get("public_keys", [])
                    if pk_current in pks:
                        pks.remove(pk_current)
                        req["received"] = req.get("received", 0) + 1
                        req["status"] = "approved" if not pks else "partial"
                        w._save()
                        matched = True
                        break

                if not matched:
                    for req in w._data.get("outgoing_payment_requests", []):
                        if req.get("status") not in ("pending", "partial"):
                            continue
                        req_pks = req.get("public_keys", [])
                        if pk_current in req_pks:
                            req_pks.remove(pk_current)
                            req["received"] = req.get("received", 0) + 1
                            req["status"] = "paid" if not req_pks else "partial"
                            w._save()
                            break
                        if req.get("pk") == pk_current and not req_pks:
                            req["received"] = req.get("received", 0) + 1
                            req["status"] = "paid"
                            w._save()
                            break

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

    elif msg_type == "payment_request":
        w = _get_wallet(data_dir)
        w._data.setdefault("incoming_requests", []).append({
            "from_hash": from_hash,
            "from_role": from_role,
            "payload": payload,
            "ts": _now(),
            "status": "pending",
        })
        w._save()
        notify_local({
            "type": "payment_request",
            "from_hash": from_hash,
            "address": payload.get("address", ""),
            "pk": payload.get("pk", ""),
        })

    elif msg_type == "payment_response":
        w = _get_wallet(data_dir)
        w._data.setdefault("received_responses", []).append({
            "from_hash": from_hash,
            "pk": payload.get("pk", ""),
            "address": payload.get("address", ""),
            "ts": payload.get("ts", ""),
        })
        w._save()
        notify_local({
            "type": "payment_response",
            "from_hash": from_hash,
            "pk": payload.get("pk", ""),
            "address": payload.get("address", ""),
        })

    elif msg_type == "coin_request_declined":
        w = _get_wallet(data_dir)
        for req in w._data.get("outgoing_coin_requests", []):
            if req.get("status") == "pending" and req.get("bank_dest") == from_hash:
                req["status"] = "declined"
                break
        w._save()
        notify_local({"type": "coin_request_declined", "reason": payload.get("reason", "")})

    elif msg_type == "payment_declined":
        w = _get_wallet(data_dir)
        for req in w._data.get("outgoing_payment_requests", []):
            if req.get("status") == "pending" and req.get("dest") == from_hash:
                req["status"] = "declined"
                break
        w._save()
        notify_local({"type": "payment_declined", "from_hash": from_hash})
