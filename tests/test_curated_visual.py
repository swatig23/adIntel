import json
from types import SimpleNamespace

from adintel.clients import curated_visual


async def test_curated_visual_loads_only_requested_advertiser_and_serves_safe_asset(tmp_path, monkeypatch):
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "creative.png").write_bytes(b"not-a-real-png")
    corpus = tmp_path / "ads.json"
    corpus.write_text(json.dumps({"ads": [
        {
            "ad_id": "a1", "advertiser": "Acme", "platform": "instagram",
            "creative_type": "image", "body_text": "Shop now", "cta": "Shop Now",
            "first_seen": "2026-08-01", "status": "active", "image_path": "creative.png",
        },
        {
            "ad_id": "a2", "advertiser": "Other", "creative_type": "text",
            "body_text": "Other ad", "first_seen": "2026-08-01", "status": "active",
        },
    ]}), encoding="utf-8")
    monkeypatch.setattr(
        curated_visual,
        "get_settings",
        lambda: SimpleNamespace(curated_visual_file=str(corpus), curated_visual_asset_dir=str(assets)),
    )

    ads = await curated_visual.fetch_curated_visual_ads("acme")

    assert len(ads) == 1
    assert ads[0].id == "a1"
    assert ads[0].image_url == "/demo-assets/creative.png"


def test_curated_visual_rejects_path_outside_asset_directory(tmp_path, monkeypatch):
    assets = tmp_path / "assets"
    assets.mkdir()
    monkeypatch.setattr(
        curated_visual,
        "get_settings",
        lambda: SimpleNamespace(curated_visual_asset_dir=str(assets)),
    )

    assert curated_visual._safe_local_image_url("../secret.png") is None
