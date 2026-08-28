import sys

import pytest


DYNAMIC_REASON = "computed at import time"
FEATURE_OFF = True


@pytest.mark.xfail(reason="blocked by upstream issue #417")
def test_expected_failure():
    pass


@pytest.mark.skip
def test_unconditional_skip():
    pass


@pytest.mark.skipif(sys.platform == "win32", reason="unsupported on Windows")
async def test_platform_condition():
    pass


class TestGroupedBehavior:
    @pytest.mark.xfail(FEATURE_OFF, reason=DYNAMIC_REASON)
    def test_computed_reason(self):
        pass


@pytest.mark.skip(reason="the entire group is unavailable")
class TestDisabledGroup:
    def test_member(self):
        pass


@pytest.mark.custom
def test_custom_marker():
    pass


@pytest.mark.parametrize("value", [1])
def test_parameterized(value):
    pass


@pytest.mark.skip(reason="not a pytest test target")
def helper():
    pass


from pytest import mark


@mark.skip(reason="aliased imports are intentionally unsupported")
def test_aliased_marker():
    pass


pytestmark = pytest.mark.skip(reason="module-level marks are unsupported")
