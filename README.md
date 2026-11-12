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
│   ├── demand.csv           # Forecast demand by day and ship option
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

For every locker and day, expected occupancy cannot exceed physical capacity:

```text
sum(q[s,t-v] * y[l,s,v] for s and arrival days v <= t) <= capacity[l]
```

Here, `q[s,k]` is the probability that a package using ship option `s`
still occupies a slot `k` days after arrival.

### Demand constraint

```text
sum(y[l,s,t] for l) <= demand[s,t]
```

Because the current `demand.csv` has no `locker_id` column, demand is
treated as a pool shared across lockers. With the current single-locker data,
this is equivalent to `y[s,t] <= demand[s,t]`.

## Input data

Ship-option columns must match between `demand.csv` and `occupancy.csv`.

### `data/locker.csv`

```csv
locker_id,capacity
L1,30
```

Each locker ID must be unique and capacity must be a positive integer.

### `data/demand.csv`

```csv
day,two_day,standard
1,12,15
2,14,18
```

Demand must be nonnegative. Each row represents forecast arrivals for one day.

### `data/occupancy.csv`

```csv
days_since_arrival,two_day,standard
0,1.00,1.00
1,0.25,0.70
```

Probabilities must lie between 0 and 1. The
`days_since_arrival` values must be contiguous and start at zero. A value of
`0.25` for `two_day` at age 1 means that 25% of those packages are expected
to remain one day after arrival.

## Assumptions

- The locker is empty immediately before the first planning day.
- Packages are indivisible, so acceptance variables are integers.
- Occupancy is enforced in expectation.
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

## Output

The program prints:

1. The solver used and maximum throughput.
2. Accepted packages for every locker, day, and ship option.
3. Expected capacity reservations by ship option.
4. Expected total locker occupancy by day.

For the current data, the maximum throughput is 43 packages. Multiple optimal
allocations can exist, so the package mix may vary while the objective value
remains the same.

## Troubleshooting

If no solver is available, activate the environment and install HiGHS:

```bash
python -m pip install highspy
```

If Pyomo is missing:

```bash
python -m pip install pyomo
```
