import base64
import hashlib
import os
import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.responses import JSONResponse

from config import SECRET_TOKEN
from transport.middleware import debug_log

router = APIRouter()

_auth_codes = {}

@router.get("/.well-known/oauth-authorization-server")
@router.get("/.well-known/oauth-authorization-server/{path:path}")
async def oauth_authorization_server(request: Request, path: str | None = ""):
    forwarded_host = request.headers.get("x-forwarded-host") or request.headers.get("x-original-host")
    forwarded_proto = request.headers.get("x-forwarded-proto", "https")
    base_url_env = os.getenv("BASE_URL", "").rstrip("/")
    if forwarded_host:
        base_url = f"{forwarded_proto}://{forwarded_host}"
    elif base_url_env:
        base_url = base_url_env
    else:
        base_url = str(request.base_url).rstrip("/")
    
    # Debug log for OAuth server requests
    debug_log(f">>> [DEBUG] OAuth Server requested. Host: {forwarded_host}, Proto: {forwarded_proto}, Base: {base_url}")
    return {
        "issuer": base_url,
        "authorization_endpoint": f"{base_url}/authorize",
        "token_endpoint": f"{base_url}/token",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
        "scopes_supported": ["openid", "mcp", "claudeai"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["RS256"],
        "userinfo_endpoint": f"{base_url}/userinfo"
    }

@router.get("/.well-known/openid-configuration")
async def openid_configuration_combined(request: Request):
    return await oauth_authorization_server(request)

@router.get("/.well-known/mcp-server")
async def mcp_server_discovery(request: Request):
    forwarded_host = request.headers.get("x-forwarded-host") or request.headers.get("x-original-host")
    forwarded_proto = request.headers.get("x-forwarded-proto", "https")
    base_url_env = os.getenv("BASE_URL", "").rstrip("/")
    if forwarded_host:
        base_url = f"{forwarded_proto}://{forwarded_host}"
    elif base_url_env:
        base_url = base_url_env
    else:
        base_url = str(request.base_url).rstrip("/")
    
    return {
        "mcp-version": "1.0",
        "name": "marrow_server",
        "description": "Task Management MCP with Project-based Artifacts",
        "endpoints": {
            "sse": f"{base_url}/mcp",
            "messages": f"{base_url}/messages"
        }
    }

@router.get("/.well-known/oauth-protected-resource")
@router.get("/.well-known/oauth-protected-resource/{path:path}")
async def oauth_protected_resource(request: Request, path: str | None = ""):
    forwarded_host = request.headers.get("x-forwarded-host") or request.headers.get("x-original-host")
    forwarded_proto = request.headers.get("x-forwarded-proto", "https")
    base_url_env = os.getenv("BASE_URL", "").rstrip("/")
    if forwarded_host:
        base_url = f"{forwarded_proto}://{forwarded_host}"
    elif base_url_env:
        base_url = base_url_env
    else:
        base_url = str(request.base_url).rstrip("/")
    
    resource_url = f"{base_url}/{path}" if path else base_url
    
    return {
        "resource": resource_url,
        "authorization_servers": [base_url],
        "bearer_methods_supported": ["header"],
        "scopes_supported": ["openid", "mcp"]
    }

@router.post("/register")
async def register_client(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    client_id = body.get("client_id") or secrets.token_urlsafe(12)
    return JSONResponse({
        "client_id": client_id,
        "client_name": body.get("client_name", "Unknown"),
        "redirect_uris": body.get("redirect_uris", []),
        "grant_types": ["authorization_code"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }, status_code=201)

@router.get("/authorize", response_class=HTMLResponse)
async def authorize(state: str, redirect_uri: str, client_id: str, code_challenge: str):
    html = f"""<html><body><form method='POST' action='/authorize_confirm'>
    <input type='hidden' name='state' value='{state}'>
    <input type='hidden' name='redirect_uri' value='{redirect_uri}'>
    <input type='hidden' name='client_id' value='{client_id}'>
    <input type='hidden' name='code_challenge' value='{code_challenge}'>
    <button type='submit'>Allow Access</button></form></body></html>"""
    return HTMLResponse(html)

@router.post("/authorize_confirm")
async def authorize_confirm(state: str = Form(...), redirect_uri: str = Form(...), client_id: str = Form(...), code_challenge: str = Form(...)):
    code = secrets.token_urlsafe(32)
    _auth_codes[code] = {"code_challenge": code_challenge, "redirect_uri": redirect_uri}
    params = urlencode({"code": code, "state": state})
    return RedirectResponse(url=f"{redirect_uri}?{params}", status_code=302)

@router.post("/token")
async def token(request: Request):
    data = await request.form()
    code = data.get("code")
    code_verifier = data.get("code_verifier", "")
    stored = _auth_codes.pop(code, None)
    if not stored:
        return JSONResponse({"error": "invalid_grant"}, status_code=400)
    
    digest = hashlib.sha256(code_verifier.encode()).digest()
    computed_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    if computed_challenge != stored["code_challenge"]:
        return JSONResponse({"error": "pkce_failed"}, status_code=400)
    
    return JSONResponse({
        "access_token": SECRET_TOKEN,
        "token_type": "bearer",
        "expires_in": 3600 * 24 * 365,
        "scope": "claudeai mcp openid"
    })

@router.get("/userinfo")
async def userinfo(request: Request):
    return {"sub": "mcp-user", "name": "MCP User"}

@router.get("/health")
async def health_check(): return {"status": "ok"}
