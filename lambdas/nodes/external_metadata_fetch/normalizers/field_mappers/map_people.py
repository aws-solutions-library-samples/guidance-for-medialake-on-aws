"""Configuration-driven people/credits field mapping for MEC People/Job elements.

This module provides functions to map source system cast and crew fields
to MEC-compliant People/Job elements. All field names are configuration-driven -
NO hardcoded customer-specific values.

The people_field_mappings configuration defines which source fields map to which
MEC JobFunction values. Attribute names for person data (first_name, last_name, etc.)
are also configurable.

Example configuration:
    {
        "people_field_mappings": {
            "actors": "Actor",
            "directors": "Director",
            "writers": "Writer",
            "producers": "Producer",
            "executive_producers": "ExecutiveProducer",
            "series_creators": "Creator",
            "guest_actors": "Actor",
        },
        "guest_actors_field": "guest_actors",
        "person_first_name_attr": "@first_name",
        "person_last_name_attr": "@last_name",
        "person_order_attr": "@order",
        "person_role_attr": "@role",
    }

Reference: MovieLabs MEC v2.25 - People/Job element

IMPORTANT MEC v2.25 Schema Notes:
- DisplayName is REQUIRED in PersonName
- Use FirstGivenName (not FirstName) and FamilyName (not LastName)
- JobFunction is an ELEMENT, not an attribute
- BillingBlockOrder is an ELEMENT, not an attribute
- Guest is a boolean ELEMENT for guest appearances
"""

from typing import Any

# Support both pytest imports (package-qualified) and Lambda runtime (absolute)
try:
    from nodes.external_metadata_fetch.normalizers.mec_schema import Job, PersonName
except ImportError:
    from normalizers.mec_schema import Job, PersonName


# Default role mappings - can be overridden via config
DEFAULT_ROLE_MAPPINGS: dict[str, str] = {
    "actors": "Actor",
    "directors": "Director",
    "writers": "Writer",
    "producers": "Producer",
    "executive_producers": "ExecutiveProducer",
    "series_creators": "Creator",
    "guest_actors": "Actor",  # Will set guest=True
}

# Default attribute names for person data
DEFAULT_FIRST_NAME_ATTR = "@first_name"
DEFAULT_LAST_NAME_ATTR = "@last_name"
DEFAULT_ORDER_ATTR = "@order"
DEFAULT_ROLE_ATTR = "@role"
DEFAULT_GUEST_ACTORS_FIELD = "guest_actors"


def get_person_attribute(
    person_data: dict[str, Any],
    attr_name: str,
) -> str | None:
    """Extract an attribute value from person data.

    Handles both @ prefixed attributes (XML style) and plain attribute names.

    Args:
        person_data: Dictionary containing person attributes.
        attr_name: Attribute name to extract (e.g., "@first_name" or "first_name").

    Returns:
        The attribute value as string, or None if not found/empty.
    """
    if not person_data or not attr_name:
        return None

    value = person_data.get(attr_name)

    if value is None:
        return None

    # Convert to string if needed
    if not isinstance(value, str):
        value = str(value)

    # Return None for empty/whitespace-only strings
    stripped = value.strip()
    return stripped if stripped else None


def build_display_name(
    person_data: dict[str, Any],
    first_name_attr: str,
    last_name_attr: str,
) -> str:
    """Build the display name from person data.

    DisplayName is REQUIRED by MEC v2.25 schema. This function constructs
    the display name from available data:
    1. Use #text if available (full name from XML text content)
    2. Construct from first_name + last_name
    3. Use "Unknown" as fallback

    Args:
        person_data: Dictionary containing person attributes.
        first_name_attr: Config attribute name for first name.
        last_name_attr: Config attribute name for last name.

    Returns:
        Display name string (never empty - REQUIRED by MEC).
    """
    # First try to get full name from text content
    full_name = person_data.get("#text")
    if full_name and isinstance(full_name, str) and full_name.strip():
        return full_name.strip()

    # Construct from first and last name
    first = get_person_attribute(person_data, first_name_attr) or ""
    last = get_person_attribute(person_data, last_name_attr) or ""

    constructed = f"{first} {last}".strip()
    if constructed:
        return constructed

    # Fallback - DisplayName is REQUIRED
    return "Unknown"


def map_person(
    person_data: dict[str, Any],
    job_function: str,
    config: dict[str, Any],
    is_guest: bool = False,
) -> Job:
    """Map a single person entry to MEC Job element.

    IMPORTANT MEC v2.25 Schema Notes:
    - DisplayName is REQUIRED in PersonName
    - Use FirstGivenName (not FirstName) and FamilyName (not LastName)
    - JobFunction is an ELEMENT, not an attribute
    - BillingBlockOrder is an ELEMENT, not an attribute
    - Guest is a boolean ELEMENT for guest appearances

    Args:
        person_data: Dictionary containing person attributes from source.
        job_function: MEC JobFunction value (Actor, Director, Writer, etc.).
        config: Configuration dictionary with attribute name mappings.
        is_guest: Whether this is a guest appearance (sets Guest element).

    Returns:
        Job element with mapped person data.

    Example:
        >>> person = {
        ...     "#text": "John Actor",
        ...     "@first_name": "John",
        ...     "@last_name": "Actor",
        ...     "@order": "1",
        ...     "@role": "Main Character"
        ... }
        >>> config = {
        ...     "person_first_name_attr": "@first_name",
        ...     "person_last_name_attr": "@last_name",
        ...     "person_order_attr": "@order",
        ...     "person_role_attr": "@role",
        ... }
        >>> job = map_person(person, "Actor", config)
        >>> job.name.display_name
        'John Actor'
    """
    # Get attribute name mappings from config (with defaults)
    first_name_attr = config.get("person_first_name_attr", DEFAULT_FIRST_NAME_ATTR)
    last_name_attr = config.get("person_last_name_attr", DEFAULT_LAST_NAME_ATTR)
    order_attr = config.get("person_order_attr", DEFAULT_ORDER_ATTR)
    role_attr = config.get("person_role_attr", DEFAULT_ROLE_ATTR)

    # Build display name (REQUIRED by MEC v2.25)
    display_name = build_display_name(person_data, first_name_attr, last_name_attr)

    # Create PersonName structure
    name = PersonName(
        display_name=display_name,
        first_given_name=get_person_attribute(person_data, first_name_attr),
        family_name=get_person_attribute(person_data, last_name_attr),
    )

    # Extract billing order (BillingBlockOrder ELEMENT, not attribute)
    billing_block_order: int | None = None
    order_value = get_person_attribute(person_data, order_attr)
    if order_value:
        try:
            billing_block_order = int(order_value)
        except (ValueError, TypeError):
            pass

    # Extract character for actors
    character: str | None = None
    if job_function == "Actor":
        character = get_person_attribute(person_data, role_attr)

    # Create Job element
    return Job(
        job_function=job_function,
        name=name,
        billing_block_order=billing_block_order,
        character=character,
        guest=True if is_guest else None,
    )


def normalize_people_list(people_data: Any) -> list[dict[str, Any]]:
    """Normalize people data to a list of dictionaries.

    Handles various input formats:
    - Single dict (one person)
    - List of dicts (multiple people)
    - None or empty

    Args:
        people_data: Raw people data from source (dict, list, or None).

    Returns:
        List of person dictionaries.
    """
    if people_data is None:
        return []

    if isinstance(people_data, dict):
        return [people_data]

    if isinstance(people_data, list):
        return [p for p in people_data if p and isinstance(p, dict)]

    return []


def map_people_list(
    raw_metadata: dict[str, Any],
    field_name: str,
    job_function: str,
    config: dict[str, Any],
) -> list[Job]:
    """Map a list of people from a specific field to Job elements.

    Handles nested XML structures where people are in a container element
    with singular child elements (e.g., actors/actor, directors/director).

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        field_name: The field name containing people (e.g., "actors").
        job_function: MEC JobFunction value for these people.
        config: Configuration dictionary with attribute name mappings.

    Returns:
        List of Job elements for all people in the field.

    Example:
        >>> raw = {
        ...     "actors": {
        ...         "actor": [
        ...             {"#text": "John Actor", "@order": "1"},
        ...             {"#text": "Jane Actress", "@order": "2"},
        ...         ]
        ...     }
        ... }
        >>> config = {"guest_actors_field": "guest_actors"}
        >>> jobs = map_people_list(raw, "actors", "Actor", config)
        >>> len(jobs)
        2
    """
    # Get the container element
    container = raw_metadata.get(field_name)
    if container is None:
        return []

    # Handle direct list (no container)
    if isinstance(container, list):
        people_list = normalize_people_list(container)
    elif isinstance(container, dict):
        # Try to get singular child element (actors -> actor)
        singular = field_name.rstrip("s")
        if singular in container:
            people_list = normalize_people_list(container[singular])
        else:
            # Container might be the person data itself
            people_list = normalize_people_list(container)
    else:
        return []

    # Check if this is a guest actors field
    guest_field = config.get("guest_actors_field", DEFAULT_GUEST_ACTORS_FIELD)
    is_guest = field_name == guest_field

    # Map each person
    return [
        map_person(person, job_function, config, is_guest)
        for person in people_list
        if person
    ]


def map_all_people(
    raw_metadata: dict[str, Any],
    config: dict[str, Any],
) -> list[Job]:
    """Map all people fields from source metadata using configuration.

    This function iterates through the people_field_mappings configuration
    and extracts matching fields from the raw metadata, converting them to
    MEC-compliant Job elements.

    NO hardcoded field names - all field names come from config["people_field_mappings"].

    Args:
        raw_metadata: Raw metadata dictionary from the source system.
        config: Configuration dictionary containing:
            - people_field_mappings: Dict mapping field names to JobFunction values
            - guest_actors_field: Field name for guest actors (sets Guest=true)
            - person_first_name_attr: Attribute name for first name
            - person_last_name_attr: Attribute name for last name
            - person_order_attr: Attribute name for billing order
            - person_role_attr: Attribute name for character/role

    Returns:
        List of Job elements for all people, sorted by billing order and function.

    Example config:
        {
            "people_field_mappings": {
                "actors": "Actor",
                "directors": "Director",
                "writers": "Writer",
                "producers": "Producer",
                "executive_producers": "ExecutiveProducer",
                "series_creators": "Creator",
                "guest_actors": "Actor",
            },
            "guest_actors_field": "guest_actors",
            "person_first_name_attr": "@first_name",
            "person_last_name_attr": "@last_name",
            "person_order_attr": "@order",
            "person_role_attr": "@role",
        }

    Example usage:
        >>> raw = {
        ...     "actors": {"actor": [{"#text": "John Actor", "@order": "1"}]},
        ...     "directors": {"director": [{"#text": "Jane Director"}]},
        ... }
        >>> config = {
        ...     "people_field_mappings": {
        ...         "actors": "Actor",
        ...         "directors": "Director",
        ...     }
        ... }
        >>> people = map_all_people(raw, config)
        >>> len(people)
        2
    """
    all_people: list[Job] = []

    # Get role mappings from config or use defaults
    role_mappings = config.get("people_field_mappings", DEFAULT_ROLE_MAPPINGS)

    # Process each configured people field
    for field_name, job_function in role_mappings.items():
        people = map_people_list(raw_metadata, field_name, job_function, config)
        all_people.extend(people)

    # Sort by billing order (None values last) then by job function
    all_people.sort(
        key=lambda j: (
            j.billing_block_order if j.billing_block_order is not None else 999999,
            j.job_function,
        )
    )

    return all_people
