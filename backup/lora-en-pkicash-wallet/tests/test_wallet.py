import pytest
from src.crypto_utils import generate_keypair, pk_to_hex, sk_to_hex
from src.issuer import Issuer
from src.wallet import Wallet


@pytest.fixture
def wallet_a(tmp_path):
    return Wallet(str(tmp_path / "wallet_a.json"), address="wallet_a")


@pytest.fixture
def issuer():
    return Issuer()


def test_generate_receive_keypair(wallet_a):
    pk_hex = wallet_a.generate_receive_keypair()
    assert len(pk_hex) == 64


def test_add_coin_from_issuer(wallet_a, issuer):
    pk_hex = wallet_a.generate_receive_keypair()

    coin = issuer.issue_coin(
        waarde=10,
        pk_owner_hex=pk_hex,
        engine_endpoint="http://localhost:5000",
        pk_engine_hex="aa" * 32,
    )

    wallet_a.add_coin(coin)
    coins = wallet_a.list_coins()
    assert len(coins) == 1
    assert coins[0]["waarde"] == 10


def test_add_coin_no_matching_keypair(wallet_a, issuer):
    sk, pk = generate_keypair()
    coin = issuer.issue_coin(10, pk_to_hex(pk), "http://localhost", "aa" * 32)

    with pytest.raises(ValueError, match="Geen pending keypair"):
        wallet_a.add_coin(coin)


def test_create_transaction(wallet_a, issuer):
    pk_hex = wallet_a.generate_receive_keypair()
    coin = issuer.issue_coin(10, pk_hex, "http://localhost", "aa" * 32)
    wallet_a.add_coin(coin)

    sk_next, pk_next = generate_keypair()
    tx = wallet_a.create_transaction(coin.coin_id, pk_to_hex(pk_next), "wallet_b")

    assert tx["coin_id"] == coin.coin_id
    assert tx["pk_next"] == pk_to_hex(pk_next)
    assert tx["recipient_address"] == "wallet_b"
    assert len(tx["signature"]) == 128  # 64 bytes as hex


def test_confirm_send_removes_coin(wallet_a, issuer):
    pk_hex = wallet_a.generate_receive_keypair()
    coin = issuer.issue_coin(10, pk_hex, "http://localhost", "aa" * 32)
    wallet_a.add_coin(coin)

    assert wallet_a.get_balance() == 10
    wallet_a.confirm_send(coin.coin_id)
    assert wallet_a.get_balance() == 0


def test_balance(wallet_a, issuer):
    for waarde in [5, 10, 25]:
        pk_hex = wallet_a.generate_receive_keypair()
        coin = issuer.issue_coin(waarde, pk_hex, "http://localhost", "aa" * 32)
        wallet_a.add_coin(coin)

    assert wallet_a.get_balance() == 40
    assert len(wallet_a.list_coins()) == 3


def test_validate_coin(wallet_a, issuer):
    pk_hex = wallet_a.generate_receive_keypair()
    coin = issuer.issue_coin(10, pk_hex, "http://localhost", "aa" * 32)

    assert wallet_a.validate_coin(coin, [issuer.pk_hex])
    assert not wallet_a.validate_coin(coin, ["ff" * 32])
