# Offline RL Dispatch Experiment

## Protocol
- **State Space**: (Hour of day 0-23, Battery SOC decile 0-9)
- **Action Space**: Battery charge/discharge [-2000, -1000, 0, 1000, 2000] W
- **Splits**: 
  - Train: 7 synthetic episodes (demand/PV scaled by 0.9-1.1) repeated 100 times
  - Val: 3 synthetic episodes
  - Test: 1 deterministic `gnitc_energy.json` CityLearn fixed trace
- **Algorithm**: Tabular Q-Learning (alpha=0.1, gamma=0.9, epsilon=0.2, seed=42)
- **Authority validation**: The RL proposes a dispatch action which determines `grid_import_w`. `DistrictAuthority._electrical_state` simulates the resulting load flows over the constrained network topology.

## Assertions Verified
Every step in training and evaluation asserts that:
- Total `grid_served_w` <= source capacity
- `flow_w` <= line capacity limits
- No service is routed across known open edges
- Python authority validates all constraints

## Results on Pinned Test Scenario
### Baseline (CityLearn Fixed Schedule)
- **Total Demand (Denominator)**: 141800 Wh
- **Scheduled Import**: 78380 Wh
- **Actually Routed Import**: 78180 Wh
- **Total Unmet Load**: 200 Wh
- **Critical Shortfall**: 0 Wh

### RL Agent Policy
- **Total Demand (Denominator)**: 141800 Wh
- **Scheduled Import**: 80064.91106406736 Wh
- **Actually Routed Import**: 80066.0 Wh
- **Total Unmet Load**: 0.0 Wh
- **Critical Shortfall**: 0.0 Wh

*Note: The profile and network are synthetic and make no real-world savings, prediction-accuracy, or power-delivery claim. The learned policy is advisory only and has not been loaded into the live backend loop.*
