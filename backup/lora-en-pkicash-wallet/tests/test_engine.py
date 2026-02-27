import pytest
from src.crypto_utils import generate_keypair, pk_to_hex, sign, build_payload
from src.issuer import Issuer
from src.engine import (
    StateEngine, InvalidSignatureError, DoubleSpendError,
    UnknownCoinError, UntrustedIssuerError,
)


@pytest.fixture
def setup():
    issuer = Issuer()
    engine = StateEngine()
    engine.register_issuer(issuer.pk_hex)

    sk_owner, pk_owner = generate_keypair()
    coin = issuer.issue_coin(
        waarde=10,
        pk_owner_hex=pk_to_hex(pk_owner),
        engine_endpoint="http://localhost:5000",
        pk_engine_hex=engine.pk_hex,
    )
    engine.register_coin(coin, "wallet_a")

    return {"issuer": issuer, "engine": engine, "coin": coin, "sk_owner": sk_owner}


def test_register_trusted_issuer():
    engine = StateEngine()
    issuer = Issuer()
    engine.register_issuer(issuer.pk_hex)
    assert engine.is_trusted_issuer(issuer.pk_hex)


def test_register_coin_untrusted_issuer():
    engine = StateEngine()
    issuer = Issuer()
    sk_owner, pk_owner = generate_keypair()

    coin = issuer.issue_coin(10, pk_to_hex(pk_owner), "http://localhost", "aa" * 32)

    with pytest.raises(UntrustedIssuerError):
        engine.register_coin(coin, "wallet_a")


def test_register_coin_invalid_signature():
    engine = StateEngine()
    issuer = Issuer()
    engine.register_issuer(issuer.pk_hex)

    sk_owner, pk_owner = generate_keypair()
    coin = issuer.issue_coin(10, pk_to_hex(pk_owner), "http://localhost", "aa" * 32)
    coin.issuer_signature = "00" * 64  # tampered

    with pytest.raises(InvalidSignatureError):
        engine.register_coin(coin, "wallet_a")


def test_valid_transaction(setup):
    engine = setup["engine"]
    coin = setup["coin"]
    sk_owner = setup["sk_owner"]

    sk_next, pk_next = generate_keypair()
    pk_next_hex = pk_to_hex(pk_next)

    payload = build_payload(coin.coin_id, pk_next_hex)
    sig = sign(sk_owner, payload)

    tx = {
        "coin_id": coin.coin_id,
        "pk_next": pk_next_hex,
        "recipient_address": "wallet_b",
        "signature": sig.hex(),
    }

    confirmation = engine.process_transaction(tx)
    assert confirmation["status"] == "confirmed"
    assert confirmation["pk_next"] == pk_next_hex

    state = engine.get_coin_state(coin.coin_id)
    assert state["pk_current"] == pk_next_hex


def test_double_spend(setup):
    engine = setup["engine"]
    coin = setup["coin"]
    sk_owner = setup["sk_owner"]

    sk_next, pk_next = generate_keypair()
    pk_next_hex = pk_to_hex(pk_next)
    payload = build_payload(coin.coin_id, pk_next_hex)
    sig = sign(sk_owner, payload)

    tx = {
        "coin_id": coin.coin_id,
        "pk_next": pk_next_hex,
        "recipient_address": "wallet_b",
        "signature": sig.hex(),
    }
    engine.process_transaction(tx)

    sk_next2, pk_next2 = generate_keypair()
    payload2 = build_payload(coin.coin_id, pk_to_hex(pk_next2))
    sig2 = sign(sk_owner, payload2)

    tx2 = {
        "coin_id": coin.coin_id,
        "pk_next": pk_to_hex(pk_next2),
        "recipient_address": "wallet_c",
        "signature": sig2.hex(),
    }

    with pytest.raises(InvalidSignatureError):
        engine.process_transaction(tx2)


def test_unknown_coin():
    engine = StateEngine()
    tx = {
        "coin_id": "nonexistent",
        "pk_next": "aa" * 32,
        "recipient_address": "wallet_b",
        "signature": "00" * 64,
    }
    with pytest.raises(UnknownCoinError):
        engine.process_transaction(tx)


def test_pending_deliveries(setup):
    engine = setup["engine"]
    coin = setup["coin"]
    sk_owner = setup["sk_owner"]

    sk_next, pk_next = generate_keypair()
    pk_next_hex = pk_to_hex(pk_next)
    payload = build_payload(coin.coin_id, pk_next_hex)
    sig = sign(sk_owner, payload)

    tx = {
        "coin_id": coin.coin_id,
        "pk_next": pk_next_hex,
        "recipient_address": "wallet_b",
        "signature": sig.hex(),
    }
    engine.process_transaction(tx)

    deliveries = engine.get_pending_deliveries("wallet_b")
    assert len(deliveries) == 1
    assert deliveries[0]["coin"]["coin_id"] == coin.coin_id

    # Second call returns empty (already delivered)
    assert len(engine.get_pending_deliveries("wallet_b")) == 0
