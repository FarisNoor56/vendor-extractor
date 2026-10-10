from src.parser import VendorParser


def test_parser_extracts_name():
    html = """
    <html><body>
    <h1 class='company-name'>ABC Textiles</h1>
    <span class='phone-number'>+91 80 12345678 ext 456</span>
    <span class='gst-number'>27AABCT1234F2Z5</span>
    <span class='contact-person'>Rajesh Kumar</span>
    <span class='company-address'>123 Textile Park, Bengaluru</span>
    <span class='categories'>Cloth, Packaging</span>
    </body></html>
    """
    parser = VendorParser()
    data = parser.parse_profile(html, "https://example.com/vendor/1", "Bengaluru")
    assert data["name"] == "ABC Textiles"
    assert data["phone_type"] == "IndiaMART virtual line"


def test_parser_hidden_phone_is_handled():
    html = "<html><body><span class='phone-number'>*** (View contact no)</span></body></html>"
    parser = VendorParser()
    data = parser.parse_profile(html, "https://example.com/vendor/2", "Bengaluru")
    assert data["phone"] == "hidden"


def test_parser_missing_fields_are_empty_strings():
    html = "<html><body></body></html>"
    parser = VendorParser()
    data = parser.parse_profile(html, "https://example.com/vendor/3", "Bengaluru")
    assert data["name"] == ""
    assert data["address"] == ""
    assert data["gst"] == ""
    assert data["contact_person"] == ""
    assert data["phone"] == ""
    assert data["categories"] == ""


def test_parser_direct_phone_is_direct():
    html = "<html><body><span class='phone-number'>+91 9876543210</span></body></html>"
    parser = VendorParser()
    data = parser.parse_profile(html, "https://example.com/vendor/4", "Bengaluru")
    assert data["phone_type"] == "direct"
