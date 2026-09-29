"""Country and region reference data.

Country codes are ISO 3166-1 alpha-2. Region codes are the subdivision part of
ISO 3166-2 (``NW`` for ``DE-NW``). Only countries relevant to the pilot carry a
closed region list; for the rest we check the format and nothing more.
"""

from __future__ import annotations

import re

ISO_3166_1_ALPHA2: frozenset[str] = frozenset(
    """
    AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL
    BM BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV
    CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD
    GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM
    IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK
    LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW
    MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR
    PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS
    ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY
    UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW
    """.split()
)

# Closed subdivision lists for pilot countries (ISO 3166-2 suffixes).
KNOWN_REGIONS: dict[str, frozenset[str]] = {
    "DE": frozenset(
        "BW BY BE BB HB HH HE MV NI NW RP SL SN ST SH TH".split()
    ),
    "AT": frozenset("1 2 3 4 5 6 7 8 9".split()),
}

_REGION_FORMAT = re.compile(r"^[A-Z0-9]{1,3}$")


def is_valid_country_code(value: object) -> bool:
    """Strict check. No case folding, no alpha-3, no defaults."""
    return isinstance(value, str) and value in ISO_3166_1_ALPHA2


def region_problem(country_code: str, region_code: str | None) -> str | None:
    """Return a reason string if the region code is not acceptable, else None.

    ``None`` is allowed: a missing region is recorded as missing, never guessed.
    """
    if region_code is None:
        return None
    if not isinstance(region_code, str) or not _REGION_FORMAT.match(region_code):
        return f"region_code {region_code!r} is not an ISO 3166-2 subdivision code"
    known = KNOWN_REGIONS.get(country_code)
    if known is not None and region_code not in known:
        return f"region_code {region_code!r} is not a subdivision of {country_code}"
    return None
