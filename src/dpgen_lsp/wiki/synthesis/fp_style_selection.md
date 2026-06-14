# fp_style Selection Guide

The choice of `fp_style` depends on your available software and system type:

## Common Workflows

| System Type | Recommended fp_style | Notes |
|---|---|---|
| Periodic solids | vasp, abacus, pwscf | Plane-wave DFT |
| Molecules | gaussian | Gaussian basis sets |
| Large systems | cp2k | Efficient for >1000 atoms |
| 1D/2D materials | vasp (aniso_kspacing), abacus | Anisotropic k-spacing support |

## Engine-specific Notes

### VASP
- Requires `fp_incar` with KSPACING and KGAMMA settings
- Supports `fp_aniso_kspacing` for 1D/2D materials
- `cvasp` enables Custodian-based error handling

### ABACUS
- Supports both PW and LCAO basis
- `fp_orb_files` required for LCAO calculations
- `k_points` or `kspacing` for k-grid specification

### CP2K
- `user_fp_params` for custom input parameters
- `external_input_path` for template-based input
- Requires force and stress tensor output sections in template