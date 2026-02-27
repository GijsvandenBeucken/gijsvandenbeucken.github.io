import pytest
from src.crypto_utils import generate_keypair, pk_to_hex
from src.issuer import Issuer


def test_keypair_generation():
    issuer = Issuer()
    assert len(issuer.pk_hex) == 64  # 32 bytes as hex


def test_issue_coin():
    issuer = Issuer()
    sk_owner, pk_owner = generate_keypair()
    pk_owner_hex = pk_to_hex(pk_owner)

    coin = issuer.issue_coin(
        waarde=10,
        pk_owner_hex=pk_owner_hex,
        engine_endpoint="http://localhost:5000",
        pk_engine_hex="aa" * 32,
    )

    assert coin.waarde == 10
    assert coin.pk_current == pk_owner_hex
    assert coin.pk_issuer == issuer.pk_hex
    assert coin.verify_issuer()


def test_verify_wrong_issuer_fails():
    issuer = Issuer()
    other_issuer = Issuer()
    sk_owner, pk_owner = generate_keypair()

    coin = issuer.issue_coin(
        waarde=5,
        pk_owner_hex=pk_to_hex(pk_owner),
        engine_endpoint="http://localhost:5000",
        pk_engine_hex="bb" * 32,
    )

    assert not coin.verify_issuer(other_issuer.pk_hex)


def test_save_and_load_key(tmp_path):
    issuer = Issuer()
    key_file = str(tmp_path / "issuer.key")
    issuer.save_key(key_file)

    loaded = Issuer.load_key(key_file)
    assert loaded.pk_hex == issuer.pk_hex


def test_coin_serialization():
    issuer = Issuer()
    sk_owner, pk_owner = generate_keypair()

    coin = issuer.issue_coin(
        waarde=25,
        pk_owner_hex=pk_to_hex(pk_owner),
        engine_endpoint="http://localhost:5000",
        pk_engine_hex="cc" * 32,
    )

    data = coin.to_dict()
    from src.coin import Coin
    restored = Coin.from_dict(data)

    assert restored.coin_id == coin.coin_id
    assert restored.waarde == coin.waarde
    assert restored.verify_issuer()
