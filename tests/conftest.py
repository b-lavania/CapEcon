"""
Pytest configuration and fixtures for CRO Analytics Enhancement tests.

This file configures hypothesis settings to ensure minimum 100 iterations
per property test as specified in the design document.
"""

try:
    from hypothesis import settings, Verbosity

    # Configure hypothesis settings for property-based tests
    # Minimum 100 iterations as per design document requirement
    settings.register_profile(
        "default",
        max_examples=100,
        verbosity=Verbosity.normal,
        deadline=None,  # No deadline for test execution
    )

    settings.register_profile(
        "ci",
        max_examples=200,  # More thorough testing in CI
        verbosity=Verbosity.verbose,
        deadline=None,
    )

    settings.register_profile(
        "dev",
        max_examples=50,  # Faster feedback during development
        verbosity=Verbosity.normal,
        deadline=5000,  # 5s per Hypothesis example (dev/CI)
    )

    # Load the default profile
    settings.load_profile("default")
except ImportError:
    pass

