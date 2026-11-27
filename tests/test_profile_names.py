"""Custom profile ids must not be turned into made-up names."""
from custom_components.fellow_espresso.profiles import builtin_name, profile_options

CUSTOM_ID = "AbC12XyZ34qrStu"
LISTED = [{"id": "4_classic9bar", "title": "Classic 9 bar"}]


async def test_custom_id_is_not_renamed(hass):
    assert builtin_name(CUSTOM_ID) == CUSTOM_ID
    assert builtin_name("1_lightroast") == "Lightroast"
    assert builtin_name("4_classic9bar") == "Classic 9-Bar"


async def test_unlisted_custom_id_is_not_offered(hass):
    """Also covers a deleted profile that was active earlier."""
    options = profile_options(LISTED, {CUSTOM_ID, "1_lightroast"})
    assert CUSTOM_ID not in options.values()
    assert "1_lightroast" in options.values()
