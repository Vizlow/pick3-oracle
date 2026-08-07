"""Stdlib-only statistical primitives for the deep analysis battery.

No scipy on the target machine (system python3.9), so the chi-square tail is
computed from the regularized incomplete gamma (series + Lentz continued
fraction, Numerical Recipes 6.2). Values are unit-tested against scipy
references hard-coded in tests/test_statutil.py.
"""
import math

_EPS = 3e-16
_MAX_ITER = 500


def _gammp_series(a, x):
    """Regularized lower incomplete gamma P(a,x) by series; valid for x < a+1."""
    term = 1.0 / a
    total = term
    for n in range(1, _MAX_ITER):
        term *= x / (a + n)
        total += term
        if abs(term) < abs(total) * _EPS:
            break
    return total * math.exp(-x + a * math.log(x) - math.lgamma(a))


def _gammq_cf(a, x):
    """Regularized upper incomplete gamma Q(a,x) by continued fraction; x >= a+1."""
    tiny = 1e-300
    b = x + 1.0 - a
    c = 1.0 / tiny
    d = 1.0 / b
    h = d
    for i in range(1, _MAX_ITER):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < _EPS:
            break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def chi2_sf(x, df):
    """Survival function of the chi-square distribution: P(X >= x)."""
    if x <= 0:
        return 1.0
    a = df / 2.0
    xx = x / 2.0
    if xx < a + 1.0:
        return max(0.0, min(1.0, 1.0 - _gammp_series(a, xx)))
    return max(0.0, min(1.0, _gammq_cf(a, xx)))


def normal_sf(z):
    """Standard normal upper tail P(Z >= z)."""
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def binom_sf(k, n, p):
    """Exact binomial upper tail P(X >= k) for X ~ Binomial(n, p)."""
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return 1.0
    lp, lq = math.log(p), math.log1p(-p)
    lbase = math.lgamma(n + 1)
    total = 0.0
    mode = (n + 1) * p
    for i in range(k, n + 1):
        term = math.exp(lbase - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * lp + (n - i) * lq)
        total += term
        if i > mode and term < total * 1e-16:
            break
    return min(1.0, total)


def merge_bins(observed, expected, min_expected=5.0):
    """Merge adjacent bins left-to-right until every expected count >= min_expected."""
    obs_out, exp_out = [], []
    acc_o = acc_e = 0.0
    for o, e in zip(observed, expected):
        acc_o += o
        acc_e += e
        if acc_e >= min_expected:
            obs_out.append(acc_o)
            exp_out.append(acc_e)
            acc_o = acc_e = 0.0
    if acc_e > 0:
        if exp_out:
            obs_out[-1] += acc_o
            exp_out[-1] += acc_e
        else:
            obs_out.append(acc_o)
            exp_out.append(acc_e)
    return obs_out, exp_out


def chi_square_gof(observed, expected, min_expected=5.0):
    """Goodness-of-fit test with adjacent-bin merging. Returns (stat, df, p).

    df = bins - 1 (no fitted parameters anywhere in the battery)."""
    obs, exp = merge_bins(observed, expected, min_expected)
    if len(obs) < 2:
        return 0.0, 0, 1.0
    stat = sum((o - e) ** 2 / e for o, e in zip(obs, exp))
    df = len(obs) - 1
    return stat, df, chi2_sf(stat, df)


def chi_square_independence(table):
    """Independence test on a contingency table (list of rows). All-zero rows
    and columns are dropped. Returns (stat, df, p)."""
    rows = [list(r) for r in table if sum(r) > 0]
    if not rows:
        return 0.0, 0, 1.0
    keep = [j for j in range(len(rows[0])) if sum(r[j] for r in rows) > 0]
    rows = [[r[j] for j in keep] for r in rows]
    n = sum(sum(r) for r in rows)
    if n == 0 or len(rows) < 2 or len(rows[0]) < 2:
        return 0.0, 0, 1.0
    row_tot = [sum(r) for r in rows]
    col_tot = [sum(r[j] for r in rows) for j in range(len(rows[0]))]
    stat = 0.0
    for i, r in enumerate(rows):
        for j, o in enumerate(r):
            e = row_tot[i] * col_tot[j] / n
            stat += (o - e) ** 2 / e
    df = (len(rows) - 1) * (len(rows[0]) - 1)
    return stat, df, chi2_sf(stat, df)


def bh_fdr(pvals):
    """Benjamini-Hochberg q-values, returned in the original order."""
    m = len(pvals)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: pvals[i])
    q = [0.0] * m
    running = 1.0
    for rank in range(m - 1, -1, -1):
        i = order[rank]
        running = min(running, pvals[i] * m / (rank + 1))
        q[i] = running
    return q
