import ipaddress
import socket
from urllib.parse import urlparse
import httpx

class SSRFViolationError(ValueError):
    """Raised when a URL resolves to a forbidden internal or private IP address."""
    pass

def validate_public_url(url: str) -> str:
    """
    Validates a URL against Server-Side Request Forgery attacks.
    - Requires http/https
    - Resolves DNS
    - Rejects private, loopback, link-local, multicast, and 0.0.0.0/8 IPs.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise SSRFViolationError(f"Forbidden URL scheme: {parsed.scheme}")
    
    hostname = parsed.hostname
    if not hostname:
        raise SSRFViolationError("URL missing hostname")
        
    try:
        # Resolve hostname to all IPv4/IPv6 addresses
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror as e:
        raise SSRFViolationError(f"DNS resolution failed for {hostname}: {e}")
        
    for res in addr_info:
        ip_str = res[4][0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
            
        if (
            ip_obj.is_private or
            ip_obj.is_loopback or
            ip_obj.is_link_local or
            ip_obj.is_multicast or
            ip_obj.is_reserved or
            # Explicitly block 0.0.0.0/8 which some OSes route to loopback
            (ip_obj.version == 4 and ip_str.startswith("0."))
        ):
            raise SSRFViolationError(f"URL hostname resolves to restricted IP range: {ip_str}")
            
    return url

async def _verify_request(request: httpx.Request):
    """Event hook to validate public URLs on every outbound request (including redirects)."""
    validate_public_url(str(request.url))

def get_safe_client(**kwargs) -> httpx.AsyncClient:
    """
    Returns an httpx.AsyncClient configured to abort on SSRF violations.
    Includes an event hook that verifies the URL of every request, natively protecting against DNS rebinding via redirects.
    """
    # Ensure our safety hook runs before any request is dispatched
    event_hooks = kwargs.get("event_hooks", {})
    request_hooks = event_hooks.get("request", [])
    request_hooks.append(_verify_request)
    event_hooks["request"] = request_hooks
    kwargs["event_hooks"] = event_hooks
    
    return httpx.AsyncClient(**kwargs)

