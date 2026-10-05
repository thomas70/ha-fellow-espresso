# Fellow Espresso Series 1 for Home Assistant

Unofficial integration for the Fellow Espresso Series 1 (ES1), using
Fellow's cloud API. It polls every 60 seconds and runs alongside the Fellow
Aiden integration without conflict (separate domain: `fellow_espresso`).

> Not affiliated with or endorsed by Fellow. Built with
> [Claude](https://claude.ai) by someone who doesn't code, so issues and pull
> requests are very welcome.

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
| Descale interval | `descaleRem` | Configured interval, e.g. every 200 drinks (diagnostic) |
| Backflush interval | `backflushRem` | Configured interval, e.g. every 60 shots (diagnostic) |
| Shower screen clean interval | `showerRem` | Configured interval (diagnostic) |
| **Profile** (select) | `PATCH /active-profile` | Switch the active profile: Fellow's built-in profiles (Light/Medium/Dark roast, Classic 9 bar, Lever, Modern arc, Turbo shot) and your Drops profiles |
| Active profile | `activeProfileId` | Profile name. Attributes: dose, ratio, temperature, grind, pre-infusion, infusion steps, ramp-down, transition, declining temp, and `notes` (the profile's description of the shot) |
| Profiles | `/profiles` | Number of profiles; full list as an attribute |
| Connected | `isConnected` | Whether the machine is online in Fellow's cloud |
| Firmware upgrade required | `firmwareUpgradeRequired` | |
| Total descales / backflushes / shower cleans | `total*Count` | Completed maintenance runs; confirmed to update after a backflush (diagnostic) |
| Water hardness, Firmware, Auto stop, Preheat | settings | Diagnostic |
| Group rinse, Chime, Brew guidance | `groupRinse`, `chime`, `brewGuidance` | Diagnostic, values as reported by the machine |

### Showing the shot description

`notes` is often longer than the 255 characters a sensor state can hold, so it
is an attribute on **Active profile**. A Markdown card shows it and follows
profile changes:

```yaml
type: markdown
content: >
  ### {{ states('sensor.espresso_series_1_active_profile') }}
  {{ state_attr('sensor.espresso_series_1_active_profile', 'notes') }}
```

## Icon

The integration ships its own icon in `custom_components/fellow_espresso/brand/`
(light and dark variants). Home Assistant 2026.3 or newer shows it automatically.

## API endpoints used

All against `https://l8qtmnc692.execute-api.us-west-2.amazonaws.com/v2`:

- `POST /auth/login` (returns HTTP 201) and `POST /auth/refresh-token`
- `GET /devices?dataType=real`, filtered on `deviceType == "Solo"`
- `GET /solo/devices/{id}`
- `GET /solo/devices/{id}/profiles`
- `PATCH /solo/devices/{id}/active-profile` with `{"profileId": "...", "settingsVersion": <current Unix time in seconds>}` (returns 204)

## Not yet supported

The machine reports `schedules` and `remoteBrewing` in `enabledFlags`, but those
endpoints are not mapped yet. Preheat and schedules may go over AWS IoT (MQTT)
rather than this HTTP API. Capturing the Fellow app's traffic (e.g. with mimic
or mitmproxy) while using those features would show which.

Despite their names, `descaleRem`, `backflushRem` and `showerRem` are the
*intervals* set on the machine (Maintenance → Cleaning interval), not countdowns.
The machine's progress toward them (e.g. "33/200 drinks") is not sent to the
cloud, and neither are individual shots, so maintenance-due alerts are not
possible from this integration alone. A power-monitoring smart plug could be
used to count shots in Home Assistant instead.

The API has a `missingWater` field, but it stays `null` even with an empty tank,
so there is no water tank sensor.

The profiles endpoint may also return Fellow's built-in profiles; their API
titles are used when present. `profiles.py` holds fallback names for built-in
ids seen so far, and any other id the machine reports as active is added to the
selector automatically.

## Tests

`tests/` contains Home Assistant tests with the API mocked:
`pip install pytest-homeassistant-custom-component && pytest`
