"""
Test suite for oauth/token_store.py

Covers OAuthToken (serialization + expiry logic), the TokenStore ABC
contract, and the FileTokenStore concrete implementation (round-tripping,
atomic writes, permissions, and failure handling).
"""

import json
import os
import time
from pathlib import Path

import pytest

from hakiapi.core.oauth.token_store import OAuthToken, TokenStore, FileTokenStore


# OAuthToken - to_dict / from_dict


class TestOAuthTokenSerialization:
    def test_to_dict_contains_all_fields(self):
        token = OAuthToken(
            access_token="access-123",
            refresh_token="refresh-456",
            expires_at=1_700_000_000.0,
            scopes=["gmail.readonly", "calendar"],
        )
        data = token.to_dict()
        assert data == {
            "access_token": "access-123",
            "refresh_token": "refresh-456",
            "expires_at": 1_700_000_000.0,
            "scopes": ["gmail.readonly", "calendar"],
        }

    def test_to_dict_scopes_is_a_copy_not_the_same_list(self):
        scopes = ["gmail.readonly"]
        token = OAuthToken(access_token="a", scopes=scopes)
        data = token.to_dict()
        data["scopes"].append("calendar")
        assert token.scopes == ["gmail.readonly"]

    def test_from_dict_round_trip(self):
        original = OAuthToken(
            access_token="access-123",
            refresh_token="refresh-456",
            expires_at=1_700_000_000.0,
            scopes=["gmail.readonly"],
        )
        rebuilt = OAuthToken.from_dict(original.to_dict())
        assert rebuilt == original

    def test_from_dict_minimal_required_field_only(self):
        token = OAuthToken.from_dict({"access_token": "only-this"})
        assert token.access_token == "only-this"
        assert token.refresh_token is None
        assert token.expires_at is None
        assert token.scopes == []

    def test_from_dict_missing_access_token_raises_value_error(self):
        with pytest.raises(ValueError):
            OAuthToken.from_dict({"refresh_token": "r"})

    def test_from_dict_null_scopes_defaults_to_empty_list(self):
        token = OAuthToken.from_dict({"access_token": "a", "scopes": None})
        assert token.scopes == []

    def test_from_dict_does_not_mutate_input_dict(self):
        data = {"access_token": "a", "scopes": ["x"]}
        OAuthToken.from_dict(data)
        assert data == {"access_token": "a", "scopes": ["x"]}

    def test_default_scopes_is_independent_per_instance(self):
        # Guards against a mutable-default-argument style bug even though
        # a dataclass field(default_factory=list) is used correctly here.
        t1 = OAuthToken(access_token="a")
        t2 = OAuthToken(access_token="b")
        t1.scopes.append("gmail.readonly")
        assert t2.scopes == []


# OAuthToken - is_expired


class TestOAuthTokenIsExpired:
    def test_no_expiry_is_never_expired(self):
        token = OAuthToken(access_token="a", expires_at=None)
        assert token.is_expired is False

    def test_far_future_expiry_is_not_expired(self):
        token = OAuthToken(access_token="a", expires_at=time.time() + 3600)
        assert token.is_expired is False

    def test_past_expiry_is_expired(self):
        token = OAuthToken(access_token="a", expires_at=time.time() - 10)
        assert token.is_expired is True

    def test_within_leeway_window_counts_as_expired(self):
        # 30s leeway: a token expiring in 10s should already read as expired
        # so callers refresh ahead of the real deadline.
        token = OAuthToken(access_token="a", expires_at=time.time() + 10)
        assert token.is_expired is True

    def test_just_outside_leeway_window_is_not_expired(self):
        token = OAuthToken(access_token="a", expires_at=time.time() + 45)
        assert token.is_expired is False

    def test_expiry_exactly_now_is_expired(self):
        token = OAuthToken(access_token="a", expires_at=time.time())
        assert token.is_expired is True


# TokenStore - abstract contract


class TestTokenStoreContract:
    def test_cannot_instantiate_abstract_base_class(self):
        with pytest.raises(TypeError):
            TokenStore()  # type: ignore[abstract]

    def test_subclass_missing_methods_cannot_be_instantiated(self):
        class IncompleteStore(TokenStore):
            def get_token(self):
                return None

            # save_token and delete_token intentionally omitted

        with pytest.raises(TypeError):
            IncompleteStore()  # type: ignore[abstract]

    def test_subclass_implementing_all_methods_can_be_instantiated(self):
        class CompleteStore(TokenStore):
            def get_token(self):
                return None

            def save_token(self, token):
                pass

            def delete_token(self):
                pass

        assert isinstance(CompleteStore(), TokenStore)


# FileTokenStore - basic get/save round trip


class TestFileTokenStoreRoundTrip:
    def test_get_token_returns_none_when_file_does_not_exist(self, tmp_path: Path):
        store = FileTokenStore(tmp_path / "token.json")
        assert store.get_token() is None

    def test_save_then_get_round_trips_full_token(self, tmp_path: Path):
        store = FileTokenStore(tmp_path / "token.json")
        token = OAuthToken(
            access_token="access-123",
            refresh_token="refresh-456",
            expires_at=1_700_000_000.0,
            scopes=["gmail.readonly", "calendar"],
        )
        store.save_token(token)
        loaded = store.get_token()
        assert loaded == token

    def test_save_writes_readable_json_to_disk(self, tmp_path: Path):
        path = tmp_path / "token.json"
        store = FileTokenStore(path)
        store.save_token(OAuthToken(access_token="abc"))
        on_disk = json.loads(path.read_text(encoding="utf-8"))
        assert on_disk["access_token"] == "abc"

    def test_save_overwrites_previous_token(self, tmp_path: Path):
        store = FileTokenStore(tmp_path / "token.json")
        store.save_token(OAuthToken(access_token="first"))
        store.save_token(OAuthToken(access_token="second"))

        # Type guard: ensure it's not None before checking attributes
        token = store.get_token()
        assert token is not None
        assert token.access_token == "second"

    def test_default_path_is_token_json(self):
        store = FileTokenStore()
        assert store.path == Path("token.json")

    def test_accepts_str_path(self, tmp_path: Path):
        store = FileTokenStore(str(tmp_path / "token.json"))
        assert store.path == tmp_path / "token.json"

    def test_save_creates_missing_parent_directories(self, tmp_path: Path):
        nested_path = tmp_path / "nested" / "dirs" / "token.json"
        store = FileTokenStore(nested_path)
        store.save_token(OAuthToken(access_token="abc"))
        assert nested_path.exists()


# FileTokenStore - malformed / edge-case file contents


class TestFileTokenStoreMalformedFile:
    def test_empty_file_returns_none(self, tmp_path: Path):
        path = tmp_path / "token.json"
        path.write_text("", encoding="utf-8")
        store = FileTokenStore(path)
        assert store.get_token() is None

    def test_whitespace_only_file_returns_none(self, tmp_path: Path):
        path = tmp_path / "token.json"
        path.write_text("   \n  ", encoding="utf-8")
        store = FileTokenStore(path)
        assert store.get_token() is None

    def test_invalid_json_raises_value_error(self, tmp_path: Path):
        path = tmp_path / "token.json"
        path.write_text("{not valid json", encoding="utf-8")
        store = FileTokenStore(path)
        with pytest.raises(ValueError):
            store.get_token()

    def test_valid_json_missing_access_token_raises_value_error(self, tmp_path: Path):
        path = tmp_path / "token.json"
        path.write_text(json.dumps({"refresh_token": "r"}), encoding="utf-8")
        store = FileTokenStore(path)
        with pytest.raises(ValueError):
            store.get_token()

    def test_read_oserror_is_wrapped_and_reraised(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        path = tmp_path / "token.json"
        path.write_text(json.dumps({"access_token": "a"}), encoding="utf-8")
        store = FileTokenStore(path)

        def broken_read_text(self, *args, **kwargs):
            raise OSError("simulated disk failure")

        monkeypatch.setattr(Path, "read_text", broken_read_text)

        with pytest.raises(OSError):
            store.get_token()


# FileTokenStore - atomicity, permissions, cleanup


class TestFileTokenStoreAtomicityAndPermissions:
    def test_no_leftover_temp_files_after_successful_save(self, tmp_path: Path):
        store = FileTokenStore(tmp_path / "token.json")
        store.save_token(OAuthToken(access_token="abc"))
        remaining = list(tmp_path.iterdir())
        assert remaining == [tmp_path / "token.json"]

    @pytest.mark.skipif(os.name == "nt", reason="POSIX file permissions only")
    def test_saved_file_has_0600_permissions(self, tmp_path: Path):
        path = tmp_path / "token.json"
        store = FileTokenStore(path)
        store.save_token(OAuthToken(access_token="abc"))
        mode = oct(path.stat().st_mode)[-3:]
        assert mode == "600"

    def test_temp_file_is_cleaned_up_when_write_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        store = FileTokenStore(tmp_path / "token.json")

        def broken_dump(*args, **kwargs):
            raise RuntimeError("simulated write failure")

        monkeypatch.setattr(json, "dump", broken_dump)

        with pytest.raises(RuntimeError):
            store.save_token(OAuthToken(access_token="abc"))

        # No stray .tmp files and no partial target file left behind.
        assert list(tmp_path.iterdir()) == []

    def test_original_file_untouched_if_save_fails_after_it_exists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        path = tmp_path / "token.json"
        store = FileTokenStore(path)
        store.save_token(OAuthToken(access_token="original"))

        def broken_dump(*args, **kwargs):
            raise RuntimeError("simulated write failure")

        monkeypatch.setattr(json, "dump", broken_dump)

        with pytest.raises(RuntimeError):
            store.save_token(OAuthToken(access_token="new"))

        # The atomic-replace never happened, so the original content survives.
        # Type guard: ensure it's not None before checking attributes
        token = store.get_token()
        assert token is not None
        assert token.access_token == "original"


# FileTokenStore - delete_token


class TestFileTokenStoreDelete:
    def test_delete_removes_existing_token_file(self, tmp_path: Path):
        path = tmp_path / "token.json"
        store = FileTokenStore(path)
        store.save_token(OAuthToken(access_token="abc"))
        store.delete_token()
        assert not path.exists()

    def test_delete_then_get_returns_none(self, tmp_path: Path):
        store = FileTokenStore(tmp_path / "token.json")
        store.save_token(OAuthToken(access_token="abc"))
        store.delete_token()
        assert store.get_token() is None

    def test_delete_is_idempotent_when_no_file_exists(self, tmp_path: Path):
        store = FileTokenStore(tmp_path / "token.json")
        store.delete_token()
        store.delete_token()  # must not raise

    def test_delete_does_not_touch_unrelated_files(self, tmp_path: Path):
        other = tmp_path / "unrelated.json"
        other.write_text("{}", encoding="utf-8")
        store = FileTokenStore(tmp_path / "token.json")
        store.save_token(OAuthToken(access_token="abc"))
        store.delete_token()
        assert other.exists()
