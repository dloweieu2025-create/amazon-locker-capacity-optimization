import numpy as np
import pandas as pd

# Makes the generated dataset reproducible.
rng = np.random.default_rng(seed=42)

# Illustrative averages, NOT measured demand.
# Equal values provide a neutral starting scenario.
average_demand = {
    "hopkins": 33,
    "caleido": 33,
    "enara": 33,
    "alcala_norte": 33,
}

two_day_share = 0.40
planning_days = 7

rows = []

for locker_id, daily_average in average_demand.items():
    for day in range(1, planning_days + 1):

        # Total package requests for this location and day.
        total = int(rng.poisson(lam=daily_average))

        # Assign each request a shipping option.
        two_day = int(rng.binomial(
            n=total,
            p=two_day_share
        ))
        standard = total - two_day

        rows.append({
            "locker_id": locker_id,
            "day": day,
            "two_day": two_day,
            "standard": standard,
        })

demand = pd.DataFrame(rows)

# Save separately so your existing file is preserved.
demand.to_csv("demand_poisson.csv", index=False)

print(demand.to_string(index=False))