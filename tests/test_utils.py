from domhunter.utils import normalize_domain


def test_normalize_domain_basic():
    assert normalize_domain("Example.com") == "example.com"
    assert normalize_domain(" https://www.Example.com/path ") == "www.example.com"


def test_normalize_domain_invalid():
    assert normalize_domain("") is None
    assert normalize_domain("not a domain") is None