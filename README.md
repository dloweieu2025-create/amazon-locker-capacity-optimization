# Amazon Locker Capacity Optimization

This project implements an integer linear programming model for ship-option
capacity reservation at Amazon Locker locations. The model decides how many
packages of each ship option to accept on each day while respecting expected
locker occupancy. Its objective is to maximize total accepted packages.

The implementation uses [Pyomo](https://www.pyomo.org/) and the open-source
[HiGHS](https://highs.dev/) optimizer.

## Project structure

```text
.
├── article/                 # Reference paper
├── data/
│   ├── demand.csv           # Synthetic demand by locker, day, and ship option
│   ├── locker.csv           # Locker IDs and capacities
│   └── occupancy.csv        # Probability of remaining by package age
├── src/
│   └── solve_capacity.py    # Pyomo model and command-line interface
├── environment.yaml         # Conda environment definition
├── .gitignore
└── README.md
```

## Model

### Decision variable

```text
y[l,s,t] = packages of ship option s accepted at locker l on day t
```

The variables are nonnegative integers.

### Objective

```text
maximize  sum(y[l,s,t] for all lockers, ship options, and days)
```

### Capacity constraint

For every locker and day, expected occupancy cannot exceed a safety-adjusted
fraction of physical capacity:

```text
sum(q[s,t-v] * y[l,s,v] for s and arrival days v <= t) <= alpha * capacity[l]
```

Here, `q[s,k]` is the probability that a package using ship option `s`
still occupies a slot `k` days after arrival.

`alpha` is a fixed safety factor, shared by all lockers and scenarios. The
default is **0.9**, reserving 10% of physical capacity as an illustrative buffer.
For a 46-slot locker, the expected-occupancy limit is 41.4 slots; acceptance
quantities remain integers. Physical capacities stay at 23, 46, or 69 slots
depending on the scenario, and the safety factor is applied once to each.
This assumed buffer is not calibrated to a specific overflow probability and
does not guarantee that actual occupancy stays within physical capacity.
Values must satisfy `0 < alpha <= 1`; `alpha=1` is the unbuffered benchmark.

### Demand constraint

```text
y[l,s,t] <= demand[l,s,t]  for every locker, ship option, and day
```

Demand is specific to each location. Unused space at one locker cannot serve
another location's demand. The four locker problems are independent, although
they are solved together in one model.

## Input data

Ship-option columns must match between `demand.csv` and `occupancy.csv`.

### `data/locker.csv`

```csv
locker_id,capacity
hopkins,46
caleido,46
enara,46
alcala_norte,46
```

Each locker ID must be unique and capacity must be a positive integer.
The 46-slot capacities are assumed configurations, not verified measurements.

### `data/demand.csv`

```csv
locker_id,day,two_day,standard
hopkins,1,18,20
hopkins,2,20,16
```

Demand must be finite and nonnegative. Each row represents one locker and
arrival day. Every locker/day pair must occur exactly once; planning days
must be consecutive integers starting at 1.

The saved synthetic data contain 909 requests over four locations and seven
days: independent Poisson totals with mean 33 per location per day, followed
by a binomial split with probability 0.40 for two-day shipping, using NumPy's
default random generator and seed 42. These are assumed demand scenarios,
not measured demand or population-calibrated forecasts. The solver never
regenerates demand.

### `data/occupancy.csv`

```csv
days_since_arrival,two_day,standard
0,1.00,1.00
1,0.25,0.70
2,0.00,0.25
3,0.00,0.00
```

Probabilities must lie between 0 and 1. The
`days_since_arrival` values must be contiguous and start at zero. A value of
`0.25` for `two_day` at age 1 means that 25% of those packages are expected
to remain one day after arrival.

## Assumptions

- All four lockers start empty.
- Every package uses one slot; compartment sizes are ignored.
- Deliveries occur before pickups each day.
- Identical age-based occupancy probabilities apply to all locations and days.
- Probabilities equal 1 at age zero and cannot increase with age.
- Module III only: demand and pickup probabilities are supplied inputs.
- Occupancy after the last planning day has no objective penalty.
- Packages are indivisible, so acceptance variables are integers.
- Occupancy is enforced in expectation, with a default safety factor of 0.9.
- Occupancy beyond the largest age in `occupancy.csv` is treated as zero.
- Reservations are expected slot requirements and may be fractional.

## Installation with Conda

From the repository root, create and activate the environment:

```bash
conda env create -f environment.yaml
conda activate amazon-locker-capacity
```

If the environment already exists, update it with:

```bash
conda env update -f environment.yaml --prune
```

Dependencies in the `pip:` section of `environment.yaml` are installed
automatically by Conda.

## Alternative installation with pip

If Conda is unavailable:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install "pyomo>=6.8,<7" "highspy>=1.7,<2"
```

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

## Run the model

From the repository root:

```bash
python src/solve_capacity.py
```

Choose another safety factor, or reproduce the unbuffered benchmark:

```bash
python src/solve_capacity.py --alpha 0.95
python src/solve_capacity.py --scenarios --alpha 1 --output-dir reports/unbuffered
```

The selected factor applies to every scenario in that run. Use different output
directories when comparing factors to retain both sets of results.

Default data paths are resolved relative to the repository, so the script can
also be launched from another working directory.

Display the HiGHS solver log:

```bash
python src/solve_capacity.py --tee
```

Explicitly select HiGHS:

```bash
python src/solve_capacity.py --solver appsi_highs
```

With `--solver auto`, the script searches for `appsi_highs`, `highs`,
`cbc`, and `glpk`, in that order.

### Use different input files

```bash
python src/solve_capacity.py \
  --locker path/to/locker.csv \
  --demand path/to/demand.csv \
  --occupancy path/to/occupancy.csv
```

View every command-line option:

```bash
python src/solve_capacity.py --help
```

## First-come-first-served benchmark

Every run also evaluates first-come-first-served (FCFS) acceptance. For each
locker and day, the policy accounts for expected occupancy from previously
accepted packages, then accepts each arriving request while one additional
package fits below `alpha * capacity`. Once no further package fits, the
remaining requests that day are rejected. Previously rejected requests are
not carried forward. The policy never reserves space using future demand or
prioritizes shipping options by their pickup speed.

The CSV contains daily totals, not request timestamps. We therefore assume
a shuffled within-day order using Python's standard-library random generator
with seed 42. There is a separate reproducible stream per locker/day, and the
same request order is used across all capacity and pickup scenarios. This
does not regenerate demand. Change the order assumption with:

```bash
python src/solve_capacity.py --scenarios --fcfs-seed 43 --output-dir reports/seed_43
```

Both policies use identical demand, physical capacities, alpha, pickup
probabilities, empty starting lockers, and planning horizon. FCFS is evaluated
with expected occupancy, not sampled pickup times, so the comparison isolates
acceptance decisions within the same model. If demand is fractional, FCFS
processes its integer part, matching the optimizer's integer acceptance bound;
the saved synthetic requests are all integers.

The optimizer knows the whole week's demand, whereas FCFS does not look ahead.
Its gain therefore measures the benefit of planning with that information
relative to this greedy policy. It is not an estimate of performance under
forecast errors or actual random pickups. FCFS results also depend on the
assumed arrival order; the reported seed is one illustrative realization.

## Output

The program prints:

1. The solver used, safety factor, and maximum throughput.
2. Accepted packages for every locker, day, and ship option.
3. Expected capacity reservations by ship option.
4. Expected total locker occupancy by day.
5. FCFS throughput and the additional packages accepted by optimization.

The program also writes these files to `reports/base/`:

- `decisions.csv`: demand, accepted, rejected, and expected slots by option.
- `daily_occupancy.csv`: physical capacity, alpha, effective capacity, expected
  occupancy, and unused physical and effective capacity. `unused_capacity`
  measures physical capacity minus expected occupancy;
  `unused_effective_capacity` measures remaining room below the buffered limit.
- `locker_summary.csv`: physical and effective capacity, alpha, weekly demand,
  accepted, and rejected by location.

The same three files for FCFS are written to the scenario's `fcfs/` subfolder,
for example `reports/base/fcfs/`. These are greedy policy evaluations, not
solver-optimal solutions.

Run all what-if scenarios with:

```bash
python src/solve_capacity.py --scenarios
```

This uses the same saved demand for every run: base capacities from the CSV
(currently 46 each), 23 slots each, 69 slots each, and base capacities with
all pickups delayed one day. Delayed-pickup occupancy is 1 at ages 0 and 1;
thereafter it equals the original probability at age minus one. Scenario
runs do not alter any input files. The same alpha (0.9 by default) applies to
all four scenarios, including slower pickups.

Results are saved in `reports/base/`, `reports/capacity_23/`,
`reports/capacity_69/`, and `reports/slower_pickups/`.
`reports/scenario_comparison.csv` summarizes the scenarios in the current run.
It includes alpha, total physical slots, and total effective capacity.
It also records the FCFS seed, accepted and rejected requests, acceptance rate,
and optimization's gain in packages and percent relative to FCFS throughput.
The percentage is blank when FCFS accepts zero requests, since division by
zero is undefined. The solver and optimal status refer to the optimized policy.
Use `--output-dir PATH` to choose another destination. Re-running replaces
the corresponding result files.

Verified results for the current data, using integer acceptance quantities
and the default safety factor `alpha=0.9`:

| Scenario | Physical slots per locker | Effective capacity per locker | Requests | Accepted | Rejected |
| --- | ---: | ---: | ---: | ---: | ---: |
| Base | 46 | 41.4 | 909 | 746 | 163 |
| Less capacity | 23 | 20.7 | 909 | 423 | 486 |
| More capacity | 69 | 62.1 | 909 | 907 | 2 |
| Pickups delayed one day | 46 | 41.4 | 909 | 506 | 403 |

For comparison, the unbuffered benchmark (`alpha=1`) accepts 803, 464, 909,
and 557 packages respectively. These benchmark runs were also verified.
In the base scenario, the illustrative buffer reduces accepted packages by
57 (from 803 to 746); overflow risk has not been measured.

All runs terminated optimally with HiGHS. More capacity increases
throughput; slower collection ties up slots and reduces throughput. These
results describe this synthetic week, not measured Amazon performance.
Multiple optimal allocations can exist, so individual decisions can differ
while the maximum throughput remains the same.

### Optimization versus FCFS

Verified comparison for `alpha=0.9` and FCFS seed 42:

| Scenario | FCFS accepted | Optimized accepted | Additional packages | Gain over FCFS |
| --- | ---: | ---: | ---: | ---: |
| Base | 723 | 746 | 23 | 3.18% |
| Less capacity | 365 | 423 | 58 | 15.89% |
| More capacity | 907 | 907 | 0 | 0.00% |
| Pickups delayed one day | 483 | 506 | 23 | 4.76% |

For this assumed arrival order, planning adds the most value when capacity is
tight. With 69 physical slots per locker, both policies achieve the same total.
These comparisons use the same 909 saved requests in every scenario.

## Validation

Run the safety-factor and FCFS regression checks in the installed environment:

```bash
python -m unittest discover -s tests -v
```

## Troubleshooting

If no solver is available, activate the environment and install HiGHS:

```bash
python -m pip install highspy
```

If Pyomo is missing:

```bash
python -m pip install pyomo
```
