"""Field mapper modules for MEC-compliant metadata normalization.

This package contains modular mapping functions for each field category.
All mappers are configuration-driven - they receive configuration dictionaries
that specify customer-specific field names and mappings.

Modules:
    map_identifiers: AltIdentifier mapping (config-driven)
    map_titles: LocalizedInfo (titles, descriptions)
    map_classifications: WorkType, genres
    map_hierarchy: SequenceInfo, Parent relationships
    map_people: People/Job mapping
    map_ratings: RatingSet mapping
    map_technical: DigitalAsset attributes
    extract_custom_fields: Unmapped field extraction
"""

__all__ = [
    "map_identifiers",
    "map_titles",
    "map_classifications",
    "map_hierarchy",
    "map_people",
    "map_ratings",
    "map_technical",
    "extract_custom_fields",
]
