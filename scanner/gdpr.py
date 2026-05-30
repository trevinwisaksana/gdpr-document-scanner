"""The 13 GDPR personal-data categories, their UI metadata, and the GDPR articles
each one implicates. Single source of truth shared by detectors and the UI."""
from __future__ import annotations

# Category keys — the 13 required by the Bosch challenge.
NAME = "name"
USERNAME = "username"
EMAIL = "email"
SIGNATURE = "signature"
PHOTO_VIDEO = "photo_video"
PHONE = "phone"
FAX = "fax"
HOME_ADDRESS = "home_address"
BILLING_SHIPPING = "billing_shipping_address"
PASSPORT = "passport"
ID_CARD = "id_card"
DRIVERS_LICENSE = "drivers_license"
TRAVEL_HISTORY = "travel_history"

CATEGORIES = [
    NAME, USERNAME, EMAIL, SIGNATURE, PHOTO_VIDEO, PHONE, FAX,
    HOME_ADDRESS, BILLING_SHIPPING, PASSPORT, ID_CARD, DRIVERS_LICENSE, TRAVEL_HISTORY,
]

# label, icon for the UI
META: dict[str, dict] = {
    NAME:             {"label": "Name",                 "icon": "👤"},
    USERNAME:         {"label": "Username / login",     "icon": "🆔"},
    EMAIL:            {"label": "Email address",        "icon": "📧"},
    SIGNATURE:        {"label": "Signature",            "icon": "✍️"},
    PHOTO_VIDEO:      {"label": "Photo / video",        "icon": "📷"},
    PHONE:            {"label": "Phone number",         "icon": "📞"},
    FAX:              {"label": "Fax number",           "icon": "📠"},
    HOME_ADDRESS:     {"label": "Home address",         "icon": "🏠"},
    BILLING_SHIPPING: {"label": "Billing / shipping",   "icon": "📦"},
    PASSPORT:         {"label": "Passport number",      "icon": "🛂"},
    ID_CARD:          {"label": "ID card number",       "icon": "🪪"},
    DRIVERS_LICENSE:  {"label": "Driver's license",     "icon": "🚗"},
    TRAVEL_HISTORY:   {"label": "Travel history",       "icon": "✈️"},
}

# GDPR articles surfaced in the UI — gives each finding its "why".
ARTICLES: dict[str, str] = {
    "Art. 5":  "Principles — data minimisation & storage limitation",
    "Art. 17": "Right to erasure (right to be forgotten)",
    "Art. 25": "Data protection by design and by default",
    "Art. 32": "Security of processing",
}

# Every category implicates the storage-limitation principle (Art. 5) and the
# erasure right (Art. 17) once past retention. Identity/credential and special
# documents additionally implicate design-by-default (25) and security (32).
_HIGH_SENSITIVITY = {PASSPORT, ID_CARD, DRIVERS_LICENSE, SIGNATURE, PHOTO_VIDEO}

# Risk priority for UI triage
_PRIORITY_HIGH   = {PASSPORT, ID_CARD, DRIVERS_LICENSE, SIGNATURE, PHOTO_VIDEO}
_PRIORITY_MEDIUM = {HOME_ADDRESS, BILLING_SHIPPING, EMAIL, PHONE, FAX}
# NAME, USERNAME, TRAVEL_HISTORY → low

def priority(category: str) -> str:
    """Return 'high', 'medium', or 'low' risk priority for a category."""
    if category in _PRIORITY_HIGH:
        return "high"
    if category in _PRIORITY_MEDIUM:
        return "medium"
    return "low"


def articles_for(category: str) -> list[str]:
    arts = ["Art. 5", "Art. 17"]
    if category in _HIGH_SENSITIVITY:
        arts += ["Art. 25", "Art. 32"]
    elif category in (HOME_ADDRESS, BILLING_SHIPPING, EMAIL, PHONE):
        arts += ["Art. 25"]
    return arts


# one-line justification per category, shown on the finding card
WHY: dict[str, str] = {
    NAME:             "Direct identifier — names must be minimised and erased after retention.",
    USERNAME:         "Account/login identifier ties activity to a person.",
    EMAIL:            "Contact data — directly identifies and reaches an individual.",
    SIGNATURE:        "Biometric-adjacent identifier; high re-identification value.",
    PHOTO_VIDEO:      "Image of a person — sensitive identifier requiring protection by design.",
    PHONE:            "Contact data — directly reaches an individual.",
    FAX:              "Contact data tied to an individual or office.",
    HOME_ADDRESS:     "Location data — strong quasi-identifier.",
    BILLING_SHIPPING: "Location + transaction data linking a person to activity.",
    PASSPORT:         "Government identifier — high-risk, requires security of processing.",
    ID_CARD:          "Government identifier — high-risk, requires security of processing.",
    DRIVERS_LICENSE:  "Government identifier — high-risk, requires security of processing.",
    TRAVEL_HISTORY:   "Movement data — reveals patterns of life; storage must be limited.",
}


def label(category: str) -> str:
    return META.get(category, {}).get("label", category)


def icon(category: str) -> str:
    return META.get(category, {}).get("icon", "•")
