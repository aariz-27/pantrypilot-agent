from app.domain.ingredient_normalizer import normalize_ingredient_name, normalize_pantry
from app.domain.models import NormalizationStatus


def test_exact_match():
    result = normalize_ingredient_name("rice")
    assert result.canonical_id == "rice"
    assert result.status == NormalizationStatus.EXACT


def test_case_and_whitespace_insensitive():
    result = normalize_ingredient_name("  RICE  ")
    assert result.canonical_id == "rice"
    assert result.status == NormalizationStatus.EXACT


def test_punctuation_cleanup():
    result = normalize_ingredient_name("garlic!!")
    assert result.canonical_id == "garlic"


def test_plural_normalization_via_naive_suffix_stripping():
    result = normalize_ingredient_name("carrots")
    assert result.canonical_id == "carrot"
    assert result.status == NormalizationStatus.EXACT


def test_alias_synonym_capsicum():
    result = normalize_ingredient_name("Capsicum")
    assert result.canonical_id == "bell_pepper"
    assert result.status == NormalizationStatus.ALIAS


def test_alias_marketing_term_chicken_breast():
    result = normalize_ingredient_name("Boneless Chicken Breast")
    assert result.canonical_id == "chicken_breast"
    assert result.status == NormalizationStatus.ALIAS


def test_alias_plural_onions():
    result = normalize_ingredient_name("onions")
    assert result.canonical_id == "onion"


def test_unknown_specialty_item():
    result = normalize_ingredient_name("dried lotus root shavings")
    assert result.canonical_id is None
    assert result.status == NormalizationStatus.UNKNOWN


def test_empty_string_is_unknown_not_an_error():
    result = normalize_ingredient_name("")
    assert result.canonical_id is None
    assert result.status == NormalizationStatus.UNKNOWN


def test_whitespace_only_string_is_unknown():
    result = normalize_ingredient_name("   ")
    assert result.canonical_id is None
    assert result.status == NormalizationStatus.UNKNOWN


def test_malicious_input_is_handled_safely():
    malicious = "<script>alert('xss')</script>"
    result = normalize_ingredient_name(malicious)
    assert result.status == NormalizationStatus.UNKNOWN
    assert result.canonical_id is None


def test_very_long_input_does_not_crash():
    long_input = "a" * 10_000
    result = normalize_ingredient_name(long_input)
    assert result.status == NormalizationStatus.UNKNOWN


def test_normalize_pantry_dedupes_duplicates_to_one_canonical_id():
    result = normalize_pantry(["onion", "onions", "Onion "])
    assert result.canonical_ids == frozenset({"onion"})
    assert result.unresolved == ()


def test_normalize_pantry_tracks_unresolved_raw_names():
    result = normalize_pantry(["rice", "unobtainium"])
    assert result.canonical_ids == frozenset({"rice"})
    assert result.unresolved == ("unobtainium",)


def test_normalize_pantry_empty_list():
    result = normalize_pantry([])
    assert result.canonical_ids == frozenset()
    assert result.unresolved == ()
