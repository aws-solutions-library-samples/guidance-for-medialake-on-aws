import re
from typing import Any, Dict


def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    CloudFront Edge Lambda function that:
    1. Strips /*/*/ from the URI
    2. Modifies CSP headers to allow WASM
    3. Forwards to S3 origin
    """

    # Get the request from the event
    request = event["Records"][0]["cf"]["request"]

    # Get the original URI
    original_uri = request["uri"]

    # Strip /*/*/ pattern from URI
    # This removes path segments that match the pattern
    cleaned_uri = re.sub(r"/\*/\*/", "/", original_uri)

    # Update the request URI
    request["uri"] = cleaned_uri

    # Get the response headers (if this is a response event)
    if "response" in event["Records"][0]["cf"]:
        response = event["Records"][0]["cf"]["response"]
        headers = response.get("headers", {})

        # Modify CSP headers to allow WASM
        if "content-security-policy" in headers:
            csp_header = headers["content-security-policy"][0]["value"]

            # Update CSP to allow WASM and blob URLs
            updated_csp = modify_csp_for_wasm(csp_header)

            headers["content-security-policy"] = [
                {"key": "Content-Security-Policy", "value": updated_csp}
            ]

        # Add additional security headers if not present
        add_security_headers(headers)

        return {
            "status": "200",
            "statusDescription": "OK",
            "headers": headers,
            "body": response.get("body", ""),
        }

    # For request events, just return the modified request
    return request


def modify_csp_for_wasm(csp_header: str) -> str:
    """
    Modify CSP header to allow WASM and blob URLs
    """
    # Parse the CSP directive
    directives = {}

    # Split by semicolon and parse each directive
    for directive in csp_header.split(";"):
        directive = directive.strip()
        if not directive:
            continue

        if " " in directive:
            key, values = directive.split(" ", 1)
            directives[key] = values.strip()
        else:
            directives[directive] = ""

    # Update script-src to include wasm-unsafe-eval and blob:
    if "script-src" in directives:
        script_src = directives["script-src"]
        if "wasm-unsafe-eval" not in script_src:
            script_src += " 'wasm-unsafe-eval'"
        if "blob:" not in script_src:
            script_src += " blob:"
        directives["script-src"] = script_src

    # Update connect-src to include data: and blob:
    if "connect-src" in directives:
        connect_src = directives["connect-src"]
        if "data:" not in connect_src:
            connect_src += " data:"
        if "blob:" not in connect_src:
            connect_src += " blob:"
        directives["connect-src"] = connect_src

    # Update img-src to include data:
    if "img-src" in directives:
        img_src = directives["img-src"]
        if "data:" not in img_src:
            img_src += " data:"
        directives["img-src"] = img_src

    # Update font-src to include data:
    if "font-src" in directives:
        font_src = directives["font-src"]
        if "data:" not in font_src:
            font_src += " data:"
        directives["font-src"] = font_src

    # Update media-src to include data:
    if "media-src" in directives:
        media_src = directives["media-src"]
        if "data:" not in media_src:
            media_src += " data:"
        directives["media-src"] = media_src

    # Reconstruct the CSP header
    csp_parts = []
    for key, value in directives.items():
        if value:
            csp_parts.append(f"{key} {value}")
        else:
            csp_parts.append(key)

    return "; ".join(csp_parts)


def add_security_headers(headers: Dict[str, Any]) -> None:
    """
    Add additional security headers if not present
    """
    # Add X-Content-Type-Options if not present
    if "x-content-type-options" not in headers:
        headers["x-content-type-options"] = [
            {"key": "X-Content-Type-Options", "value": "nosniff"}
        ]

    # Add X-Frame-Options if not present
    if "x-frame-options" not in headers:
        headers["x-frame-options"] = [{"key": "X-Frame-Options", "value": "DENY"}]

    # Add Referrer-Policy if not present
    if "referrer-policy" not in headers:
        headers["referrer-policy"] = [
            {"key": "Referrer-Policy", "value": "strict-origin-when-cross-origin"}
        ]
