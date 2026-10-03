# Fellow Espresso Series 1 for Home Assistant

Unofficial, read-only integration for the Fellow Espresso Series 1 (ES1), using
Fellow's cloud API. It polls every 60 seconds and runs alongside the Fellow
Aiden integration without conflict (separate domain: `fellow_espresso`).

## Install

### HACS

1. HACS → ⋮ (top right) → **Custom repositories**.
2. Repository: `https://github.com/thomas70/ha-fellow-espresso`, type: **Integration**.
3. Search for **Fellow Espresso Series 1**, download it and restart Home Assistant.
4. Settings → Devices & services → Add integration → **Fellow Espresso Series 1**,
   and log in with your Fellow account.

### Manual

Copy `custom_components/fellow_espresso` to `/config/custom_components/`,
restart Home Assistant and add the integration as in step 4.

## Entities

| Entity | Source field | Notes |
| --- | --- | --- |
| Descale remaining | `descaleRem` | Countdown to next descale |
| Backflush remaining | `backflushRem` | Countdown to next backflush |
| Shower screen clean remaining | `showerRem` | Countdown to next shower screen clean |
| Active profile | `activeProfileId` | Profile title, with dose/ratio/temp/grind as attributes. Built-in profiles show their id |
| Profiles | `/profiles` | Number of profiles; full list as an attribute |
| Connected | `isConnected` | Whether the machine is online in Fellow's cloud |
| Water tank empty | `missingWater` | Was `null` while idle; may populate when the tank is empty |
| Firmware upgrade required | `firmwareUpgradeRequired` | |
| Total descales / backflushes / shower cleans | `total*Count` | Diagnostic |
| Water hardness, Firmware, Auto stop, Preheat | settings | Diagnostic |

## API endpoints used

All against `https://l8qtmnc692.execute-api.us-west-2.amazonaws.com/v2`:

- `POST /auth/login` (returns HTTP 201) and `POST /auth/refresh-token`
- `GET /devices?dataType=real`, filtered on `deviceType == "Solo"`
- `GET /solo/devices/{id}`
- `GET /solo/devices/{id}/profiles`

## Not yet supported

The machine reports `schedules` and `remoteBrewing` in `enabledFlags`, but those
endpoints, plus changing the active profile, are not mapped yet. Capturing the
Fellow app's traffic (e.g. with mimic or mitmproxy) while using those features
would reveal them.

## Tests

`tests/` contains Home Assistant tests with the API mocked:
`pip install pytest-homeassistant-custom-component && pytest`
