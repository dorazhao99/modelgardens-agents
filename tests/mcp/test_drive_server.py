from __future__ import annotations

import types
import importlib
import sys

import pytest


class DummyCreds:
    # Top-level class so it is picklable across import boundaries
    valid = True
    expired = False
    refresh_token = None


def _install_fake_google_modules(monkeypatch):
    # google base
    google = types.ModuleType("google")
    monkeypatch.setitem(sys.modules, "google", google)

    # google.auth.transport.requests
    google_auth = types.ModuleType("google.auth")
    transport = types.ModuleType("google.auth.transport")
    requests_mod = types.ModuleType("google.auth.transport.requests")

    class Request:
        pass

    requests_mod.Request = Request
    monkeypatch.setitem(sys.modules, "google.auth", google_auth)
    monkeypatch.setitem(sys.modules, "google.auth.transport", transport)
    monkeypatch.setitem(sys.modules, "google.auth.transport.requests", requests_mod)

    # google.oauth2.credentials
    oauth2 = types.ModuleType("google.oauth2")
    credentials = types.ModuleType("google.oauth2.credentials")

    class Credentials:
        valid = True
        expired = False
        refresh_token = None

    credentials.Credentials = Credentials
    monkeypatch.setitem(sys.modules, "google.oauth2", oauth2)
    monkeypatch.setitem(sys.modules, "google.oauth2.credentials", credentials)

    # google_auth_oauthlib.flow
    flow_module = types.ModuleType("google_auth_oauthlib.flow")

    class Flow:
        @classmethod
        def from_client_secrets_file(cls, *args, **kwargs):
            return cls()

        def run_local_server(self, port=0):
            # Return a picklable object with .valid attribute
            return DummyCreds()

    flow_module.InstalledAppFlow = Flow
    monkeypatch.setitem(sys.modules, "google_auth_oauthlib.flow", flow_module)

    # googleapiclient.discovery
    discovery = types.ModuleType("googleapiclient.discovery")

    class DummyService:
        def files(self):  # pragma: no cover - not used during registration test
            return self

        def documents(self):  # pragma: no cover
            return self

        def list(self, **kwargs):  # pragma: no cover
            return self

        def get(self, **kwargs):  # pragma: no cover
            return self

        def get_media(self, **kwargs):  # pragma: no cover
            return self

        def export(self, **kwargs):  # pragma: no cover
            return self

        def create(self, **kwargs):  # pragma: no cover
            return self

        def batchUpdate(self, **kwargs):  # pragma: no cover
            return self

        def execute(self):  # pragma: no cover
            return {}

    def build(api, version, credentials=None):
        return DummyService()

    discovery.build = build
    monkeypatch.setitem(sys.modules, "googleapiclient.discovery", discovery)

    # googleapiclient.http
    http = types.ModuleType("googleapiclient.http")

    class MediaIoBaseDownload:
        def __init__(self, buf, req):
            self._done = False

        def next_chunk(self):
            if self._done:
                return None, True
            self._done = True
            return None, False

    http.MediaIoBaseDownload = MediaIoBaseDownload
    monkeypatch.setitem(sys.modules, "googleapiclient.http", http)


def _install_fake_fastmcp(monkeypatch):
    # Provide a fake FastMCP to capture tool registration
    fastmcp_mod = types.ModuleType("mcp.server.fastmcp")

    class FakeFastMCP:
        def __init__(self, name, lifespan=None):
            self.name = name
            self.lifespan = lifespan
            self.tools = []

        def tool(self):
            def decorator(fn):
                self.tools.append(fn)
                return fn
            return decorator

        # For server run() calls in __main__
        def run(self):  # pragma: no cover
            pass

        # For gum tests expecting get_context; not used here
        def get_context(self):  # pragma: no cover
            return None

    fastmcp_mod.FastMCP = FakeFastMCP
    monkeypatch.setitem(sys.modules, "mcp.server.fastmcp", fastmcp_mod)


def test_drive_server_registers_expected_tools(monkeypatch, tmp_path):
    _install_fake_fastmcp(monkeypatch)
    _install_fake_google_modules(monkeypatch)

    # Prepare a valid token file so _get_credentials takes the fast path
    import pickle
    token_path = tmp_path / "token.pickle"
    with open(token_path, "wb") as f:
        pickle.dump(DummyCreds(), f)
    monkeypatch.setenv("GOOGLE_TOKEN_PICKLE", str(token_path))
    monkeypatch.setenv("GOOGLE_CREDENTIALS_JSON", str(tmp_path / "cred.json"))

    server = importlib.import_module("precursor.mcp_servers.drive.server")
    tool_names = {fn.__name__ for fn in server.mcp.tools}
    assert {"search_files", "get_file_as_text", "create_google_doc", "suggest_edit"} <= tool_names


def test_get_file_as_text_type_routing(monkeypatch, tmp_path):
    _install_fake_google_modules(monkeypatch)
    # Valid token pickle to bypass auth flow
    import pickle
    token_path = tmp_path / "token.pickle"
    with open(token_path, "wb") as f:
        pickle.dump(DummyCreds(), f)
    monkeypatch.setenv("GOOGLE_TOKEN_PICKLE", str(token_path))
    monkeypatch.setenv("GOOGLE_CREDENTIALS_JSON", str(tmp_path / "cred.json"))
    server = importlib.import_module("precursor.mcp_servers.drive.server")

    # Minimal drive service for meta queries
    class FilesAPI:
        def __init__(self, file_id_to_meta):
            self.map = file_id_to_meta

        def get(self, fileId, fields=None):
            class R:
                def __init__(self, meta):
                    self._meta = meta
                def execute(self):
                    return self._meta
            return R(self.map[fileId])

    class DriveService:
        def __init__(self, file_id_to_meta):
            self._files = FilesAPI(file_id_to_meta)
        def files(self):
            return self._files

    class DocsService:
        def documents(self):  # pragma: no cover - not used here
            return self

    def fake_build(api, version, credentials=None):
        if api == "drive":
            return DriveService({
                "doc": {"mimeType": "application/vnd.google-apps.document"},
                "sheet": {"mimeType": "application/vnd.google-apps.spreadsheet"},
                "binary": {"mimeType": "application/pdf", "size": "12"},
            })
        return DocsService()

    monkeypatch.setattr(server, "build", fake_build)

    dt = server.DriveTools(credentials_file=str(tmp_path / "cred.json"), token_file=str(token_path))

    # Patch bytes exporters
    monkeypatch.setattr(dt, "_export_bytes", lambda fid, mime: b"Hello, world\n" if mime in ("text/plain", "text/csv") else b"")
    monkeypatch.setattr(dt, "_download_bytes", lambda fid: b"Binary content")

    assert dt.get_file_as_text("doc").startswith("Hello")
    sheet_text = dt.get_file_as_text("sheet")
    assert isinstance(sheet_text, str) and len(sheet_text) > 0 and ("\n" in sheet_text or "," in sheet_text)
    bin_text = dt.get_file_as_text("binary")
    assert "Binary content" in bin_text or "application/pdf" in bin_text


def test_suggest_edit_locator_modes_use_correct_indices(monkeypatch, tmp_path):
    _install_fake_google_modules(monkeypatch)
    import pickle
    token_path = tmp_path / "token.pickle"
    with open(token_path, "wb") as f:
        pickle.dump(DummyCreds(), f)
    monkeypatch.setenv("GOOGLE_TOKEN_PICKLE", str(token_path))
    monkeypatch.setenv("GOOGLE_CREDENTIALS_JSON", str(tmp_path / "cred.json"))
    server = importlib.import_module("precursor.mcp_servers.drive.server")

    class DocsBatch:
        def __init__(self, capture):
            self.capture = capture
        def execute(self):
            # Return the captured request body for assertions (simulated)
            return {"ok": True}

    class DocsDocuments:
        def __init__(self, capture):
            self.capture = capture
        def get(self, documentId):
            class R:
                def execute(self_inner):
                    # Minimal doc shape
                    return {"body": {"content": [{"endIndex": 50}]}}
            return R()
        def batchUpdate(self, documentId, body):
            self.capture.append(body)
            return DocsBatch(self.capture)

    class DocsService:
        def __init__(self, capture):
            self._docs = DocsDocuments(capture)
        def documents(self):
            return self._docs

    class DriveService:
        pass

    captured = []
    def fake_build(api, version, credentials=None):
        if api == "docs":
            return DocsService(captured)
        return DriveService()

    monkeypatch.setattr(server, "build", fake_build)
    dt = server.DriveTools(credentials_file=str(tmp_path / "cred.json"), token_file=str(token_path))

    # Force helper returns
    monkeypatch.setattr(dt, "_doc_end_index", lambda doc: 50)
    monkeypatch.setattr(dt, "_find_after_text", lambda doc, t, occ: 10)
    monkeypatch.setattr(dt, "_find_after_heading", lambda doc, h: 20)

    # Top
    captured.clear()
    out = dt.suggest_edit("docid", {"mode": "top"}, "X")
    assert out["insert_index"] == 1
    # End
    captured.clear()
    out = dt.suggest_edit("docid", {"mode": "end"}, "X")
    assert out["insert_index"] == 50
    # after_text
    captured.clear()
    out = dt.suggest_edit("docid", {"mode": "after_text", "text": "foo", "occurrence": 1}, "X")
    assert out["insert_index"] == 10
    # after_heading
    captured.clear()
    out = dt.suggest_edit("docid", {"mode": "after_heading", "heading": "intro"}, "X")
    assert out["insert_index"] == 20


def test_suggest_edit_docstring_contains_locator_schema(monkeypatch, tmp_path):
    # Ensure valid token pickle before import so module-level _DRIVE instantiates cleanly
    import pickle
    token_path = tmp_path / "token.pickle"
    with open(token_path, "wb") as f:
        pickle.dump(DummyCreds(), f)
    monkeypatch.setenv("GOOGLE_TOKEN_PICKLE", str(token_path))
    monkeypatch.setenv("GOOGLE_CREDENTIALS_JSON", str(tmp_path / "cred.json"))
    server = importlib.import_module("precursor.mcp_servers.drive.server")
    doc = server.suggest_edit.__doc__ or ""
    assert "after_text" in doc
    assert "after_heading" in doc
    assert "top" in doc
    assert "end" in doc


