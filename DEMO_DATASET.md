# Curated visual demo corpus

Set `DATA_SOURCE=curated_visual` in `.env`. The app then reads
`demo_ads.json` and serves local assets from `demo_assets/`.

## Add one record

Copy the object in `demo_ads.json`, use an exact advertiser name, and place
the matching image or video thumbnail in `demo_assets/`.

Required fields: `ad_id`, `advertiser`, `creative_type`, `body_text`, and
`first_seen`. Use `status: "active"` for an active ad; otherwise set a
`last_seen` date.

`image_path` is a filename relative to `demo_assets/`. It is only served if
it stays inside that directory. `image_url` is for a permissioned remote
asset. Preserve `snapshot_url` for the original public source record.

`visual_source` is documentation for your dataset and should be one of:

- `original_public_preview` — an approved source/API preview
- `illustrative_demo` — a generated or owned representative visual
- `text_only` — no visual asset available

Never present illustrative visuals as original competitor creatives.
