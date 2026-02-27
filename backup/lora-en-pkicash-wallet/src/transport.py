"""
Reticulum (RNS) transport layer for PKI Cash.

Each actor (engine, bank, wallet) gets its own RNS Identity and Destination.
Identity keys (RNS) are separate from transaction keys (PyNaCl).
Communication between actors goes via RNS Links and Packets.
"""

import json
import os
import time
import zlib
import threading
from datetime import datetime

import RNS

APP_NAME = "pkicash"


class PKICashTransport:
    """
    Transport wrapper for a single PKI Cash actor.

    Manages: RNS identity, destination, announces, send/receive, inbox.
    Thread-safe — RNS callbacks run on background threads, Flask runs on main.
    """

    def __init__(self, role: str, data_dir: str, config_path: str = None):
        """
        Args:
            role: one of 'engine', 'bank', 'wallet'
            data_dir: actor-specific directory (e.g. data/engine/)
            config_path: optional Reticulum config directory
        """
        self.role = role
        self.data_dir = data_dir

        self._inbox: list[dict] = []
        self._inbox_lock = threading.Lock()
        self._message_log: list[dict] = []
        self._log_lock = threading.Lock()
        self._announces: dict[str, dict] = {}
        self._announces_lock = threading.Lock()
        self._message_handlers: list = []
        self._announce_handlers: list = []

        os.makedirs(data_dir, exist_ok=True)

        self.reticulum = RNS.Reticulum(config_path)

        identity_path = os.path.join(data_dir, "identity")
        if os.path.exists(identity_path):
            self.identity = RNS.Identity.from_file(identity_path)
            RNS.log(f"PKICash {role}: loaded identity", RNS.LOG_INFO)
        else:
            self.identity = RNS.Identity()
            self.identity.to_file(identity_path)
            RNS.log(f"PKICash {role}: created new identity", RNS.LOG_INFO)

        self.destination = RNS.Destination(
            self.identity,
            RNS.Destination.IN,
            RNS.Destination.SINGLE,
            APP_NAME,
            role,
        )
        self.destination.set_proof_strategy(RNS.Destination.PROVE_ALL)
        self.destination.set_link_established_callback(self._on_inbound_link)

        _handler = _AnnounceHandler(self)
        RNS.Transport.register_announce_handler(_handler)

        self.dest_hash_hex: str = self.destination.hexhash

        self._load_announces()
        self._load_message_log()

        RNS.log(
            f"PKICash {role} ready — dest {self.dest_hash_hex}",
            RNS.LOG_INFO,
        )

    # ── public API ──────────────────────────────────────────

    def announce(self, name: str = "", pk_transaction: str = ""):
        """Broadcast this actor's presence on the Reticulum network."""
        app_data = json.dumps({
            "name": name,
            "role": self.role,
            "pk_transaction": pk_transaction,
        }).encode("utf-8")
        self.destination.announce(app_data=app_data)
        RNS.log(f"PKICash {self.role}: announced", RNS.LOG_INFO)

    def send(self, dest_hash_hex: str, target_role: str,
             msg_type: str, payload: dict):
        """
        Send a typed message to another PKICash actor.

        Establishes a temporary RNS Link, sends zlib-compressed JSON,
        then tears down the link.
        """
        if "|" in dest_hash_hex:
            dest_hash_hex = dest_hash_hex.split("|")[0]
        dest_hash = bytes.fromhex(dest_hash_hex)

        if not RNS.Transport.has_path(dest_hash):
            RNS.Transport.request_path(dest_hash)
            deadline = time.time() + 15
            while not RNS.Transport.has_path(dest_hash):
                time.sleep(0.1)
                if time.time() > deadline:
                    raise TimeoutError(
                        f"Geen pad naar {dest_hash_hex[:16]}…"
                    )

        remote_identity = RNS.Identity.recall(dest_hash)
        if remote_identity is None:
            raise ConnectionError(
                f"Identity onbekend voor {dest_hash_hex[:16]}…"
            )

        remote_dest = RNS.Destination(
            remote_identity,
            RNS.Destination.OUT,
            RNS.Destination.SINGLE,
            APP_NAME,
            target_role,
        )

        envelope = json.dumps({
            "type": msg_type,
            "from_hash": self.dest_hash_hex,
            "from_role": self.role,
            "payload": payload,
            "ts": datetime.now().isoformat(),
        })
        data = zlib.compress(envelope.encode("utf-8"))

        link = RNS.Link(remote_dest)
        done = threading.Event()
        result = {"ok": False, "error": None}

        def _established(lnk):
            try:
                RNS.Packet(lnk, data).send()
                result["ok"] = True
            except Exception as exc:
                result["error"] = str(exc)
            finally:
                done.set()
                threading.Timer(1.0, lnk.teardown).start()

        def _closed(lnk):
            if not done.is_set():
                result["error"] = "Link gesloten voordat bericht verzonden was"
                done.set()

        link.set_link_established_callback(_established)
        link.set_link_closed_callback(_closed)

        done.wait(timeout=15)
        if not result["ok"]:
            raise ConnectionError(result["error"] or "Timeout bij verzenden")

        self._append_to_log({
            "direction": "out",
            "type": msg_type,
            "to_hash": dest_hash_hex,
            "to_role": target_role,
            "payload": payload,
            "ts": datetime.now().isoformat(),
        })

    # ── inbox ───────────────────────────────────────────────

    def get_inbox(self) -> list[dict]:
        """Return and clear all queued inbox messages."""
        with self._inbox_lock:
            msgs = list(self._inbox)
            self._inbox.clear()
            return msgs

    def peek_inbox(self) -> list[dict]:
        """Return inbox messages without clearing."""
        with self._inbox_lock:
            return list(self._inbox)

    def inbox_count(self) -> int:
        with self._inbox_lock:
            return len(self._inbox)

    # ── message log (persistent history) ────────────────────

    def get_message_log(self) -> list[dict]:
        with self._log_lock:
            return list(self._message_log)

    def _append_to_log(self, msg: dict):
        with self._log_lock:
            self._message_log.append(msg)
            self._save_message_log()

    def _message_log_path(self):
        return os.path.join(self.data_dir, "message_log.json")

    def _save_message_log(self):
        try:
            with open(self._message_log_path(), "w") as f:
                json.dump(self._message_log, f, indent=2)
        except Exception:
            pass

    def _load_message_log(self):
        path = self._message_log_path()
        if os.path.exists(path):
            try:
                with open(path) as f:
                    self._message_log = json.load(f)
            except Exception:
                self._message_log = []

    # ── announces ───────────────────────────────────────────

    def get_announces(self) -> dict[str, dict]:
        """Return all discovered actors. Key = dest_hash hex."""
        with self._announces_lock:
            return dict(self._announces)

    # ── callbacks ───────────────────────────────────────────

    def on_message(self, callback):
        """Register callback(msg_dict) for incoming messages."""
        self._message_handlers.append(callback)

    def on_announce(self, callback):
        """Register callback(announce_info) for incoming announces."""
        self._announce_handlers.append(callback)

    # ── persistence ─────────────────────────────────────────

    def _announces_path(self):
        return os.path.join(self.data_dir, "announces.json")

    def _save_announces(self):
        try:
            with open(self._announces_path(), "w") as f:
                json.dump(self._announces, f, indent=2)
        except Exception:
            pass

    def _load_announces(self):
        path = self._announces_path()
        if os.path.exists(path):
            try:
                with open(path) as f:
                    self._announces = json.load(f)
            except Exception:
                self._announces = {}

    # ── internal RNS callbacks ──────────────────────────────

    def _on_inbound_link(self, link):
        """Called when another actor opens a Link to us."""
        link.set_packet_callback(self._on_packet)

    def _on_packet(self, raw_data, packet):
        """Called when a packet arrives over an inbound Link."""
        try:
            decompressed = zlib.decompress(raw_data)
            msg = json.loads(decompressed.decode("utf-8"))
        except (zlib.error, json.JSONDecodeError):
            try:
                msg = json.loads(raw_data.decode("utf-8"))
            except Exception:
                return

        with self._inbox_lock:
            self._inbox.append(msg)

        log_entry = {**msg, "direction": "in"}
        self._append_to_log(log_entry)

        for handler in self._message_handlers:
            try:
                handler(msg)
            except Exception:
                pass

    def _on_announce_received(self, dest_hash_bytes, identity, app_data):
        """Called by _AnnounceHandler when an announce arrives."""
        if dest_hash_bytes == self.destination.hash:
            return

        try:
            info = json.loads(app_data.decode("utf-8")) if app_data else {}
        except Exception:
            return

        if "role" not in info:
            return

        hex_hash = dest_hash_bytes.hex()
        info["dest_hash"] = hex_hash
        info["seen"] = datetime.now().isoformat()

        with self._announces_lock:
            self._announces[hex_hash] = info
            self._save_announces()

        for handler in self._announce_handlers:
            try:
                handler(info)
            except Exception:
                pass

        RNS.log(
            f"PKICash {self.role}: announce from {info.get('role','?')} "
            f"'{info.get('name','')}' [{hex_hash[:16]}…]",
            RNS.LOG_INFO,
        )


class _AnnounceHandler:
    """RNS announce handler — forwards all announces to PKICashTransport."""

    def __init__(self, transport: PKICashTransport):
        self.aspect_filter = None
        self._transport = transport

    def received_announce(self, destination_hash, announced_identity, app_data):
        self._transport._on_announce_received(
            destination_hash, announced_identity, app_data
        )
