"""CityLearn equity metric, reused only for offline allocation evaluation.

Source: citylearn/internal/kpi.py, CityLearnKPIService._equity_distribution_metrics
https://github.com/citylearn-project/CityLearn/tree/834575c1a0194c8ae9d648ae858376a94dfceb78
MIT; Copyright (c) 2020 Jose Ramon Vazquez-Canteli, Intelligent Environments Laboratory.
Full notice: licenses/CityLearn-LICENSE. Change: extracted static method unchanged.
"""
from typing import Dict, Optional

import numpy as np


def _equity_distribution_metrics(relative_benefits: np.ndarray) -> Dict[str, Optional[float]]:
    benefits = np.array(relative_benefits, dtype='float64')
    benefits = benefits[np.isfinite(benefits)]

    if benefits.size == 0:
        return {
            'equity_gini_benefit': None,
            'equity_cr20_benefit': None,
            'equity_losers_percent': None,
        }

    losers_percent = float(100.0 * np.count_nonzero(benefits < 0.0) / benefits.size)
    benefits_plus = np.clip(benefits, 0.0, None)
    total_plus = float(benefits_plus.sum())

    if total_plus <= 0.0:
        return {
            'equity_gini_benefit': None,
            'equity_cr20_benefit': None,
            'equity_losers_percent': losers_percent,
        }

    n = benefits_plus.size
    diff_sum = float(np.abs(benefits_plus[:, None] - benefits_plus[None, :]).sum())
    gini = float(diff_sum / (2.0 * n * total_plus))

    k = max(1, int(np.ceil(0.2 * n)))
    top_sum = float(np.sort(benefits_plus)[::-1][:k].sum())
    cr20 = float(top_sum / total_plus)

    return {
        'equity_gini_benefit': gini,
        'equity_cr20_benefit': cr20,
        'equity_losers_percent': losers_percent,
    }
