# Active Learning in DP-GEN

DP-GEN uses a concurrent learning approach to generate Deep Potential models:

## Workflow

1. **Initialization**: Start with a small set of first-principles data
2. **Training**: Train multiple DP models (typically 4) with different random seeds
3. **Exploration**: Run MD with all models, use model deviation to identify uncertain structures
4. **Labeling**: Calculate first-principles energies/forces for selected uncertain structures
5. **Iteration**: Add new data to training set, repeat until convergence

## Key Parameters

- `numb_models`: Typically 4 models for reliable model deviation estimation
- `model_devi_f_trust_lo/hi`: Force model deviation thresholds for candidate selection
- `fp_task_max/min`: Maximum and minimum number of FP calculations per iteration
- `model_devi_adapt_trust_lo`: Adaptive threshold adjustment for balanced exploration