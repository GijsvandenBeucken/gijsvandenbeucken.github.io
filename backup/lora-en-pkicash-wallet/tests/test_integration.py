"""End-to-end integration test: issuer -> engine -> wallet A -> wallet B -> double spend fail -> chain test."""

import pytest
from src.issuer import Issuer
from src.engine import StateEngine, InvalidSignatureError
from src.wallet import Wallet
from src.crypto_utils import generate_keypair, pk_to_hex


@pytest.fixture
def system(tmp_path):
    issuer = Issuer()
    engine = StateEngine()
    wallet_a = Wallet(str(tmp_path / "wallet_a.json"), address="wallet_a")
    wallet_b = Wallet(str(tmp_path / "wallet_b.json"), address="wallet_b")
    wallet_c = Wallet(str(tmp_path / "wallet_c.json"), address="wallet_c")

    engine.register_issuer(issuer.pk_hex)

    return {
        "issuer": issuer,
        "engine": engine,
        "wallet_a": wallet_a,
        "wallet_b": wallet_b,
        "wallet_c": wallet_c,
    }


def test_full_flow(system):
    issuer = system["issuer"]
    engine = system["engine"]
    wallet_a = system["wallet_a"]
    wallet_b = system["wallet_b"]
    wallet_c = system["wallet_c"]

    # --- Coin uitgifte: issuer -> engine -> wallet A (push delivery) ---
    pk_a = wallet_a.generate_receive_keypair()
    coin = issuer.issue_coin(
        waarde=10,
        pk_owner_hex=pk_a,
        engine_endpoint="http://localhost:5000",
        pk_engine_hex=engine.pk_hex,
    )
    engine.register_coin(coin, wallet_a.address)

    # Wallet A receives via engine delivery (push)
    deliveries = engine.get_pending_deliveries(wallet_a.address)
    assert len(deliveries) == 1
    wallet_a.receive_from_engine(deliveries[0])

    assert wallet_a.get_balance() == 10
    assert len(engine.list_coins()) == 1

    # --- Betaling: wallet A -> wallet B ---
    pk_b = wallet_b.generate_receive_keypair()

    tx = wallet_a.create_transaction(coin.coin_id, pk_b, wallet_b.address)
    confirmation = engine.process_transaction(tx)

    assert confirmation["status"] == "confirmed"

    wallet_a.confirm_send(coin.coin_id)
    assert wallet_a.get_balance() == 0

    # Wallet B receives via engine delivery (push)
    deliveries = engine.get_pending_deliveries(wallet_b.address)
    assert len(deliveries) == 1
    wallet_b.receive_from_engine(deliveries[0])

    assert wallet_b.get_balance() == 10

    # --- Double spend poging: wallet A probeert opnieuw ---
    try:
        tx_double = wallet_a.create_transaction(coin.coin_id, pk_to_hex(generate_keypair()[1]), "wallet_x")
        pytest.fail("Wallet A should not have the coin anymore")
    except ValueError:
        pass

    # --- Keten-test: wallet B -> wallet C ---
    pk_c = wallet_c.generate_receive_keypair()

    tx2 = wallet_b.create_transaction(coin.coin_id, pk_c, wallet_c.address)
    confirmation2 = engine.process_transaction(tx2)

    assert confirmation2["status"] == "confirmed"

    wallet_b.confirm_send(coin.coin_id)
    assert wallet_b.get_balance() == 0

    deliveries2 = engine.get_pending_deliveries(wallet_c.address)
    assert len(deliveries2) == 1
    wallet_c.receive_from_engine(deliveries2[0])

    assert wallet_c.get_balance() == 10


def test_multiple_coins(system):
    issuer = system["issuer"]
    engine = system["engine"]
    wallet_a = system["wallet_a"]
    wallet_b = system["wallet_b"]

    coins = []
    for waarde in [5, 10, 25]:
        pk_a = wallet_a.generate_receive_keypair()
        coin = issuer.issue_coin(waarde, pk_a, "http://localhost:5000", engine.pk_hex)
        engine.register_coin(coin, wallet_a.address)
        coins.append(coin)

    # Wallet A receives all 3 via engine delivery
    deliveries = engine.get_pending_deliveries(wallet_a.address)
    assert len(deliveries) == 3
    for d in deliveries:
        wallet_a.receive_from_engine(d)

    assert wallet_a.get_balance() == 40

    # Transfer the 10-coin to wallet B
    pk_b = wallet_b.generate_receive_keypair()
    tx = wallet_a.create_transaction(coins[1].coin_id, pk_b, wallet_b.address)
    engine.process_transaction(tx)
    wallet_a.confirm_send(coins[1].coin_id)

    deliveries = engine.get_pending_deliveries(wallet_b.address)
    wallet_b.receive_from_engine(deliveries[0])

    assert wallet_a.get_balance() == 30
    assert wallet_b.get_balance() == 10
