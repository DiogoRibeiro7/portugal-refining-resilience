import pandas as pd
import pytest

from portugal_refining_resilience.validation import assert_nonnegative, assert_unique


def test_assert_unique_rejects_duplicate_keys() -> None:
    df = pd.DataFrame({"year": [2020, 2020], "product": ["diesel", "diesel"]})
    with pytest.raises(ValueError):
        assert_unique(df, ["year", "product"])


def test_assert_nonnegative_rejects_negative_physical_value() -> None:
    df = pd.DataFrame({"value_kt": [1.0, -1.0]})
    with pytest.raises(ValueError):
        assert_nonnegative(df, ["value_kt"])
