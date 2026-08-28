import pytest


@pytest.mark.xfail(reason="not a collected test module")
def helper():
    pass

