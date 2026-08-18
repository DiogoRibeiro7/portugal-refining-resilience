import numpy as np
import pandas as pd

from portugal_refining_resilience.breaks import chow_test


def test_chow_detects_large_known_level_break() -> None:
    years = pd.Series(range(2005, 2025))
    values = pd.Series(
        [year - 2000 for year in range(2005, 2015)]
        + [100 + year - 2015 for year in range(2015, 2025)]
    )
    result = chow_test(years, values, break_year=2015)
    assert np.isfinite(result.f_statistic)
    assert result.p_value < 0.05


def test_chow_excludes_transition_years() -> None:
    years = pd.Series(range(2005, 2025))
    values = pd.Series(range(20))
    result = chow_test(years, values, break_year=2022, transition_years=(2021,))
    assert result.excluded_years == (2021,)
    assert result.n_pre == 16
    assert result.n_post == 3
