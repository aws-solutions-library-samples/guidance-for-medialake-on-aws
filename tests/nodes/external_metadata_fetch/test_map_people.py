"""
Unit tests for the people/credits field mapper module.

These tests verify that:
- map_person() correctly creates Job elements with PersonName
- Each role type maps to correct JobFunction using config
- Name parsing works with configurable attribute names
- Billing order is preserved
- Character name mapping works for actors
- Guest flag is set correctly for guest actors

⚠️ GENERIC NAMING: Uses generic names like "John Actor", "Jane Director".
Do NOT use real celebrity names or customer-specific cast data.
"""

import pytest
from nodes.external_metadata_fetch.normalizers.field_mappers.map_people import (
    DEFAULT_ROLE_MAPPINGS,
    build_display_name,
    get_person_attribute,
    map_all_people,
    map_people_list,
    map_person,
    normalize_people_list,
)
from nodes.external_metadata_fetch.normalizers.mec_schema import Job, PersonName


@pytest.mark.unit
class TestGetPersonAttribute:
    """Tests for get_person_attribute function"""

    def test_extracts_attribute_value(self):
        """Extracts attribute value from person data."""
        person = {"@first_name": "John"}
        result = get_person_attribute(person, "@first_name")
        assert result == "John"

    def test_returns_none_for_missing_attribute(self):
        """Returns None when attribute is missing."""
        person = {"@first_name": "John"}
        result = get_person_attribute(person, "@last_name")
        assert result is None

    def test_returns_none_for_empty_string(self):
        """Returns None when attribute is empty string."""
        person = {"@first_name": ""}
        result = get_person_attribute(person, "@first_name")
        assert result is None

    def test_returns_none_for_whitespace_only(self):
        """Returns None when attribute is whitespace only."""
        person = {"@first_name": "   "}
        result = get_person_attribute(person, "@first_name")
        assert result is None

    def test_strips_whitespace(self):
        """Strips leading/trailing whitespace from value."""
        person = {"@first_name": "  John  "}
        result = get_person_attribute(person, "@first_name")
        assert result == "John"

    def test_handles_none_person_data(self):
        """Returns None when person data is None."""
        result = get_person_attribute(None, "@first_name")
        assert result is None

    def test_handles_none_attr_name(self):
        """Returns None when attribute name is None."""
        person = {"@first_name": "John"}
        result = get_person_attribute(person, None)
        assert result is None

    def test_converts_non_string_to_string(self):
        """Converts non-string values to string."""
        person = {"@order": 1}
        result = get_person_attribute(person, "@order")
        assert result == "1"


@pytest.mark.unit
class TestBuildDisplayName:
    """Tests for build_display_name function"""

    def test_uses_text_content_when_available(self):
        """Uses #text content as display name when available."""
        person = {
            "#text": "John Actor",
            "@first_name": "John",
            "@last_name": "Actor",
        }
        result = build_display_name(person, "@first_name", "@last_name")
        assert result == "John Actor"

    def test_constructs_from_first_and_last_name(self):
        """Constructs display name from first and last name."""
        person = {
            "@first_name": "John",
            "@last_name": "Actor",
        }
        result = build_display_name(person, "@first_name", "@last_name")
        assert result == "John Actor"

    def test_uses_first_name_only_when_no_last(self):
        """Uses first name only when last name is missing."""
        person = {"@first_name": "John"}
        result = build_display_name(person, "@first_name", "@last_name")
        assert result == "John"

    def test_uses_last_name_only_when_no_first(self):
        """Uses last name only when first name is missing."""
        person = {"@last_name": "Actor"}
        result = build_display_name(person, "@first_name", "@last_name")
        assert result == "Actor"

    def test_returns_unknown_when_no_name_data(self):
        """Returns 'Unknown' when no name data available."""
        person = {}
        result = build_display_name(person, "@first_name", "@last_name")
        assert result == "Unknown"

    def test_strips_whitespace_from_text(self):
        """Strips whitespace from #text content."""
        person = {"#text": "  John Actor  "}
        result = build_display_name(person, "@first_name", "@last_name")
        assert result == "John Actor"

    def test_ignores_empty_text_content(self):
        """Ignores empty #text and falls back to name parts."""
        person = {
            "#text": "",
            "@first_name": "John",
            "@last_name": "Actor",
        }
        result = build_display_name(person, "@first_name", "@last_name")
        assert result == "John Actor"


@pytest.mark.unit
class TestNormalizePeopleList:
    """Tests for normalize_people_list function"""

    def test_returns_empty_list_for_none(self):
        """Returns empty list when input is None."""
        result = normalize_people_list(None)
        assert result == []

    def test_wraps_single_dict_in_list(self):
        """Wraps single dict in a list."""
        person = {"#text": "John Actor"}
        result = normalize_people_list(person)
        assert result == [person]

    def test_returns_list_as_is(self):
        """Returns list of dicts as-is."""
        people = [{"#text": "John Actor"}, {"#text": "Jane Actress"}]
        result = normalize_people_list(people)
        assert result == people

    def test_filters_none_from_list(self):
        """Filters None values from list."""
        people = [{"#text": "John Actor"}, None, {"#text": "Jane Actress"}]
        result = normalize_people_list(people)
        assert len(result) == 2

    def test_filters_non_dict_from_list(self):
        """Filters non-dict values from list."""
        people = [{"#text": "John Actor"}, "invalid", {"#text": "Jane Actress"}]
        result = normalize_people_list(people)
        assert len(result) == 2


@pytest.mark.unit
class TestMapPerson:
    """Tests for map_person function"""

    def test_creates_job_with_actor_function(self):
        """Creates Job element with Actor function."""
        person = {"#text": "John Actor", "@order": "1"}
        config = {}

        result = map_person(person, "Actor", config)

        assert isinstance(result, Job)
        assert result.job_function == "Actor"
        assert result.name.display_name == "John Actor"

    def test_creates_job_with_director_function(self):
        """Creates Job element with Director function."""
        person = {"#text": "Jane Director"}
        config = {}

        result = map_person(person, "Director", config)

        assert result.job_function == "Director"
        assert result.name.display_name == "Jane Director"

    def test_maps_billing_block_order(self):
        """Maps billing order to BillingBlockOrder element."""
        person = {"#text": "John Actor", "@order": "1"}
        config = {"person_order_attr": "@order"}

        result = map_person(person, "Actor", config)

        assert result.billing_block_order == 1

    def test_maps_character_for_actors(self):
        """Maps role to Character element for actors."""
        person = {
            "#text": "John Actor",
            "@role": "Main Character",
        }
        config = {"person_role_attr": "@role"}

        result = map_person(person, "Actor", config)

        assert result.character == "Main Character"

    def test_does_not_map_character_for_non_actors(self):
        """Does not map role to Character for non-actors."""
        person = {
            "#text": "Jane Director",
            "@role": "Some Role",
        }
        config = {"person_role_attr": "@role"}

        result = map_person(person, "Director", config)

        assert result.character is None

    def test_sets_guest_flag_when_is_guest_true(self):
        """Sets Guest element to True for guest actors."""
        person = {"#text": "Guest Star"}
        config = {}

        result = map_person(person, "Actor", config, is_guest=True)

        assert result.guest is True

    def test_guest_flag_none_when_not_guest(self):
        """Guest element is None for non-guest actors."""
        person = {"#text": "Regular Actor"}
        config = {}

        result = map_person(person, "Actor", config, is_guest=False)

        assert result.guest is None

    def test_uses_configurable_attribute_names(self):
        """Uses configurable attribute names for person data."""
        person = {
            "first": "John",
            "last": "Actor",
            "billing": "2",
            "character_name": "Hero",
        }
        config = {
            "person_first_name_attr": "first",
            "person_last_name_attr": "last",
            "person_order_attr": "billing",
            "person_role_attr": "character_name",
        }

        result = map_person(person, "Actor", config)

        assert result.name.display_name == "John Actor"
        assert result.name.first_given_name == "John"
        assert result.name.family_name == "Actor"
        assert result.billing_block_order == 2
        assert result.character == "Hero"

    def test_handles_invalid_billing_order(self):
        """Handles non-numeric billing order gracefully."""
        person = {"#text": "John Actor", "@order": "invalid"}
        config = {"person_order_attr": "@order"}

        result = map_person(person, "Actor", config)

        assert result.billing_block_order is None

    def test_person_name_structure(self):
        """Verifies PersonName structure follows MEC schema."""
        person = {
            "@first_name": "John",
            "@last_name": "Actor",
        }
        config = {
            "person_first_name_attr": "@first_name",
            "person_last_name_attr": "@last_name",
        }

        result = map_person(person, "Actor", config)

        assert isinstance(result.name, PersonName)
        assert result.name.display_name == "John Actor"
        assert result.name.first_given_name == "John"
        assert result.name.family_name == "Actor"


@pytest.mark.unit
class TestMapPeopleList:
    """Tests for map_people_list function"""

    def test_maps_nested_actor_list(self):
        """Maps nested actors/actor structure."""
        raw = {
            "actors": {
                "actor": [
                    {"#text": "John Actor", "@order": "1"},
                    {"#text": "Jane Actress", "@order": "2"},
                ]
            }
        }
        config = {"guest_actors_field": "guest_actors"}

        result = map_people_list(raw, "actors", "Actor", config)

        assert len(result) == 2
        assert result[0].name.display_name == "John Actor"
        assert result[1].name.display_name == "Jane Actress"

    def test_maps_single_person_in_container(self):
        """Maps single person (dict instead of list)."""
        raw = {"directors": {"director": {"#text": "Jane Director"}}}
        config = {}

        result = map_people_list(raw, "directors", "Director", config)

        assert len(result) == 1
        assert result[0].name.display_name == "Jane Director"

    def test_returns_empty_for_missing_field(self):
        """Returns empty list when field is missing."""
        raw = {}
        config = {}

        result = map_people_list(raw, "actors", "Actor", config)

        assert result == []

    def test_returns_empty_for_none_field(self):
        """Returns empty list when field is None."""
        raw = {"actors": None}
        config = {}

        result = map_people_list(raw, "actors", "Actor", config)

        assert result == []

    def test_handles_direct_list_without_container(self):
        """Handles direct list without nested container."""
        raw = {
            "writers": [
                {"#text": "Writer One"},
                {"#text": "Writer Two"},
            ]
        }
        config = {}

        result = map_people_list(raw, "writers", "Writer", config)

        assert len(result) == 2

    def test_sets_guest_flag_for_guest_actors_field(self):
        """Sets guest flag for configured guest actors field."""
        raw = {"guest_actors": {"guest_actor": [{"#text": "Guest Star"}]}}
        config = {"guest_actors_field": "guest_actors"}

        result = map_people_list(raw, "guest_actors", "Actor", config)

        assert len(result) == 1
        assert result[0].guest is True

    def test_no_guest_flag_for_regular_actors(self):
        """Does not set guest flag for regular actors."""
        raw = {"actors": {"actor": [{"#text": "Regular Actor"}]}}
        config = {"guest_actors_field": "guest_actors"}

        result = map_people_list(raw, "actors", "Actor", config)

        assert len(result) == 1
        assert result[0].guest is None


@pytest.mark.unit
class TestMapAllPeople:
    """Tests for map_all_people function"""

    def test_maps_all_configured_role_types(self):
        """Maps all role types defined in configuration."""
        raw = {
            "actors": {"actor": [{"#text": "John Actor", "@order": "1"}]},
            "directors": {"director": [{"#text": "Jane Director"}]},
            "writers": {"writer": [{"#text": "Writer Person"}]},
        }
        config = {
            "people_field_mappings": {
                "actors": "Actor",
                "directors": "Director",
                "writers": "Writer",
            }
        }

        result = map_all_people(raw, config)

        assert len(result) == 3
        functions = {j.job_function for j in result}
        assert "Actor" in functions
        assert "Director" in functions
        assert "Writer" in functions

    def test_uses_default_mappings_when_not_configured(self):
        """Uses DEFAULT_ROLE_MAPPINGS when not configured."""
        raw = {
            "actors": {"actor": [{"#text": "John Actor"}]},
            "directors": {"director": [{"#text": "Jane Director"}]},
        }
        config = {}

        result = map_all_people(raw, config)

        assert len(result) == 2

    def test_sorts_by_billing_order(self):
        """Sorts results by billing order."""
        raw = {
            "actors": {
                "actor": [
                    {"#text": "Third Actor", "@order": "3"},
                    {"#text": "First Actor", "@order": "1"},
                    {"#text": "Second Actor", "@order": "2"},
                ]
            }
        }
        config = {
            "people_field_mappings": {"actors": "Actor"},
            "person_order_attr": "@order",
        }

        result = map_all_people(raw, config)

        assert len(result) == 3
        assert result[0].name.display_name == "First Actor"
        assert result[1].name.display_name == "Second Actor"
        assert result[2].name.display_name == "Third Actor"

    def test_none_billing_order_sorted_last(self):
        """People without billing order are sorted last."""
        raw = {
            "actors": {
                "actor": [
                    {"#text": "No Order Actor"},
                    {"#text": "First Actor", "@order": "1"},
                ]
            }
        }
        config = {
            "people_field_mappings": {"actors": "Actor"},
            "person_order_attr": "@order",
        }

        result = map_all_people(raw, config)

        assert len(result) == 2
        assert result[0].name.display_name == "First Actor"
        assert result[1].name.display_name == "No Order Actor"

    def test_returns_empty_list_when_no_people(self):
        """Returns empty list when no people fields present."""
        raw = {}
        config = {"people_field_mappings": {"actors": "Actor"}}

        result = map_all_people(raw, config)

        assert result == []

    def test_handles_guest_actors_correctly(self):
        """Handles guest actors with Guest flag."""
        raw = {
            "actors": {"actor": [{"#text": "Regular Actor", "@order": "1"}]},
            "guest_actors": {"guest_actor": [{"#text": "Guest Star", "@order": "2"}]},
        }
        config = {
            "people_field_mappings": {
                "actors": "Actor",
                "guest_actors": "Actor",
            },
            "guest_actors_field": "guest_actors",
            "person_order_attr": "@order",
        }

        result = map_all_people(raw, config)

        assert len(result) == 2
        regular = next(j for j in result if j.name.display_name == "Regular Actor")
        guest = next(j for j in result if j.name.display_name == "Guest Star")
        assert regular.guest is None
        assert guest.guest is True

    def test_comprehensive_config_example(self):
        """Tests with comprehensive configuration."""
        raw = {
            "actors": {
                "actor": [
                    {
                        "#text": "John Actor",
                        "@first_name": "John",
                        "@last_name": "Actor",
                        "@order": "1",
                        "@role": "Main Character",
                    },
                    {
                        "#text": "Jane Actress",
                        "@first_name": "Jane",
                        "@last_name": "Actress",
                        "@order": "2",
                        "@role": "Supporting Role",
                    },
                ]
            },
            "directors": {"director": [{"#text": "Director Person"}]},
            "writers": {"writer": [{"#text": "Writer Person"}]},
            "producers": {"producer": [{"#text": "Producer Person"}]},
            "executive_producers": {"executive_producer": [{"#text": "Exec Producer"}]},
            "series_creators": {"series_creator": [{"#text": "Creator Person"}]},
        }
        config = {
            "people_field_mappings": {
                "actors": "Actor",
                "directors": "Director",
                "writers": "Writer",
                "producers": "Producer",
                "executive_producers": "ExecutiveProducer",
                "series_creators": "Creator",
            },
            "person_first_name_attr": "@first_name",
            "person_last_name_attr": "@last_name",
            "person_order_attr": "@order",
            "person_role_attr": "@role",
        }

        result = map_all_people(raw, config)

        # Should have 7 people total
        assert len(result) == 7

        # Verify job functions
        functions = {j.job_function for j in result}
        assert functions == {
            "Actor",
            "Director",
            "Writer",
            "Producer",
            "ExecutiveProducer",
            "Creator",
        }

        # Verify actors have character names
        actors = [j for j in result if j.job_function == "Actor"]
        assert len(actors) == 2
        assert actors[0].character == "Main Character"
        assert actors[1].character == "Supporting Role"

    def test_to_dict_serialization(self):
        """Verifies Job to_dict works correctly."""
        raw = {
            "actors": {
                "actor": [
                    {
                        "#text": "John Actor",
                        "@first_name": "John",
                        "@last_name": "Actor",
                        "@order": "1",
                        "@role": "Hero",
                    }
                ]
            }
        }
        config = {
            "people_field_mappings": {"actors": "Actor"},
            "person_first_name_attr": "@first_name",
            "person_last_name_attr": "@last_name",
            "person_order_attr": "@order",
            "person_role_attr": "@role",
        }

        result = map_all_people(raw, config)

        assert len(result) == 1
        dict_result = result[0].to_dict()

        assert dict_result["JobFunction"] == "Actor"
        assert dict_result["BillingBlockOrder"] == 1
        assert dict_result["Character"] == "Hero"
        assert dict_result["Name"]["DisplayName"] == "John Actor"
        assert dict_result["Name"]["FirstGivenName"] == "John"
        assert dict_result["Name"]["FamilyName"] == "Actor"


@pytest.mark.unit
class TestDefaultRoleMappings:
    """Tests for DEFAULT_ROLE_MAPPINGS constant"""

    def test_contains_expected_mappings(self):
        """Verifies DEFAULT_ROLE_MAPPINGS contains expected entries."""
        assert DEFAULT_ROLE_MAPPINGS["actors"] == "Actor"
        assert DEFAULT_ROLE_MAPPINGS["directors"] == "Director"
        assert DEFAULT_ROLE_MAPPINGS["writers"] == "Writer"
        assert DEFAULT_ROLE_MAPPINGS["producers"] == "Producer"
        assert DEFAULT_ROLE_MAPPINGS["executive_producers"] == "ExecutiveProducer"
        assert DEFAULT_ROLE_MAPPINGS["series_creators"] == "Creator"
        assert DEFAULT_ROLE_MAPPINGS["guest_actors"] == "Actor"
