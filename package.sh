uv run pyinstaller --onefile entry.py \
--hidden-import=tiktoken_ext.openai_public \
--hidden-import=tiktoken_ext \
--hidden-import=litellm.litellm_core_utils.tokenizers \
--hidden-import=googleapiclient.discovery \
--hidden-import=googleapiclient.http \
--hidden-import=google_auth_oauthlib.flow \
--hidden-import=google.oauth2.credentials \
--hidden-import=google.auth.transport.requests \
--hidden-import=google.auth.exceptions \
--hidden-import=fastmcp \
--collect-submodules=fastmcp \
--collect-data=litellm \
--collect-submodules=litellm.litellm_core_utils.tokenizers \
--copy-metadata=fastmcp \
--collect-data=modelgarden \
--collect-submodules=modelgarden

uv run pyinstaller --onefile mcp_directory.py \
--hidden-import=googleapiclient.discovery \
--hidden-import=googleapiclient.http \
--hidden-import=google_auth_oauthlib.flow \
--hidden-import=google.oauth2.credentials \
--hidden-import=google.auth.transport.requests \
--hidden-import=google.auth.exceptions \
--hidden-import=fastmcp \
--collect-submodules=fastmcp \
--copy-metadata=fastmcp \
--collect-data=modelgarden \
--collect-submodules=modelgarden