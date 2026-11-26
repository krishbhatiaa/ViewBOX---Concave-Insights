from pathlib import Path

SEED = Path(__file__).resolve().parents[1] / "app" / "seed.py"


def test_seed_includes_demo_fraud_ring_and_shared_device_pair_without_preflagging():
    source = SEED.read_text(encoding="utf-8")
    for index in (10, 11, 12, 13, 14):
        assert f"mem({index}," in source
    assert "ring[1:] + ring[:1]" in source
    assert "demo-shared-device" in source
    assert "is_flagged=False" in source
    assert "FraudFlag" not in source
