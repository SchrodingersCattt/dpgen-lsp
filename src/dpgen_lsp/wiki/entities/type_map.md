# type_map

**Required parameter** defining atom types in the system.

## Format
```json
"type_map": ["H", "C", "O"]
```

## Constraints
- Order must match the order in initial data files
- Order must match `fp_pp_files` for FP calculations
- Order must match the type_map in `default_training_param.model`
- Case-sensitive

## Common Values
- Single element: `["Al"]`, `["Si"]`, `["Cu"]`
- Multi-element: `["H", "C", "O"]`, `["Li", "Fe", "P", "O"]`
- High-entropy: `["Co", "Cr", "Fe", "Mn", "Ni"]`