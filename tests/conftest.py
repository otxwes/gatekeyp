import hypothesis

# helpers is the single source of truth for shared test constants and env
# setup; importing it here (pytest auto-loads conftest) is what guarantees the
# repo-root path insertion and GATEKEYP_* defaults are applied for every test.
from helpers import TEST_HMAC_SECRET, TEST_ORGANIZER_KEY  # noqa: F401

# Project-wide Hypothesis profile: default behavior is tuned for CI robustness.
# The stock 200 ms per-example deadline is a common source of flaky failures on
# slow runners, so raise it and de-randomize the generation so failures
# reproduce. Individual tests may still override with @settings().
hypothesis.settings.register_profile(
    "repo",
    deadline=2000,
    derandomize=True,
)
hypothesis.settings.load_profile("repo")
