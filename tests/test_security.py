from app.core.security import safe_stem, valid_result_id, valid_session_id


def test_filename_sanitizing_removes_paths_and_unsafe_characters():
    assert safe_stem(r"..\..\secret file.png") == "secret_file"
    assert safe_stem("../../") == "image"


def test_identifiers_only_allow_expected_token_characters():
    assert valid_session_id("session-identifier-0123456789")
    assert not valid_session_id("../outside")
    assert valid_result_id("result_identifier-0123456789")
    assert not valid_result_id("../../file")
