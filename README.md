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

For every locker and day, expected occupancy cannot exceed physical capacity:

```text
sum(q[s,t-v] * y[l,s,v] for s and arrival days v <= t) <= capacity[l]
```

Here, `q[s,k]` is the probability that a package using ship option `s`
still occupies a slot `k` days after arrival.

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
The real-life locations that these lockers are modeled off of are included on this document: https://docs.google.com/document/d/1_viIj7C2rx0FSYzGNlHOiCVw-nTY8Gyfh8lXWRdTdyw/edit?usp=sharing

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

The program also writes these files to `reports/base/`:

- `decisions.csv`: demand, accepted, rejected, and expected slots by option.
- `daily_occupancy.csv`: capacity, expected occupancy, and unused capacity.
- `locker_summary.csv`: weekly demand, accepted, and rejected by location.

Run all what-if scenarios with:

```bash
python src/solve_capacity.py --scenarios
```

This uses the same saved demand for every run: base capacities from the CSV
(currently 46 each), 23 slots each, 69 slots each, and base capacities with
all pickups delayed one day. Delayed-pickup occupancy is 1 at ages 0 and 1;
thereafter it equals the original probability at age minus one. Scenario
runs do not alter any input files.

Results are saved in `reports/base/`, `reports/capacity_23/`,
`reports/capacity_69/`, and `reports/slower_pickups/`.
`reports/scenario_comparison.csv` summarizes the scenarios in the current run.
Use `--output-dir PATH` to choose another destination. Re-running replaces
the corresponding result files.

Verified results for the current data, using integer acceptance quantities:

| Scenario | Slots per locker | Requests | Accepted | Rejected |
| --- | ---: | ---: | ---: | ---: |
| Base | 46 | 909 | 803 | 106 |
| Less capacity | 23 | 909 | 464 | 445 |
| More capacity | 69 | 909 | 909 | 0 |
| Pickups delayed one day | 46 | 909 | 557 | 352 |

All four runs terminated optimally with HiGHS. More capacity increases
throughput; slower collection ties up slots and reduces throughput. These
results describe this synthetic week, not measured Amazon performance.
Multiple optimal allocations can exist, so individual decisions can differ
while the maximum throughput remains the same.

## Troubleshooting

If no solver is available, activate the environment and install HiGHS:

```bash
python -m pip install highspy
```

If Pyomo is missing:

```bash
python -m pip install pyomo
```
# Poster

This is a self-contained A0 LaTeX poster project based on the ICFO `baposter` layout. It uses model outputs in `../reports/` and input probabilities in `../data/`.

## Files

- `poster.tex`: editable poster source
- `baposter.cls`: local poster class from the ICFO template
- `generate_figures.py`: regenerates the vector PDF charts
- `images/`: generated charts
- `main.tex`: wrapper used by the Codex LaTeX preview

## Generate the figures

From the repository root:

```bash
conda activate amazon-locker-capacity
python -m pip install reportlab
python poster/generate_figures.py
```

## Compile the poster

```bash
cd poster
latexmk -pdf poster.tex
```

Or, without `latexmk`:

```bash
pdflatex poster.tex
pdflatex poster.tex
```

The result is `poster.pdf`. Edit `YOUR NAME` and `COLLEAGUE NAME` near the top of `poster.tex` before the final build.

## Data shown

The baseline has four 46-slot lockers, seven planning days, 909 requests, 803 accepted packages, and an 88.3% acceptance rate. Scenarios compare 23, 46, and 69 slots per locker and a one-day pickup delay.

## Attribution

Layout adapted from [ICFO-poster-template](https://github.com/episanty/ICFO-poster-template) by Emilio Pisanty. The included `baposter.cls` retains its original notices.
