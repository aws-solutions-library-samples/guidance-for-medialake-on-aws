"""Generic REST API adapter for metadata sources.

This module implements a generic REST API adapter for fetching metadata from
external systems. It supports configurable endpoint patterns, multiple response
formats (JSON and XML), and delegates authentication to the injected AuthStrategy.
"""

from typing import Any, Final, override
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests
import xmltodict

# Support both pytest imports (package-qualified) and Lambda runtime (absolute)
try:
    from nodes.external_metadata_fetch.adapters.base import (
        AdapterConfig,
        FetchResult,
        MetadataAdapter,
    )
    from nodes.external_metadata_fetch.auth.base import AuthResult, AuthStrategy
except ImportError:
    from adapters.base import AdapterConfig, FetchResult, MetadataAdapter
    from auth.base import AuthResult, AuthStrategy


class GenericRestAdapter(MetadataAdapter):
    """Generic REST API adapter for metadata sources.

    Supports configurable endpoint patterns for metadata retrieval with
    both JSON and XML response formats. Authentication is handled by the
    injected AuthStrategy, allowing this adapter to work with OAuth2,
    API Key, Basic Auth, or any other auth type without modification.

    Response Format Support:
        - JSON: Standard JSON responses (default)
        - XML: XML responses are converted to dictionaries using xmltodict
        - Auto: Automatically detects format from Content-Type header

    XML Conversion Notes:
        When parsing XML responses, the following conventions apply:
        - Element names become dictionary keys
        - XML attributes are prefixed with '@' (e.g., {"@type": "value"})
        - Text content with attributes uses '#text' key
        - Repeated elements become lists automatically

    Example:
        >>> from lambdas.nodes.external_metadata_fetch.auth import (
        ...     OAuth2ClientCredentialsStrategy,
        ...     AuthConfig,
        ... )
        >>> auth_config = AuthConfig(auth_endpoint_url="https://auth.example.com/token")
        >>> auth_strategy = OAuth2ClientCredentialsStrategy(auth_config)
        >>> adapter_config = AdapterConfig(
        ...     metadata_endpoint="https://api.example.com/assets",
        ...     additional_config={
        ...         "correlation_id_param": "externalId",
        ...         "http_method": "GET",
        ...         "timeout_seconds": 30,
        ...         "response_format": "xml"  # or "json" or "auto"
        ...     }
        ... )
        >>> adapter = GenericRestAdapter(adapter_config, auth_strategy)
        >>> auth_result = auth_strategy.authenticate(credentials)
        >>> fetch_result = adapter.fetch_metadata("ABC123", auth_result)
    """

    # Default timeout for HTTP requests in seconds
    DEFAULT_TIMEOUT_SECONDS: Final[int] = 30
    # Default query parameter name for correlation ID
    DEFAULT_CORRELATION_ID_PARAM: Final[str] = "assetId"
    # Default HTTP method
    DEFAULT_HTTP_METHOD: Final[str] = "GET"
    # Supported HTTP methods
    SUPPORTED_HTTP_METHODS: Final[frozenset[str]] = frozenset({"GET", "POST"})
    # Supported response formats
    RESPONSE_FORMAT_JSON: Final[str] = "json"
    RESPONSE_FORMAT_XML: Final[str] = "xml"
    RESPONSE_FORMAT_AUTO: Final[str] = "auto"
    SUPPORTED_RESPONSE_FORMATS: Final[frozenset[str]] = frozenset(
        {RESPONSE_FORMAT_JSON, RESPONSE_FORMAT_XML, RESPONSE_FORMAT_AUTO}
    )

    def __init__(self, config: AdapterConfig, auth_strategy: AuthStrategy):
        """Initialize the Generic REST adapter.

        Args:
            config: Adapter configuration. The additional_config dict may contain:
                - correlation_id_param (str): Query/body parameter name for correlation ID
                  (default: "assetId")
                - http_method (str): HTTP method to use - "GET" or "POST" (default: "GET")
                - timeout_seconds (int): HTTP request timeout (default: 30)
                - additional_headers (dict): Extra headers to include in requests (optional)
                - response_metadata_path (str): Path to metadata in response using dot notation
                  (e.g., "data.metadata") (optional)
                - response_format (str): Expected response format - "json", "xml", or "auto"
                  (default: "auto" - detects from Content-Type header)
            auth_strategy: Authentication strategy to use for API calls
        """
        super().__init__(config, auth_strategy)
        additional: dict[str, Any] = config.additional_config or {}

        self.timeout: int = additional.get(
            "timeout_seconds", self.DEFAULT_TIMEOUT_SECONDS
        )
        self.correlation_id_param: str = additional.get(
            "correlation_id_param", self.DEFAULT_CORRELATION_ID_PARAM
        )
        self.http_method: str = str(
            additional.get("http_method", self.DEFAULT_HTTP_METHOD)
        ).upper()
        self.additional_headers: dict[str, str] = additional.get(
            "additional_headers", {}
        )
        self.response_metadata_path: str | None = additional.get(
            "response_metadata_path"
        )

        # Response format configuration
        response_format: str = str(
            additional.get("response_format", self.RESPONSE_FORMAT_AUTO)
        ).lower()
        if response_format not in self.SUPPORTED_RESPONSE_FORMATS:
            response_format = self.RESPONSE_FORMAT_AUTO
        self.response_format: str = response_format

        # Validate HTTP method
        if self.http_method not in self.SUPPORTED_HTTP_METHODS:
            self.http_method = self.DEFAULT_HTTP_METHOD

    @override
    def fetch_metadata(
        self,
        correlation_id: str,
        auth_result: AuthResult,
        credential_headers: dict[str, str] | None = None,
    ) -> FetchResult:
        """Fetch metadata via REST API.

        Uses the auth_result from the injected AuthStrategy to build
        authorization headers. Supports any auth type that provides headers.

        Args:
            correlation_id: The external system's identifier for the asset
            auth_result: Valid authentication result from auth_strategy.authenticate()
            credential_headers: Optional additional headers from credentials secret.
                               These are merged with config-based headers, with credential
                               headers taking precedence. Useful for API keys or subscription
                               keys that should be stored securely in Secrets Manager.

        Returns:
            FetchResult containing raw metadata or error information
        """
        # Validate inputs
        if not correlation_id or not correlation_id.strip():
            return FetchResult(
                success=False,
                error_message="Correlation ID is required and cannot be empty",
            )

        if not auth_result.success or not auth_result.access_token:
            return FetchResult(
                success=False,
                error_message="Valid authentication result with access token is required",
            )

        # Build headers from auth strategy
        headers: dict[str, str] = self.auth_strategy.get_auth_header(auth_result)

        # Add any additional configured headers (from adapter config)
        if self.additional_headers:
            headers.update(self.additional_headers)

        # Add credential-based headers (from secrets, takes precedence)
        if credential_headers:
            headers.update(credential_headers)

        try:
            if self.http_method == "GET":
                return self._fetch_with_get(correlation_id, headers, auth_result)
            else:  # POST
                return self._fetch_with_post(correlation_id, headers)

        except requests.exceptions.Timeout:
            return FetchResult(
                success=False,
                error_message=f"Metadata fetch timed out after {self.timeout} seconds",
            )
        except requests.exceptions.ConnectionError as e:
            return FetchResult(
                success=False,
                error_message=f"Metadata fetch failed: connection error - {str(e)}",
            )
        except requests.exceptions.RequestException as e:
            return FetchResult(
                success=False,
                error_message=f"Metadata fetch failed: {str(e)}",
            )

    def _fetch_with_get(
        self,
        correlation_id: str,
        headers: dict[str, str],
        auth_result: AuthResult | None = None,
    ) -> FetchResult:
        """Fetch metadata using HTTP GET with correlation ID as query parameter.

        Args:
            correlation_id: The external system's identifier for the asset
            headers: HTTP headers including authorization
            auth_result: Optional auth result for strategies that use query params

        Returns:
            FetchResult containing raw metadata or error information
        """
        # Build URL with correlation ID as query parameter
        url = self._build_url_with_query_param(correlation_id)

        # Add query params from auth strategy if applicable (e.g., API key in query)
        # Some auth strategies (like APIKeyStrategy) support query param authentication
        if auth_result:
            get_query_params_method = getattr(
                self.auth_strategy, "get_query_params", None
            )
            if callable(get_query_params_method):
                auth_query_params = get_query_params_method(auth_result)
                if auth_query_params and isinstance(auth_query_params, dict):
                    url = self._append_query_params(url, auth_query_params)

        response = requests.get(url, headers=headers, timeout=self.timeout)
        return self._process_response(response, correlation_id)

    def _fetch_with_post(
        self, correlation_id: str, headers: dict[str, str]
    ) -> FetchResult:
        """Fetch metadata using HTTP POST with correlation ID in request body.

        Args:
            correlation_id: The external system's identifier for the asset
            headers: HTTP headers including authorization

        Returns:
            FetchResult containing raw metadata or error information
        """
        # Set content type for JSON body
        headers["Content-Type"] = "application/json"

        # Build request body with correlation ID
        body: dict[str, str] = {self.correlation_id_param: correlation_id}

        response = requests.post(
            self.config.metadata_endpoint,
            headers=headers,
            json=body,
            timeout=self.timeout,
        )
        return self._process_response(response, correlation_id)

    def _build_url_with_query_param(self, correlation_id: str) -> str:
        """Build URL with correlation ID as query parameter.

        Handles URLs that may already have query parameters.

        Args:
            correlation_id: The external system's identifier for the asset

        Returns:
            Complete URL with correlation ID query parameter
        """
        parsed = urlparse(self.config.metadata_endpoint)
        existing_params = parse_qs(parsed.query)

        # Add correlation ID parameter
        existing_params[self.correlation_id_param] = [correlation_id]

        # Rebuild query string
        new_query = urlencode(existing_params, doseq=True)

        # Reconstruct URL
        new_parsed = parsed._replace(query=new_query)
        return urlunparse(new_parsed)

    def _append_query_params(self, url: str, params: dict[str, Any]) -> str:
        """Append additional query parameters to a URL.

        Args:
            url: Base URL (may already have query parameters)
            params: Additional query parameters to append

        Returns:
            URL with appended query parameters
        """
        parsed = urlparse(url)
        existing_params = parse_qs(parsed.query)

        # Add new parameters
        for key, value in params.items():
            existing_params[key] = [str(value)]

        # Rebuild query string
        new_query = urlencode(existing_params, doseq=True)

        # Reconstruct URL
        new_parsed = parsed._replace(query=new_query)
        return urlunparse(new_parsed)

    def _process_response(
        self, response: requests.Response, correlation_id: str
    ) -> FetchResult:
        """Process the HTTP response and extract metadata.

        Supports both JSON and XML response formats. The format is determined by:
        1. Explicit `response_format` configuration ("json" or "xml")
        2. Auto-detection from Content-Type header (if response_format is "auto")

        Args:
            response: HTTP response from the metadata API
            correlation_id: The correlation ID used in the request (for error messages)

        Returns:
            FetchResult containing raw metadata or error information
        """
        # Handle 404 - asset not found
        if response.status_code == 404:
            return FetchResult(
                success=False,
                error_message=f"Asset not found in external system: {correlation_id}",
                http_status_code=404,
            )

        # Handle other error status codes
        if not response.ok:
            error_detail = self._extract_error_detail(response)
            return FetchResult(
                success=False,
                error_message=f"Metadata fetch failed with status {response.status_code}: {error_detail}",
                http_status_code=response.status_code,
            )

        # Determine response format
        detected_format = self._detect_response_format(response)

        # Parse response based on format
        try:
            # Check for empty response before parsing
            text = response.text.strip() if response.text else ""
            if not text:
                return FetchResult(
                    success=False,
                    error_message=f"Empty response from API for correlation ID: {correlation_id}",
                    http_status_code=response.status_code,
                )

            # For XML, check if it's just a declaration with no content
            if detected_format == self.RESPONSE_FORMAT_XML:
                import re

                # Remove XML declaration and BOM characters
                content_without_declaration = re.sub(
                    r"<\?xml[^?]*\?>", "", text
                ).strip()
                # Also strip BOM (Byte Order Mark) characters
                content_without_declaration = content_without_declaration.strip(
                    "\ufeff\ufffe"
                )
                if not content_without_declaration:
                    return FetchResult(
                        success=False,
                        error_message=f"Empty XML response from API for correlation ID: {correlation_id}",
                        http_status_code=response.status_code,
                    )
                response_data = self._parse_xml_response(response)
            else:
                response_data = self._parse_json_response(response)
        except ValueError as e:
            return FetchResult(
                success=False,
                error_message=f"Metadata fetch failed: {str(e)}",
                http_status_code=response.status_code,
            )

        # Extract metadata from response (optionally using configured path)
        metadata = self._extract_metadata(response_data)

        return FetchResult(
            success=True,
            raw_metadata=metadata,
            http_status_code=response.status_code,
        )

    def _detect_response_format(self, response: requests.Response) -> str:
        """Detect the response format from configuration or Content-Type header.

        Args:
            response: HTTP response to analyze

        Returns:
            Response format string ("json" or "xml")
        """
        # If explicit format is configured, use it
        if self.response_format != self.RESPONSE_FORMAT_AUTO:
            return self.response_format

        # Auto-detect from Content-Type header
        content_type = response.headers.get("Content-Type", "").lower()

        if "xml" in content_type:
            return self.RESPONSE_FORMAT_XML
        elif "json" in content_type:
            return self.RESPONSE_FORMAT_JSON

        # Default to JSON if Content-Type is ambiguous
        # Try to detect from response content
        text = response.text.strip()
        if text.startswith("<?xml") or text.startswith("<"):
            return self.RESPONSE_FORMAT_XML

        return self.RESPONSE_FORMAT_JSON

    def _parse_json_response(self, response: requests.Response) -> dict[str, Any]:
        """Parse a JSON response into a dictionary.

        Args:
            response: HTTP response with JSON body

        Returns:
            Parsed dictionary

        Raises:
            ValueError: If response is not valid JSON
        """
        try:
            return response.json()
        except ValueError:
            # Include response preview in error for debugging
            preview = response.text[:200] if response.text else "(empty)"
            raise ValueError(f"invalid JSON response: {preview}")

    def _parse_xml_response(self, response: requests.Response) -> dict[str, Any]:
        """Parse an XML response into a dictionary using xmltodict.

        The XML is converted to a dictionary structure where:
        - Element names become dictionary keys
        - Attributes are prefixed with '@' (e.g., @type, @order)
        - Text content is stored under '#text' key when mixed with attributes
        - Repeated elements become lists

        Args:
            response: HTTP response with XML body

        Returns:
            Parsed dictionary

        Raises:
            ValueError: If response is not valid XML
        """
        try:
            # Parse XML to dict
            # xmltodict.parse returns OrderedDict, convert to regular dict
            parsed = xmltodict.parse(response.text)
            return dict(parsed) if parsed else {}
        except Exception as e:
            # Include response preview in error for debugging
            preview = response.text[:200] if response.text else "(empty)"
            raise ValueError(f"invalid XML response: {str(e)} - Preview: {preview}")

    def _extract_metadata(self, response_data: dict[str, Any]) -> dict[str, Any]:
        """Extract metadata from response data using optional path.

        If response_metadata_path is configured, navigates to that path
        in the response. Otherwise, returns the entire response.

        Args:
            response_data: Parsed JSON response from the API

        Returns:
            Extracted metadata dictionary
        """
        if not self.response_metadata_path:
            return response_data

        # Navigate to the configured path (supports dot notation like "data.metadata")
        current = response_data
        for key in self.response_metadata_path.split("."):
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                # Path not found, return entire response
                return response_data

        # Ensure we return a dict
        if isinstance(current, dict):
            return current
        return response_data

    def _extract_error_detail(self, response: requests.Response) -> str:
        """Extract error details from a failed response.

        Attempts to parse JSON error response, falls back to raw text.

        Args:
            response: Failed HTTP response

        Returns:
            Human-readable error description
        """
        try:
            error_data: dict[str, Any] = response.json()
            # Common error response patterns
            if "error" in error_data:
                error = error_data["error"]
                if isinstance(error, dict):
                    return error.get("message", str(error))
                return str(error)
            if "message" in error_data:
                return str(error_data["message"])
            if "detail" in error_data:
                return str(error_data["detail"])
            # Return truncated JSON if no standard error field
            return str(error_data)[:200]
        except ValueError:
            # Response is not JSON, return raw text (truncated)
            text = response.text[:200] if response.text else "no response body"
            return text

    @override
    def get_adapter_name(self) -> str:
        """Return the unique name of this adapter.

        Returns:
            "generic_rest_api"
        """
        return "generic_rest_api"
