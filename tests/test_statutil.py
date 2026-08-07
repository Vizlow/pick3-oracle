"""statutil primitives vs hard-coded scipy reference values."""
from engine import statutil


def test_chi2_sf_reference_values():
    # scipy.stats.chi2.sf references
    for x, df, want in [
        (16.918978, 9, 0.05),
        (3.841459, 1, 0.05),
        (11.070498, 5, 0.05),
        (15.086272, 5, 0.01),
        (18.307038, 10, 0.05),
        (5.0, 5, 0.415880),
        (100.0, 81, 0.074720),
    ]:
        assert abs(statutil.chi2_sf(x, df) - want) < 1e-4, (x, df)
    assert statutil.chi2_sf(0.0, 5) == 1.0
    assert statutil.chi2_sf(1000.0, 5) < 1e-100


def test_normal_sf_reference_values():
    assert abs(statutil.normal_sf(0.0) - 0.5) < 1e-12
    assert abs(statutil.normal_sf(1.959964) - 0.025) < 1e-6
    assert abs(statutil.normal_sf(-1.959964) - 0.975) < 1e-6


def test_binom_sf_exact():
    # P(X >= 3 | n=10, p=0.5) = 1 - 56/1024
    assert abs(statutil.binom_sf(3, 10, 0.5) - (1 - 56 / 1024)) < 1e-12
    assert statutil.binom_sf(0, 10, 0.5) == 1.0
    assert statutil.binom_sf(11, 10, 0.5) == 0.0
    # large-n truncation path stays sane
    assert 0.0 < statutil.binom_sf(30, 25000, 0.001) < 1.0


def test_gof_bin_merging_preserves_totals():
    obs = [50, 1, 1, 1, 1, 46]
    exp = [40.0, 2.0, 2.0, 2.0, 2.0, 52.0]
    mo, me = statutil.merge_bins(obs, exp)
    assert sum(mo) == sum(obs) and abs(sum(me) - sum(exp)) < 1e-9
    assert all(e >= 5.0 for e in me)
    stat, df, p = statutil.chi_square_gof(obs, exp)
    assert df == len(mo) - 1
    assert 0.0 <= p <= 1.0


def test_gof_uniform_data_is_null():
    obs = [100] * 10
    exp = [100.0] * 10
    stat, df, p = statutil.chi_square_gof(obs, exp)
    assert stat == 0.0 and df == 9 and p == 1.0


def test_independence_drops_zero_rows_cols():
    table = [[10, 20, 0], [0, 0, 0], [20, 10, 0]]
    stat, df, p = statutil.chi_square_independence(table)
    assert df == 1  # 2x2 after drops
    assert 0.0 <= p <= 1.0


def test_bh_fdr_known_example():
    q = statutil.bh_fdr([0.01, 0.04, 0.03, 0.005])
    want = [0.02, 0.04, 0.04, 0.02]
    assert all(abs(a - b) < 1e-12 for a, b in zip(q, want))
    assert statutil.bh_fdr([]) == []
    assert statutil.bh_fdr([1.0, 1.0]) == [1.0, 1.0]
