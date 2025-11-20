# src/precursor/mcp_servers/drive/server.py
"""
Google Drive MCP Server (FastMCP)

This module exposes a minimal set of Google Drive + Google Docs tools as
MCP tools using FastMCP. Tools are documented with rich docstrings because
LLM tool-callers will read them to decide how to call each function.

Environment variables (configurable via `config/mcp_servers.yaml` under `env`):
  - GOOGLE_CREDENTIALS_JSON: path to your OAuth2 client secrets JSON (default: "credentials.json")
  - GOOGLE_TOKEN_PICKLE:     path to the local token cache (default: "token.pickle")

Exposed tools (namespaced as "drive.*"):
  - drive.search_files(query, page_size=20) -> List[dict]
  - drive.get_file_as_text(file_id) -> str
  - drive.create_google_doc(name, parent_folder_id=None) -> str
  - drive.suggest_edit(document_id, locator, suggestion_text) -> Dict[str, Any]

Run locally:
  python -m precursor.mcp_servers.drive.server
"""

from __future__ import annotations

import io
import os
import pickle
from typing import Any, Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.auth.exceptions import RefreshError

from mcp.server.fastmcp import FastMCP


# ========= Scopes (Drive read/write + Docs edits) =========
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
]


# ========= Auth / Service =========
def _get_credentials(
    credentials_file: str = "credentials.json",
    token_file: str = "token.pickle",
    scopes: List[str] = SCOPES,
) -> Credentials:
    """
    Load or prompt for OAuth2 user credentials and cache them in `token_file`.

    Returns
    -------
    Credentials
        User-authorized credentials that auto-refresh when expired.
    """
    creds: Optional[Credentials] = None
    if os.path.exists(token_file):
        try:
            with open(token_file, "rb") as f:
                creds = pickle.load(f)
        except Exception:
            # Corrupt/empty token cache; ignore and proceed to fresh auth flow
            creds = None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                # Token refresh failed (e.g., invalid_grant: expired or revoked).
                # Delete the cached token and force a fresh login.
                try:
                    if os.path.exists(token_file):
                        os.remove(token_file)
                except Exception:
                    # Best-effort cleanup; continue to re-auth regardless.
                    pass
                creds = None

        if not creds or not creds.valid:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, scopes)
            creds = flow.run_local_server(port=0)
        with open(token_file, "wb") as f:
            pickle.dump(creds, f)
    return creds


class DriveTools:
    """
    Minimal Google Drive + Docs tools exposing four agent-friendly capabilities:

    1) search_files(query, page_size)
       - Search Drive with standard Drive query; returns lightweight metadata.

    2) get_file_as_text(file_id)
       - Return file contents as **plain text** when possible (Docs/Sheets/Slides).
       - For binaries (e.g., PDFs), returns a readable placeholder string.

    3) create_google_doc(name, parent_folder_id)
       - Create a new Google Doc and return its file ID.

    4) suggest_edit(document_id, locator, suggestion_text)
       - Insert an edit in a Google Doc at the location described by `locator`,
         and auto-highlight it (light orange) so humans see it immediately.
       - This replaces “commenting” in agent workflows with visible in-doc edits.

    Notes
    -----
    - No public API exists to create tracked “Suggesting mode” edits. We use
      real insertions plus highlight for a clear, reliable UX.
    - Indices are UTF-16; concurrent edits may shift indices between read & write.
    """

    def __init__(self, credentials_file: str = "credentials.json", token_file: str = "token.pickle") -> None:
        creds = _get_credentials(credentials_file, token_file, SCOPES)
        self.drive = build("drive", "v3", credentials=creds)
        self.docs = build("docs", "v1", credentials=creds)

    # ===== 1) Search =====
    def search_files(self, query: str, page_size: int = 20) -> List[Dict[str, Any]]:
        """
        Search for files in the user’s Google Drive.

        Parameters
        ----------
        query : str
            Drive query string, e.g.:
              - name contains 'Report'
              - mimeType='application/vnd.google-apps.document'
              - fullText contains 'budget'
        page_size : int
            Max number of results to return.

        Returns
        -------
        List[Dict[str, Any]]
            Each dict contains: {id, name, mimeType, modifiedTime}.
        """
        resp = self.drive.files().list(
            q=query,
            pageSize=page_size,
            fields="files(id,name,mimeType,modifiedTime)"
        ).execute()
        return resp.get("files", [])

    # ===== 2) Read (plain text) =====
    def get_file_as_text(self, file_id: str) -> str:
        """
        Return the file's contents as **plain text** when possible.

        Behavior by file type:
          - Google Docs: exported as text/plain.
          - Google Sheets: exported as text/csv (returned as a single string).
          - Google Slides: exported as text/plain (speaker notes & text boxes).
          - Other/binary files (e.g., PDFs): returns a placeholder string with size/MIME.

        Parameters
        ----------
        file_id : str
            Drive file ID.

        Returns
        -------
        str
            Plain text contents (best effort). For binaries: a readable placeholder.
        """
        meta = self.drive.files().get(fileId=file_id, fields="mimeType, size").execute()
        mime = meta.get("mimeType", "")
        size = int(meta.get("size", 0)) if meta.get("size") else None

        # Google Editors
        if mime == "application/vnd.google-apps.document":
            data = self._export_bytes(file_id, "text/plain")
            return self._bytes_to_text(data)
        if mime == "application/vnd.google-apps.spreadsheet":
            data = self._export_bytes(file_id, "text/csv")
            return self._bytes_to_text(data)
        if mime == "application/vnd.google-apps.presentation":
            data = self._export_bytes(file_id, "text/plain")
            return self._bytes_to_text(data)

        # Other files: try decoding; if binary, return a helpful placeholder.
        data_bytes = self._download_bytes(file_id)
        try:
            return data_bytes.decode("utf-8")
        except Exception:
            approx = len(data_bytes) if isinstance(data_bytes, (bytes, bytearray)) else 0
            return f"[Binary content: {mime or 'unknown'}; approx {approx} bytes]"

    # ===== 3) Write =====
    def create_google_doc(self, name: str, parent_folder_id: Optional[str] = None) -> str:
        """
        Create a new Google Doc and return its Drive file ID.

        Parameters
        ----------
        name : str
            Document name shown in Drive.
        parent_folder_id : Optional[str]
            If provided, create inside this folder.

        Returns
        -------
        str
            The new file ID (also the Docs documentId).
        """
        meta: Dict[str, Any] = {"name": name, "mimeType": "application/vnd.google-apps.document"}
        if parent_folder_id:
            meta["parents"] = [parent_folder_id]
        res = self.drive.files().create(body=meta, fields="id").execute()
        return res["id"]

    # ===== 4) Insert edits (agent “comment” replacement) =====
    def suggest_edit(self, document_id: str, locator: Dict[str, Any], suggestion_text: str) -> Dict[str, Any]:
        """
        Insert and highlight an edit in a Google Doc at a location chosen by `locator`.

        Parameters
        ----------
        document_id : str
            Docs document ID (same as Drive file ID for Google Docs).
        locator : Dict[str, Any]
            Where to insert. Supported forms (case-insensitive `mode`):
              - {"mode": "top"}
                  Insert near the start of the document (index 1).

              - {"mode": "end"}
                  Insert at the end of the body content.

              - {"mode": "after_text", "text": "<literal>", "occurrence": 1}
                  Find the Nth (default 1) occurrence of the literal substring `text`
                  in document order and insert *after* it.
                  Example:
                    {"mode": "after_text", "text": "Introduction", "occurrence": 1}

              - {"mode": "after_heading", "heading": "<substring>"}
                  Find the first paragraph styled as a heading (Heading 1..6, Title, Subtitle)
                  whose text contains `heading` (case-insensitive substring) and insert *after* it.
                  Example:
                    {"mode": "after_heading", "heading": "Methods"}

            Notes:
              - For `after_text`, matching is a simple substring search through paragraph text runs.
              - For `after_heading`, we match on heading-styled paragraphs only.
              - If no valid location can be computed, we fall back to index 1 (top).

        suggestion_text : str
            Text to insert and highlight (light orange).

        Returns
        -------
        Dict[str, Any]
            {
              "insert_index": int,              # index used for insertion
              "insert_response": dict,          # Docs batchUpdate response (insertText)
              "highlight_response": dict        # Docs batchUpdate response (updateTextStyle)
            }

        Behavior & Caveats
        ------------------
        - Google Docs API does not expose a public "Suggesting mode" write path; we perform real
          insertions and then highlight the inserted span for a clear, reviewable UX.
        - Document indices are UTF-16 code-unit based; concurrent human edits may shift indices
          between read and write operations.
        """
        doc = self.docs.documents().get(documentId=document_id).execute()
        insert_index = self._compute_insert_index(doc, locator) or 1

        insert_resp = self._insert_text(document_id, insert_index, suggestion_text)
        end_index = insert_index + len(suggestion_text)
        highlight_resp = self._highlight_range(document_id, insert_index, end_index)

        return {"insert_index": insert_index, "insert_response": insert_resp, "highlight_response": highlight_resp}

    # ========= Private helpers =========
    def _export_bytes(self, file_id: str, mime: str) -> bytes:
        req = self.drive.files().export(fileId=file_id, mimeType=mime)
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, req)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buf.getvalue()

    def _download_bytes(self, file_id: str) -> bytes:
        req = self.drive.files().get_media(fileId=file_id)
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, req)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buf.getvalue()

    @staticmethod
    def _bytes_to_text(data: bytes) -> str:
        try:
            return data.decode("utf-8")
        except Exception:
            return data.decode("latin-1", errors="ignore")

    def _insert_text(self, document_id: str, index: int, text: str) -> Dict[str, Any]:
        requests = [{"insertText": {"location": {"index": index}, "text": text}}]
        return self.docs.documents().batchUpdate(documentId=document_id, body={"requests": requests}).execute()

    def _highlight_range(self, document_id: str, start_index: int, end_index: int) -> Dict[str, Any]:
        # Light orange highlight
        requests = [{
            "updateTextStyle": {
                "range": {"startIndex": start_index, "endIndex": end_index},
                "textStyle": {
                    "backgroundColor": {"color": {"rgbColor": {"red": 1.0, "green": 0.9, "blue": 0.6}}}
                },
                "fields": "backgroundColor"
            }
        }]
        return self.docs.documents().batchUpdate(documentId=document_id, body={"requests": requests}).execute()

    # ----- Insert index computation -----
    def _compute_insert_index(self, doc: Dict[str, Any], locator: Dict[str, Any]) -> Optional[int]:
        mode = (locator.get("mode") or "").lower()

        if mode == "top":
            return 1

        if mode == "end":
            return self._doc_end_index(doc)

        if mode == "after_text":
            text = locator.get("text", "")
            occ = int(locator.get("occurrence", 1)) if locator.get("occurrence") else 1
            return self._find_after_text(doc, text, occ)

        if mode == "after_heading":
            heading = locator.get("heading", "")
            return self._find_after_heading(doc, heading)

        return None

    def _doc_end_index(self, doc: Dict[str, Any]) -> int:
        body = doc.get("body", {})
        content = body.get("content", []) or []
        if not content:
            return 1
        last = content[-1]
        return int(last.get("endIndex", 1))

    def _find_after_text(self, doc: Dict[str, Any], needle: str, occurrence: int = 1) -> Optional[int]:
        if not needle:
            return None
        remaining = occurrence
        for el in doc.get("body", {}).get("content", []):
            para = el.get("paragraph")
            if not para:
                continue
            for run in para.get("elements", []):
                tr = run.get("textRun", {})
                txt = tr.get("content", "") or ""
                base = txt.lower()
                n = needle.lower()
                offset = 0
                while True:
                    pos = base.find(n, offset)
                    if pos == -1:
                        break
                    remaining -= 1
                    if remaining == 0:
                        return int(run["startIndex"]) + pos + len(needle)
                    offset = pos + len(needle)
        return None

    def _find_after_heading(self, doc: Dict[str, Any], heading_text: str) -> Optional[int]:
        if not heading_text:
            return None
        target = heading_text.lower()
        for el in doc.get("body", {}).get("content", []):
            para = el.get("paragraph")
            if not para:
                continue
            st = para.get("paragraphStyle", {})
            named = st.get("namedStyleType", "")
            if not named or ("HEADING" not in named and named not in ("TITLE", "SUBTITLE")):
                continue
            # collect paragraph text
            buf = []
            for run in para.get("elements", []):
                tr = run.get("textRun", {})
                buf.append(tr.get("content", "") or "")
            text = "".join(buf).strip()
            if target in text.lower():
                return int(el.get("endIndex", 0))
        return None


# ========= FastMCP server wiring =========

mcp = FastMCP("drive")

# Construct a single DriveTools instance using env-provided paths (or defaults).
_DRIVE = DriveTools(
    credentials_file=os.environ.get("GOOGLE_CREDENTIALS_JSON", "credentials.json"),
    token_file=os.environ.get("GOOGLE_TOKEN_PICKLE", "token.pickle"),
)

@mcp.tool()
def search_files(query: str, page_size: int = 20) -> List[Dict[str, Any]]:
    """
    Search for files in the user’s Google Drive.

    Parameters
    ----------
    query : str
        Drive query string, e.g.:
          - name contains 'Report'
          - mimeType='application/vnd.google-apps.document'
          - fullText contains 'budget'
    page_size : int
        Max number of results to return.

    Returns
    -------
    List[Dict[str, Any]]
        Each dict contains: {id, name, mimeType, modifiedTime}.
    """
    return _DRIVE.search_files(query, page_size)


@mcp.tool()
def get_file_as_text(file_id: str) -> str:
    """
    Return the file's contents as **plain text** when possible.

    Behavior by file type:
      - Google Docs: exported as text/plain.
      - Google Sheets: exported as text/csv (returned as a single string).
      - Google Slides: exported as text/plain (speaker notes & text boxes).
      - Other/binary files (e.g., PDFs): returns a placeholder string with size/MIME.

    Parameters
    ----------
    file_id : str
        Drive file ID.

    Returns
    -------
    str
        Plain text contents (best effort). For binaries: a readable placeholder.
    """
    return _DRIVE.get_file_as_text(file_id)


@mcp.tool()
def create_google_doc(name: str, parent_folder_id: Optional[str] = None) -> str:
    """
    Create a new Google Doc and return its Drive file ID.

    Parameters
    ----------
    name : str
        Document name shown in Drive.
    parent_folder_id : Optional[str]
        If provided, create inside this folder.

    Returns
    -------
    str
        The new file ID (also the Docs documentId).
    """
    return _DRIVE.create_google_doc(name, parent_folder_id)


@mcp.tool()
def suggest_edit(document_id: str, locator: Dict[str, Any], suggestion_text: str) -> Dict[str, Any]:
    """
    Insert and highlight an edit in a Google Doc at a location chosen by `locator`.

    Parameters
    ----------
    document_id : str
        Docs document ID (same as Drive file ID for Google Docs).
    locator : Dict[str, Any]
        Where to insert. Supported forms (case-insensitive `mode`):
          - {"mode": "top"}
              Insert near the start of the document (index 1).

          - {"mode": "end"}
              Insert at the end of the body content.

          - {"mode": "after_text", "text": "<literal>", "occurrence": 1}
              Find the Nth (default 1) occurrence of the literal substring `text`
              in document order and insert *after* it.
              Example:
                {"mode": "after_text", "text": "Introduction", "occurrence": 1}

          - {"mode": "after_heading", "heading": "<substring>"}
              Find the first paragraph styled as a heading (Heading 1..6, Title, Subtitle)
              whose text contains `heading` (case-insensitive substring) and insert *after* it.
              Example:
                {"mode": "after_heading", "heading": "Methods"}

        Notes:
          - For `after_text`, matching is a simple substring search through paragraph text runs.
          - For `after_heading`, we match on heading-styled paragraphs only.
          - If no valid location can be computed, we fall back to index 1 (top).

    suggestion_text : str
        Text to insert and highlight (light orange).

    Returns
    -------
    Dict[str, Any]
        {
          "insert_index": int,              # index used for insertion
          "insert_response": dict,          # Docs batchUpdate response (insertText)
          "highlight_response": dict        # Docs batchUpdate response (updateTextStyle)
        }

    Behavior & Caveats
    ------------------
    - Google Docs API does not expose a public "Suggesting mode" write path; we perform real
      insertions and then highlight the inserted span for a clear, reviewable UX.
    - Document indices are UTF-16 code-unit based; concurrent human edits may shift indices
      between read and write operations.
    """
    return _DRIVE.suggest_edit(document_id, locator, suggestion_text)


if __name__ == "__main__":
    mcp.run()