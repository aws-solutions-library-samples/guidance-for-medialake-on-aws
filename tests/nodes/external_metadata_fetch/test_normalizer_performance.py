"""
Performance tests for the Generic XML normalizer.

These tests measure normalization performance to ensure:
- Single asset normalization completes in < 100ms
- No external API calls during normalization
- Large metadata payloads (up to 1MB) are handled efficiently

Performance Requirements (from requirements.md 15.x):
- Single asset normalization < 100ms
- No external API calls during normalization
- Handle large metadata payloads (up to 1MB) without memory issues
- Stateless operation for concurrent execution
- Performance metrics logging
"""

import json
import time
from typing import Any

import pytest
from nodes.external_metadata_fetch.normalizers import create_normalizer

from tests.nodes.external_metadata_fetch.fixtures import (
    SAMPLE_CONFIG,
    load_fixture,
)

# Fixture file names for performance testing
EPISODE_FIXTURES = [
    "episode_full_001.xml",
    "episode_full_002.xml",
    "episode_full_003.xml",
]

TRAILER_FIXTURES = [
    "trailer_001.xml",
    "trailer_002.xml",
]

SPECIAL_FIXTURES = [
    "special_content_001.xml",
]

ALL_FIXTURES = EPISODE_FIXTURES + TRAILER_FIXTURES + SPECIAL_FIXTURES

# Performance thresholds
MAX_NORMALIZATION_TIME_MS = 100  # Maximum time for single asset normalization
WARMUP_ITERATIONS = 3  # Number of warmup iterations before measuring
MEASUREMENT_ITERATIONS = 10  # Number of iterations for timing measurement


@pytest.fixture
def normalizer():
    """Create a normalizer with sample configuration."""
    return create_normalizer("generic_xml", SAMPLE_CONFIG)


def measure_normalization_time(
    normalizer, metadata: dict[str, Any], iterations: int = MEASUREMENT_ITERATIONS
) -> dict[str, float]:
    """Measure normalization time over multiple iterations.

    Args:
        normalizer: The normalizer instance to test
        metadata: The metadata dictionary to normalize
        iterations: Number of iterations to measure

    Returns:
        Dictionary with timing statistics (min, max, avg, total)
    """
    times = []

    # Warmup iterations (not measured)
    for _ in range(WARMUP_ITERATIONS):
        normalizer.normalize(metadata)

    # Measured iterations
    for _ in range(iterations):
        start = time.perf_counter()
        normalizer.normalize(metadata)
        end = time.perf_counter()
        times.append((end - start) * 1000)  # Convert to milliseconds

    return {
        "min_ms": min(times),
        "max_ms": max(times),
        "avg_ms": sum(times) / len(times),
        "total_ms": sum(times),
        "iterations": iterations,
    }


def get_metadata_size(metadata: dict[str, Any]) -> int:
    """Get the approximate size of metadata in bytes."""
    return len(json.dumps(metadata, default=str).encode("utf-8"))


@pytest.mark.unit
class TestNormalizationPerformance:
    """Tests for normalization performance requirements."""

    @pytest.mark.parametrize("fixture_name", ALL_FIXTURES)
    def test_normalization_under_100ms(self, normalizer, fixture_name: str):
        """Each fixture normalizes in under 100ms."""
        metadata = load_fixture(fixture_name)

        timing = measure_normalization_time(normalizer, metadata)

        assert timing["avg_ms"] < MAX_NORMALIZATION_TIME_MS, (
            f"Normalization of {fixture_name} took {timing['avg_ms']:.2f}ms "
            f"(max allowed: {MAX_NORMALIZATION_TIME_MS}ms)"
        )

    @pytest.mark.parametrize("fixture_name", ALL_FIXTURES)
    def test_normalization_timing_report(self, normalizer, fixture_name: str, capsys):
        """Report detailed timing for each fixture."""
        metadata = load_fixture(fixture_name)
        input_size = get_metadata_size(metadata)

        timing = measure_normalization_time(normalizer, metadata)

        # Normalize once more to get output size
        result = normalizer.normalize(metadata)
        output_size = get_metadata_size(result.normalized_metadata or {})

        # Print timing report (captured by pytest)
        print(f"\n--- Performance Report: {fixture_name} ---")
        print(f"Input size: {input_size:,} bytes")
        print(f"Output size: {output_size:,} bytes")
        print(f"Min time: {timing['min_ms']:.3f} ms")
        print(f"Max time: {timing['max_ms']:.3f} ms")
        print(f"Avg time: {timing['avg_ms']:.3f} ms")
        print(f"Iterations: {timing['iterations']}")
        print(
            f"Status: {'PASS' if timing['avg_ms'] < MAX_NORMALIZATION_TIME_MS else 'FAIL'}"
        )

        # Always pass - this test is for reporting
        assert True


@pytest.mark.unit
class TestLargePayloadPerformance:
    """Tests for handling large metadata payloads."""

    def test_large_metadata_payload(self, normalizer):
        """Test normalization of large metadata payload (simulated ~100KB)."""
        # Load a base fixture
        base_metadata = load_fixture("episode_full_001.xml")

        # Expand the metadata to simulate a larger payload
        # Add many actors, ratings, and custom fields
        large_metadata = dict(base_metadata)

        # Add many actors (simulate large cast)
        actors = []
        for i in range(100):
            actors.append(
                {
                    "@order": str(i + 1),
                    "@first_name": f"Actor{i}",
                    "@last_name": f"LastName{i}",
                    "@role": f"Character{i}",
                    "#text": f"Actor{i} LastName{i}",
                }
            )
        large_metadata["actors"] = {"actor": actors}

        # Add many keywords
        keywords = ", ".join([f"keyword{i}" for i in range(500)])
        large_metadata["keywords"] = keywords

        # Add large description
        large_metadata["long_description"] = "A" * 50000  # 50KB description

        # Verify size is substantial
        payload_size = get_metadata_size(large_metadata)
        print(f"\nLarge payload size: {payload_size:,} bytes")

        # Measure performance
        timing = measure_normalization_time(normalizer, large_metadata, iterations=5)

        print(f"Large payload normalization time: {timing['avg_ms']:.3f} ms")

        # Should still complete in reasonable time (allow more for large payloads)
        # The 100ms requirement is for typical payloads; large payloads may take longer
        assert timing["avg_ms"] < 500, (
            f"Large payload normalization took {timing['avg_ms']:.2f}ms "
            f"(max allowed: 500ms for large payloads)"
        )

    def test_1mb_metadata_payload(self, normalizer):
        """Test normalization of ~1MB metadata payload (requirement 15.3)."""
        # Load a base fixture
        base_metadata = load_fixture("episode_full_001.xml")

        # Expand the metadata to simulate a ~1MB payload
        large_metadata = dict(base_metadata)

        # Add many actors (simulate very large cast - 500 actors)
        actors = []
        for i in range(500):
            actors.append(
                {
                    "@order": str(i + 1),
                    "@first_name": f"ActorFirstName{i:04d}",
                    "@last_name": f"ActorLastName{i:04d}",
                    "@role": f"CharacterName{i:04d}WithLongerDescription",
                    "#text": f"ActorFirstName{i:04d} ActorLastName{i:04d}",
                }
            )
        large_metadata["actors"] = {"actor": actors}

        # Add many directors
        directors = []
        for i in range(50):
            directors.append(
                {
                    "@order": str(i + 1),
                    "@first_name": f"Director{i:03d}",
                    "@last_name": f"DirectorLast{i:03d}",
                    "#text": f"Director{i:03d} DirectorLast{i:03d}",
                }
            )
        large_metadata["directors"] = {"director": directors}

        # Add many keywords (10,000 keywords)
        keywords = ", ".join([f"keyword{i:05d}" for i in range(10000)])
        large_metadata["keywords"] = keywords

        # Add very large descriptions
        large_metadata["long_description"] = "A" * 200000  # 200KB description
        large_metadata["short_description"] = "B" * 50000  # 50KB short description
        large_metadata["long_series_description"] = (
            "C" * 200000
        )  # 200KB series description
        large_metadata["long_season_description"] = (
            "D" * 200000
        )  # 200KB season description

        # Add many ratings
        ratings = []
        for i in range(50):
            ratings.append(
                {
                    "@Type": f"rating-system-{i:02d}",
                    "@Descriptor": f"DESC{i}",
                    "#text": f"Rating{i}",
                }
            )
        large_metadata["rating"] = {"Rating": ratings}

        # Verify size is close to 1MB
        payload_size = get_metadata_size(large_metadata)
        print(
            f"\n1MB payload test - Actual size: {payload_size:,} bytes ({payload_size/1024/1024:.2f} MB)"
        )

        # Ensure we're testing with at least 500KB
        assert (
            payload_size >= 500 * 1024
        ), f"Test payload too small: {payload_size:,} bytes (need at least 500KB)"

        # Measure performance
        timing = measure_normalization_time(normalizer, large_metadata, iterations=3)

        print(f"1MB payload normalization time: {timing['avg_ms']:.3f} ms")
        print(f"Throughput: {payload_size / timing['avg_ms'] / 1024:.2f} KB/ms")

        # Should complete without memory issues
        # For very large payloads, we allow more time but still expect reasonable performance
        assert timing["avg_ms"] < 1000, (
            f"1MB payload normalization took {timing['avg_ms']:.2f}ms "
            f"(max allowed: 1000ms for 1MB payloads)"
        )

    def test_memory_efficiency(self, normalizer):
        """Test that normalization doesn't cause excessive memory usage."""
        import tracemalloc

        metadata = load_fixture("episode_full_001.xml")

        # Start memory tracking
        tracemalloc.start()

        # Perform multiple normalizations
        for _ in range(100):
            result = normalizer.normalize(metadata)
            assert result.success

        # Get memory usage
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        print(f"\nMemory usage after 100 normalizations:")
        print(f"Current: {current / 1024 / 1024:.2f} MB")
        print(f"Peak: {peak / 1024 / 1024:.2f} MB")

        # Peak memory should be reasonable (< 50MB for 100 normalizations)
        assert (
            peak < 50 * 1024 * 1024
        ), f"Peak memory usage {peak / 1024 / 1024:.2f}MB exceeds 50MB limit"


@pytest.mark.unit
class TestStatelessOperation:
    """Tests for stateless operation (concurrent execution support)."""

    def test_normalizer_is_stateless(self, normalizer):
        """Verify normalizer produces consistent results across calls."""
        metadata = load_fixture("episode_full_001.xml")

        # Normalize multiple times
        results = [normalizer.normalize(metadata) for _ in range(5)]

        # All results should be identical (except for any timestamps)
        first_result = results[0].normalized_metadata
        for i, result in enumerate(results[1:], 2):
            # Compare key fields (excluding timestamps)
            assert result.normalized_metadata.get("BasicMetadata") == first_result.get(
                "BasicMetadata"
            ), f"Result {i} differs from result 1"

    def test_independent_normalizer_instances(self):
        """Verify independent normalizer instances don't interfere."""
        metadata = load_fixture("episode_full_001.xml")

        # Create multiple normalizer instances
        normalizers = [
            create_normalizer("generic_xml", SAMPLE_CONFIG) for _ in range(3)
        ]

        # Normalize with each instance
        results = [n.normalize(metadata) for n in normalizers]

        # All results should be identical
        first_basic = results[0].normalized_metadata.get("BasicMetadata")
        for i, result in enumerate(results[1:], 2):
            assert (
                result.normalized_metadata.get("BasicMetadata") == first_basic
            ), f"Normalizer instance {i} produced different result"


@pytest.mark.unit
class TestNoExternalCalls:
    """Tests to verify no external API calls during normalization."""

    def test_no_network_calls(self, normalizer, monkeypatch):
        """Verify normalization doesn't make network calls."""
        import socket

        original_socket = socket.socket
        network_calls = []

        def mock_socket(*args, **kwargs):
            network_calls.append((args, kwargs))
            return original_socket(*args, **kwargs)

        monkeypatch.setattr(socket, "socket", mock_socket)

        metadata = load_fixture("episode_full_001.xml")
        result = normalizer.normalize(metadata)

        assert result.success
        assert (
            len(network_calls) == 0
        ), f"Normalization made {len(network_calls)} network calls"

    def test_no_http_requests(self, normalizer, monkeypatch):
        """Verify normalization doesn't make HTTP requests."""
        http_calls = []

        def mock_request(*args, **kwargs):
            http_calls.append((args, kwargs))
            raise RuntimeError("HTTP calls not allowed during normalization")

        # Mock urllib and requests if available
        try:
            import urllib.request

            monkeypatch.setattr(urllib.request, "urlopen", mock_request)
        except ImportError:
            pass

        try:
            import requests

            monkeypatch.setattr(requests, "get", mock_request)
            monkeypatch.setattr(requests, "post", mock_request)
        except ImportError:
            pass

        metadata = load_fixture("episode_full_001.xml")
        result = normalizer.normalize(metadata)

        assert result.success
        assert len(http_calls) == 0


@pytest.mark.unit
class TestPerformanceBreakdown:
    """Tests to identify performance bottlenecks in individual components."""

    def test_field_mapper_performance(self, normalizer):
        """Profile individual field mapper performance."""
        from nodes.external_metadata_fetch.normalizers.field_mappers import (
            extract_custom_fields,
            map_classifications,
            map_hierarchy,
            map_identifiers,
            map_people,
            map_ratings,
            map_technical,
            map_titles,
        )

        metadata = load_fixture("episode_full_001.xml")
        config = SAMPLE_CONFIG

        mappers = [
            (
                "identifiers",
                lambda: map_identifiers.map_all_identifiers(metadata, config),
            ),
            ("titles", lambda: map_titles.map_localized_info(metadata, config)),
            (
                "classifications",
                lambda: map_classifications.get_work_type(metadata, config),
            ),
            ("hierarchy", lambda: map_hierarchy.map_sequence_info(metadata, config)),
            ("people", lambda: map_people.map_all_people(metadata, config)),
            ("ratings", lambda: map_ratings.map_ratings(metadata, config)),
            ("technical", lambda: map_technical.map_all_technical(metadata, config)),
            ("custom_fields", lambda: extract_custom_fields.extract(metadata, config)),
        ]

        print("\n--- Field Mapper Performance Breakdown ---")
        total_time = 0

        for name, mapper_func in mappers:
            times = []
            for _ in range(MEASUREMENT_ITERATIONS):
                start = time.perf_counter()
                mapper_func()
                end = time.perf_counter()
                times.append((end - start) * 1000)

            avg_time = sum(times) / len(times)
            total_time += avg_time
            print(f"{name:20s}: {avg_time:.3f} ms")

        print(f"{'Total':20s}: {total_time:.3f} ms")

        # All individual mappers should be fast
        assert (
            total_time < MAX_NORMALIZATION_TIME_MS
        ), f"Total mapper time {total_time:.2f}ms exceeds {MAX_NORMALIZATION_TIME_MS}ms"

    def test_validation_performance(self, normalizer):
        """Profile validation performance."""
        from nodes.external_metadata_fetch.normalizers.validation import (
            validate_input_metadata,
            validate_output_metadata,
        )

        metadata = load_fixture("episode_full_001.xml")
        config = SAMPLE_CONFIG

        # Measure input validation
        input_times = []
        for _ in range(MEASUREMENT_ITERATIONS):
            start = time.perf_counter()
            validate_input_metadata(metadata, config)
            end = time.perf_counter()
            input_times.append((end - start) * 1000)

        # Get normalized output for output validation
        result = normalizer.normalize(metadata)
        normalized = result.normalized_metadata

        # Measure output validation
        output_times = []
        for _ in range(MEASUREMENT_ITERATIONS):
            start = time.perf_counter()
            validate_output_metadata(normalized)
            end = time.perf_counter()
            output_times.append((end - start) * 1000)

        print("\n--- Validation Performance ---")
        print(f"Input validation:  {sum(input_times)/len(input_times):.3f} ms")
        print(f"Output validation: {sum(output_times)/len(output_times):.3f} ms")

        # Validation should be fast
        assert sum(input_times) / len(input_times) < 20, "Input validation too slow"
        assert sum(output_times) / len(output_times) < 20, "Output validation too slow"

    def test_serialization_performance(self, normalizer):
        """Profile to_dict serialization performance."""
        metadata = load_fixture("episode_full_001.xml")

        # Get the normalized result
        result = normalizer.normalize(metadata)

        # The to_dict is already called in normalize(), but we can measure
        # the JSON serialization overhead
        normalized = result.normalized_metadata

        times = []
        for _ in range(MEASUREMENT_ITERATIONS):
            start = time.perf_counter()
            json.dumps(normalized, default=str)
            end = time.perf_counter()
            times.append((end - start) * 1000)

        avg_time = sum(times) / len(times)
        print(f"\n--- Serialization Performance ---")
        print(f"JSON serialization: {avg_time:.3f} ms")

        # Serialization should be fast
        assert avg_time < 10, f"JSON serialization too slow: {avg_time:.2f}ms"


@pytest.mark.unit
class TestPerformanceLogging:
    """Tests for performance logging functionality."""

    def test_performance_logging_on_success(self, normalizer, caplog):
        """Verify performance metrics are logged on successful normalization."""
        import logging

        # Set log level to capture INFO logs
        caplog.set_level(logging.INFO)

        metadata = load_fixture("episode_full_001.xml")
        result = normalizer.normalize(metadata)

        assert result.success

        # Check that performance log was emitted
        log_messages = [r.message for r in caplog.records]
        assert any(
            "Normalization completed" in msg for msg in log_messages
        ), f"Expected 'Normalization completed' log message, got: {log_messages}"

        # Check that the log contains expected fields
        for record in caplog.records:
            if "Normalization completed" in record.message:
                # Verify extra fields are present
                assert hasattr(record, "duration_ms") or "duration_ms" in str(
                    record.__dict__
                )
                break

    def test_performance_logging_on_validation_failure(self, normalizer, caplog):
        """Verify performance metrics are logged on validation failure."""
        import logging

        caplog.set_level(logging.DEBUG)

        # Create invalid metadata (empty)
        invalid_metadata = {}
        result = normalizer.normalize(invalid_metadata)

        assert not result.success

        # Check that failure log was emitted
        log_messages = [r.message for r in caplog.records]
        assert any(
            "failed" in msg.lower() for msg in log_messages
        ), f"Expected failure log message, got: {log_messages}"

    def test_performance_metrics_are_reasonable(self, normalizer, caplog):
        """Verify logged performance metrics are reasonable values."""
        import logging

        caplog.set_level(logging.INFO)

        metadata = load_fixture("episode_full_001.xml")
        result = normalizer.normalize(metadata)

        assert result.success

        # Find the performance log record
        for record in caplog.records:
            if "Normalization completed" in record.message:
                # Check duration is reasonable (< 100ms)
                if hasattr(record, "duration_ms"):
                    assert (
                        record.duration_ms < 100
                    ), f"Duration {record.duration_ms}ms exceeds 100ms"

                # Check sizes are positive
                if hasattr(record, "input_size_bytes"):
                    assert record.input_size_bytes > 0
                if hasattr(record, "output_size_bytes"):
                    assert record.output_size_bytes > 0
                break
