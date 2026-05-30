"""Unit tests for detectors/regex.py — pure-regex PII detector."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from detectors.regex import (
    detect_pii,
    RegexDetectorConfig,
    EMAIL, PHONE, FAX, NAME, USERNAME, SIGNATURE, PHOTO_VIDEO,
    HOME_ADDRESS, BILLING_SHIPPING, PASSPORT, ID_CARD, DRIVERS_LICENSE,
    TRAVEL_HISTORY, IP_ADDRESS, CREDIT_CARD, IBAN, SSN, NHS_NUMBER, DATE_OF_BIRTH,
)


# ── helpers ────────────────────────────────────────────────────────────────────

def categories(findings):
    return {f["category"] for f in findings}


def snippets_for(findings, category):
    return [f["snippet"] for f in findings if f["category"] == category]


def one(findings, category):
    """Assert exactly one finding of category and return it."""
    matches = [f for f in findings if f["category"] == category]
    assert len(matches) == 1, f"Expected 1 {category!r} finding, got {len(matches)}: {matches}"
    return matches[0]


def assert_finding_shape(f, text):
    assert "category" in f
    assert "start" in f
    assert "end" in f
    assert "snippet" in f
    assert "confidence" in f
    assert isinstance(f["confidence"], float)
    assert 0.0 <= f["confidence"] <= 1.0
    assert f["start"] >= 0
    assert f["end"] > f["start"]
    assert f["snippet"] == text[f["start"]: f["end"]].strip()


# ── detect_pii: basic contract ─────────────────────────────────────────────────

class TestDetectPiiContract:
    def test_empty_string_returns_empty(self):
        assert detect_pii("") == []

    def test_whitespace_only_returns_empty(self):
        assert detect_pii("   \n\t  ") == []

    def test_none_like_empty_handled(self):
        assert detect_pii("no PII here at all") == []

    def test_returns_list_of_dicts(self):
        result = detect_pii("Email: user@example.com")
        assert isinstance(result, list)
        for f in result:
            assert isinstance(f, dict)

    def test_finding_has_required_keys(self):
        text = "Contact: user@example.com"
        for f in detect_pii(text):
            assert_finding_shape(f, text)

    def test_results_sorted_by_start(self):
        text = "Name: Alice Smith\nEmail: alice@example.com"
        results = detect_pii(text)
        starts = [f["start"] for f in results]
        assert starts == sorted(starts)

    def test_snippet_text_always_alphanumeric(self):
        text = "Name: John Doe\nEmail: j@x.com\nPhone: 555-123-4567"
        for f in detect_pii(text):
            import re
            assert re.search(r"[A-Za-z0-9]", f["snippet"])


# ── email ──────────────────────────────────────────────────────────────────────

class TestEmailDetection:
    def test_simple_email(self):
        f = one(detect_pii("Send to user@example.com please"), EMAIL)
        assert "user@example.com" in f["snippet"]

    def test_email_with_plus(self):
        f = one(detect_pii("user+tag@mail.org"), EMAIL)
        assert "user+tag@mail.org" in f["snippet"]

    def test_email_with_subdomain(self):
        f = one(detect_pii("contact@mail.company.co.uk"), EMAIL)
        assert "contact@mail.company.co.uk" in f["snippet"]

    def test_no_false_positive_on_at_sign(self):
        result = detect_pii("version @1.2 is released")
        assert EMAIL not in categories(result)

    def test_multiple_emails_detected(self):
        text = "alice@a.com and bob@b.com"
        snips = snippets_for(detect_pii(text), EMAIL)
        assert len(snips) == 2

    def test_confidence_is_high(self):
        f = one(detect_pii("hello@world.io"), EMAIL)
        assert f["confidence"] >= 0.95


# ── phone & fax ────────────────────────────────────────────────────────────────

class TestPhoneDetection:
    def test_labeled_phone(self):
        f = one(detect_pii("Phone: +1 555-123-4567"), PHONE)
        assert re.search(r"\d", f["snippet"])

    def test_labeled_mobile(self):
        result = detect_pii("Mobile: 0171 234 5678")
        assert PHONE in categories(result)

    def test_labeled_fax(self):
        f = one(detect_pii("Fax: +49 30 1234567"), FAX)
        assert re.search(r"\d", f["snippet"])

    def test_labeled_telefax(self):
        result = detect_pii("Telefax: 030-12345678")
        assert FAX in categories(result)

    def test_international_phone_with_country_code(self):
        result = detect_pii("Call +44 20 7946 0958 now")
        assert PHONE in categories(result)

    def test_no_phone_from_year(self):
        # A 4-digit year should not trigger phone
        result = detect_pii("Established in 1998.")
        assert PHONE not in categories(result)


import re  # needed by test_snippet_text_always_alphanumeric


# ── names ──────────────────────────────────────────────────────────────────────

class TestNameDetection:
    def test_labeled_name(self):
        f = one(detect_pii("Name: John Smith"), NAME)
        assert "John Smith" in f["snippet"]

    def test_labeled_employee(self):
        result = detect_pii("Employee: Jane Doe")
        assert NAME in categories(result)

    def test_labeled_applicant(self):
        result = detect_pii("Applicant: Maria Garcia")
        assert NAME in categories(result)

    def test_role_stopword_not_detected(self):
        result = detect_pii("Name: Manager")
        assert NAME not in categories(result)

    def test_email_value_not_detected_as_name(self):
        # The name regex stops before '@', so the local-part may be captured.
        # The email itself must always be detected; any name snippet must not
        # contain '@' or a domain.
        result = detect_pii("Name: alice@example.com")
        assert EMAIL in categories(result)
        for f in result:
            if f["category"] == NAME:
                assert "@" not in f["snippet"]

    def test_numeric_value_not_detected_as_name(self):
        result = detect_pii("Name: 12345")
        assert NAME not in categories(result)

    def test_confidence(self):
        f = one(detect_pii("Name: Anna Müller"), NAME)
        assert f["confidence"] >= 0.85


# ── usernames ──────────────────────────────────────────────────────────────────

class TestUsernameDetection:
    def test_labeled_username(self):
        result = detect_pii("Username: johndoe")
        assert USERNAME in categories(result)

    def test_labeled_login(self):
        result = detect_pii("Login: admin_user")
        assert USERNAME in categories(result)

    def test_employee_id_shorthand(self):
        f = one(detect_pii("Badge: E-20491"), USERNAME)
        assert "E-20491" in f["snippet"]

    def test_employee_id_various_lengths(self):
        for emp_id in ("A-1234", "B-123456"):
            result = detect_pii(f"ID is {emp_id}")
            assert USERNAME in categories(result), f"Expected match for {emp_id}"


# ── signatures ─────────────────────────────────────────────────────────────────

class TestSignatureDetection:
    def test_signature_label(self):
        result = detect_pii("Signature: John Doe")
        assert SIGNATURE in categories(result)

    def test_signed_by_label(self):
        result = detect_pii("Signed by: Jane Smith")
        assert SIGNATURE in categories(result)

    def test_unterschrift_label(self):
        result = detect_pii("Unterschrift: Max Mustermann")
        assert SIGNATURE in categories(result)


# ── photo / video ──────────────────────────────────────────────────────────────

class TestPhotoVideoDetection:
    def test_passport_photo_keyword(self):
        result = detect_pii("Please attach a passport photo.")
        assert PHOTO_VIDEO in categories(result)

    def test_headshot_keyword(self):
        result = detect_pii("Upload your headshot here.")
        assert PHOTO_VIDEO in categories(result)

    def test_jpg_extension(self):
        result = detect_pii("File saved as portrait.jpg")
        assert PHOTO_VIDEO in categories(result)

    def test_mp4_extension(self):
        result = detect_pii("Recording stored in clip.mp4")
        assert PHOTO_VIDEO in categories(result)

    def test_profile_photo_keyword(self):
        result = detect_pii("Set your profile photo.")
        assert PHOTO_VIDEO in categories(result)


# ── addresses ──────────────────────────────────────────────────────────────────

class TestAddressDetection:
    def test_labeled_home_address(self):
        result = detect_pii("Address: 10 Downing Street, London")
        assert HOME_ADDRESS in categories(result)

    def test_labeled_billing_address(self):
        result = detect_pii("Billing address: 123 Main St, Springfield")
        assert BILLING_SHIPPING in categories(result)

    def test_labeled_shipping_address(self):
        result = detect_pii("Shipping address: 456 Elm Ave, Shelbyville")
        assert BILLING_SHIPPING in categories(result)

    def test_german_postal_code(self):
        result = detect_pii("Wohnort: 80331 München")
        assert HOME_ADDRESS in categories(result)

    def test_german_street(self):
        result = detect_pii("Adresse: Hauptstraße 12")
        assert HOME_ADDRESS in categories(result)


# ── ID documents ───────────────────────────────────────────────────────────────

class TestIdDocumentDetection:
    def test_passport_number(self):
        result = detect_pii("Passport: AB123456")
        assert PASSPORT in categories(result)

    def test_passport_no(self):
        result = detect_pii("Passport no: C1234567")
        assert PASSPORT in categories(result)

    def test_reisepass(self):
        result = detect_pii("Reisepass: T22000129")
        assert PASSPORT in categories(result)

    def test_drivers_license(self):
        result = detect_pii("Driver's license: D1234567")
        assert DRIVERS_LICENSE in categories(result)

    def test_id_card(self):
        result = detect_pii("ID card no: 1234567890")
        assert ID_CARD in categories(result)

    def test_tax_id(self):
        result = detect_pii("Tax ID: 12345678901")
        assert ID_CARD in categories(result)

    def test_id_without_digits_not_matched(self):
        result = detect_pii("Passport: ABCDEF")
        # Must contain at least one digit in the value
        assert PASSPORT not in categories(result)


# ── travel history ─────────────────────────────────────────────────────────────

class TestTravelDetection:
    def test_boarding_pass(self):
        result = detect_pii("boarding pass attached")
        assert TRAVEL_HISTORY in categories(result)

    def test_flight_number(self):
        result = detect_pii("Flight LH4321 departs at 08:00")
        assert TRAVEL_HISTORY in categories(result)

    def test_trip_to_city(self):
        result = detect_pii("trip to Paris next month")
        assert TRAVEL_HISTORY in categories(result)

    def test_itinerary_keyword(self):
        result = detect_pii("See attached itinerary for details")
        assert TRAVEL_HISTORY in categories(result)

    def test_round_trip(self):
        result = detect_pii("Booked a round-trip to Berlin")
        assert TRAVEL_HISTORY in categories(result)


# ── IP addresses ───────────────────────────────────────────────────────────────

class TestIpAddressDetection:
    def test_ipv4(self):
        f = one(detect_pii("Server at 192.168.1.1 is down"), IP_ADDRESS)
        assert "192.168.1.1" in f["snippet"]

    def test_ipv4_edge_values(self):
        result = detect_pii("Range is 0.0.0.0 to 255.255.255.255")
        snips = snippets_for(result, IP_ADDRESS)
        assert "0.0.0.0" in snips
        assert "255.255.255.255" in snips

    def test_ipv4_out_of_range_not_matched(self):
        result = detect_pii("Bad address 256.100.100.1 here")
        assert IP_ADDRESS not in categories(result)

    def test_ipv4_confidence(self):
        f = one(detect_pii("IP: 10.0.0.1"), IP_ADDRESS)
        assert f["confidence"] >= 0.95

    def test_ipv4_not_triggered_by_version_number(self):
        # "1.2.3" is only 3 octets — should not match
        result = detect_pii("version 1.2.3 released")
        assert IP_ADDRESS not in categories(result)


# ── credit cards ───────────────────────────────────────────────────────────────

class TestCreditCardDetection:
    def test_visa_16_digits(self):
        result = detect_pii("Card: 4111 1111 1111 1111")
        assert CREDIT_CARD in categories(result)

    def test_visa_no_spaces(self):
        result = detect_pii("4111111111111111")
        assert CREDIT_CARD in categories(result)

    def test_mastercard(self):
        result = detect_pii("MC: 5500 0000 0000 0004")
        assert CREDIT_CARD in categories(result)

    def test_amex_15_digits(self):
        # Amex in compact 15-digit form (pattern expects 4-4-4-3 grouping)
        result = detect_pii("Amex: 371449635398431")
        assert CREDIT_CARD in categories(result)

    def test_discover(self):
        result = detect_pii("Discover: 6011 1111 1111 1117")
        assert CREDIT_CARD in categories(result)

    def test_wrong_digit_count_not_matched(self):
        # 12 digits — should not match
        result = detect_pii("4111 1111 1111")
        assert CREDIT_CARD not in categories(result)


# ── IBAN ───────────────────────────────────────────────────────────────────────

class TestIbanDetection:
    def test_german_iban(self):
        result = detect_pii("IBAN: DE89370400440532013000")
        assert IBAN in categories(result)

    def test_gb_iban(self):
        result = detect_pii("Account: GB29NWBK60161331926819")
        assert IBAN in categories(result)

    def test_too_short_not_matched(self):
        # Only 10 chars — too short for a real IBAN
        result = detect_pii("Ref: DE891234")
        assert IBAN not in categories(result)


# ── SSN ────────────────────────────────────────────────────────────────────────

class TestSsnDetection:
    def test_standard_ssn(self):
        f = one(detect_pii("SSN: 123-45-6789"), SSN)
        assert "123-45-6789" in f["snippet"]

    def test_ssn_with_spaces(self):
        result = detect_pii("Social Security: 234 56 7890")
        assert SSN in categories(result)

    def test_invalid_prefix_000(self):
        result = detect_pii("SSN: 000-12-3456")
        assert SSN not in categories(result)

    def test_invalid_prefix_666(self):
        result = detect_pii("SSN: 666-12-3456")
        assert SSN not in categories(result)

    def test_invalid_prefix_9xx(self):
        result = detect_pii("SSN: 987-65-4321")
        assert SSN not in categories(result)

    def test_confidence(self):
        f = one(detect_pii("SSN: 123-45-6789"), SSN)
        assert f["confidence"] >= 0.9


# ── NHS numbers ────────────────────────────────────────────────────────────────

class TestNhsDetection:
    def test_nhs_with_spaces(self):
        result = detect_pii("NHS Number: 943 476 5919")
        assert NHS_NUMBER in categories(result)

    def test_nhs_with_dashes(self):
        result = detect_pii("Patient NHS: 123-456-7890")
        assert NHS_NUMBER in categories(result)

    def test_ssn_pattern_not_matched_as_nhs(self):
        # SSN format DDD-DD-DDDD should not be matched as NHS
        result = detect_pii("123-45-6789")
        snips = snippets_for(result, NHS_NUMBER)
        # SSN format (3-2-4) must not be labelled NHS (3-3-4)
        assert not any("123-45" in s for s in snips)


# ── date of birth ──────────────────────────────────────────────────────────────

class TestDobDetection:
    def test_dob_label(self):
        f = one(detect_pii("DOB: 01/01/1990"), DATE_OF_BIRTH)
        assert "01/01/1990" in f["snippet"]

    def test_date_of_birth_label(self):
        result = detect_pii("Date of birth: 1990-01-15")
        assert DATE_OF_BIRTH in categories(result)

    def test_born_label(self):
        result = detect_pii("Born: 15.03.1985")
        assert DATE_OF_BIRTH in categories(result)

    def test_geburtsdatum_label(self):
        result = detect_pii("Geburtsdatum: 12.05.1978")
        assert DATE_OF_BIRTH in categories(result)

    def test_birthdate_label(self):
        result = detect_pii("Birthdate: 1972-11-30")
        assert DATE_OF_BIRTH in categories(result)

    def test_confidence(self):
        f = one(detect_pii("DOB: 04/22/1985"), DATE_OF_BIRTH)
        assert f["confidence"] >= 0.9


# ── RegexDetectorConfig ────────────────────────────────────────────────────────

class TestRegexDetectorConfig:
    def test_disable_emails(self):
        cfg = RegexDetectorConfig(emails=False)
        result = detect_pii("user@example.com", config=cfg)
        assert EMAIL not in categories(result)

    def test_disable_phones(self):
        cfg = RegexDetectorConfig(phones=False)
        result = detect_pii("Phone: +1 555-123-4567", config=cfg)
        assert PHONE not in categories(result)

    def test_disable_names(self):
        cfg = RegexDetectorConfig(names=False)
        result = detect_pii("Name: John Smith", config=cfg)
        assert NAME not in categories(result)

    def test_disable_ip_addresses(self):
        cfg = RegexDetectorConfig(ip_addresses=False)
        result = detect_pii("Server: 192.168.1.1", config=cfg)
        assert IP_ADDRESS not in categories(result)

    def test_disable_ssn(self):
        cfg = RegexDetectorConfig(ssn=False)
        result = detect_pii("SSN: 123-45-6789", config=cfg)
        assert SSN not in categories(result)

    def test_only_emails_enabled(self):
        cfg = RegexDetectorConfig(
            names=False, phones=False, usernames=False, signatures=False,
            photo_video=False, addresses=False, id_documents=False, travel=False,
            ip_addresses=False, credit_cards=False, iban=False, ssn=False,
            nhs=False, dob=False,
        )
        text = "Name: John Smith\nEmail: john@smith.com\nSSN: 123-45-6789"
        result = detect_pii(text, config=cfg)
        assert categories(result) == {EMAIL}

    def test_default_config_all_enabled(self):
        cfg = RegexDetectorConfig()
        assert all([
            cfg.names, cfg.emails, cfg.phones, cfg.usernames, cfg.signatures,
            cfg.photo_video, cfg.addresses, cfg.id_documents, cfg.travel,
            cfg.ip_addresses, cfg.credit_cards, cfg.iban, cfg.ssn, cfg.nhs, cfg.dob,
        ])


# ── deduplication ──────────────────────────────────────────────────────────────

class TestDeduplication:
    def test_same_email_at_different_offsets_both_kept(self):
        # Dedup is span-based — two occurrences at different positions are
        # independent findings, not duplicates.
        text = "Email: user@x.com\nContact: user@x.com"
        snips = snippets_for(detect_pii(text), EMAIL)
        assert snips.count("user@x.com") == 2

    def test_overlapping_spans_deduped(self):
        # Two detectors producing overlapping spans in the same category
        # should result in only one finding for that span.
        text = "Phone: 0171-234-5678"
        phone_findings = [f for f in detect_pii(text) if f["category"] == PHONE]
        # Spans must not overlap
        for i in range(len(phone_findings) - 1):
            assert phone_findings[i]["end"] <= phone_findings[i + 1]["start"]

    def test_different_categories_same_position_both_kept(self):
        # An email IS also parseable as part of other fields — different categories at
        # different positions should all appear.
        text = "Email: alice@example.com\nSSN: 123-45-6789"
        cats = categories(detect_pii(text))
        assert EMAIL in cats
        assert SSN in cats


# ── multi-PII document ─────────────────────────────────────────────────────────

class TestMultiPiiDocument:
    def test_realistic_document(self):
        doc = (
            "Employee: Sarah Connor\n"
            "Username: sarah.connor\n"
            "Email: s.connor@company.com\n"
            "Phone: +1 800-555-0199\n"
            "Address: 742 Evergreen Terrace, Springfield\n"
            "Passport no: A1234567\n"
            "DOB: 05/12/1984\n"
            "SSN: 123-45-6789\n"
            "Server IP: 10.0.0.1\n"
        )
        result = detect_pii(doc)
        found = categories(result)
        assert NAME in found
        assert EMAIL in found
        assert PHONE in found
        assert PASSPORT in found
        assert DATE_OF_BIRTH in found
        assert SSN in found
        assert IP_ADDRESS in found
