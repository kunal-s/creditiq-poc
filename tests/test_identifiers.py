from engine import identifiers as ids


def test_gstin_check_digit_known_answers():
    # Independently verified valid GSTINs (plan.md finding 2 / reference/05 section G).
    assert ids.gstin_check_digit("27AAPFU0939F1Z") == "V"
    assert ids.gstin_check_digit("29AAGCB7383J1Z") == "4"
    assert ids.gstin_check_digit("33AAHCS6612M1Z") == "5"


def test_validate_gstin_known_answers():
    assert ids.validate_gstin("27AAPFU0939F1ZV")
    assert ids.validate_gstin("29AAGCB7383J1Z4")
    # The generic repo's seed GSTINs are known to fail their own checksum.
    assert not ids.validate_gstin("33AAHCS6612M1ZQ")
    assert not ids.validate_gstin("27AABCN4521Q1ZP")


def test_build_gstin_round_trips():
    gstin = ids.build_gstin("33", "AAHCS6612M", "1")
    assert gstin == "33AAHCS6612M1Z5"
    assert ids.validate_gstin(gstin)


def test_build_gstin_rejects_bad_pan():
    try:
        ids.build_gstin("33", "NOTAPAN", "1")
    except ids.IdentifierError:
        pass
    else:
        raise AssertionError("expected IdentifierError")


def test_pan_format_and_holder_type():
    assert ids.validate_pan_format("AAHCS6612M")
    assert ids.validate_pan("AAHCS6612M", holder_type="company")
    assert not ids.validate_pan("AAHCS6612M", holder_type="individual")
    assert not ids.validate_pan_format("INVALIDPAN")


def test_cin_format_and_consistency():
    cin = "U17291TZ2016PTC027431"
    assert ids.validate_cin(cin)
    assert ids.validate_cin(cin, formed_year=2016, roc="TZ")
    assert not ids.validate_cin(cin, formed_year=2017)
    assert not ids.validate_cin(cin, roc="PN")


def test_udyam_format():
    assert ids.validate_udyam("UDYAM-TN-03-0001234")
    assert not ids.validate_udyam("UDYAM-TN-3-0001234")


def test_ifsc_format():
    assert ids.validate_ifsc("RATN0000123")
    assert not ids.validate_ifsc("RATN1000123")  # 5th char must be '0'


def test_tan_din_udin_itr_formats():
    assert ids.validate_tan("CMBS12345F")
    assert ids.validate_din("01847362")
    assert not ids.validate_din("1847362")
    assert ids.validate_itr_ack("274918365120725")
    assert ids.validate_udin("24051233AKQPTL4419")
