# dpgen-lsp

Language Server Protocol implementation for DP-GEN (Deep Potential GENerator) input files.

## Features

- **Auto-completion** for dpgen JSON input parameters (run, simplify workflows)
- **Diagnostics** with error and warning detection (JSON syntax, schema validation, semantic checks)
- **Hover documentation** for dpgen parameters from official arginfo documentation
- **Code formatting** for consistent JSON structure
- Support for `param.json` and `machine.json` input files

## Installation

```bash
pip install dpgen-lsp
```

## Usage

Start the language server:

```bash
dpgen-lsp
```

Agent-facing CLI:

```bash
dpgen-lsp-tool check param.json
dpgen-lsp-tool complete param.json --line 5 --character 10
dpgen-lsp-tool hover param.json --line 5 --character 10
```

### Editor Integration

This package provides the language server executable. To use it in an editor, connect an LSP client to the `dpgen-lsp` command and register `.json` files as dpgen input files.

## Supported Workflows

- **dpgen run**: `param.json` with type_map, training, model_devi, fp settings
- **dpgen simplify**: `param.json` with pick_data, iterative selection parameters

## Supported FP Engines

- VASP, Gaussian, CP2K, ABACUS, PWSCF (Quantum ESPRESSO), SIESTA, PWmat, CPX, Amber/Diff, Custom

## Example Input File

```json
{
    "type_map": ["H", "C"],
    "mass_map": [1, 12],
    "init_data_sys": ["CH4/deepmd"],
    "sys_configs": [["CH4/scale*/00000*/POSCAR"]],
    "numb_models": 4,
    "default_training_param": {
        "model": {
            "type_map": ["H", "C"],
            "descriptor": {
                "type": "se_a",
                "sel": [16, 4],
                "rcut_smth": 0.5,
                "rcut": 5.0,
                "neuron": [120, 120, 120],
                "resnet_dt": true,
                "axis_neuron": 12,
                "seed": 1
            },
            "fitting_net": {
                "neuron": [25, 50, 100],
                "resnet_dt": false,
                "seed": 1
            }
        },
        "learning_rate": {
            "type": "exp",
            "start_lr": 0.001,
            "decay_steps": 100
        },
        "loss": {
            "start_pref_e": 0.02,
            "limit_pref_e": 2,
            "start_pref_f": 1000,
            "limit_pref_f": 1,
            "start_pref_v": 0.0,
            "limit_pref_v": 0.0
        },
        "training": {
            "numb_steps": 2000,
            "disp_file": "lcurve.out",
            "disp_freq": 1000,
            "save_freq": 1000
        }
    },
    "model_devi_dt": 0.002,
    "model_devi_skip": 0,
    "model_devi_f_trust_lo": 0.05,
    "model_devi_f_trust_hi": 0.15,
    "model_devi_jobs": [
        {
            "sys_idx": [0],
            "temps": [100],
            "press": [1.0],
            "trj_freq": 10,
            "nsteps": 300,
            "ensemble": "nvt"
        }
    ],
    "fp_style": "vasp",
    "fp_task_max": 20,
    "fp_task_min": 5,
    "fp_pp_path": "./",
    "fp_pp_files": ["POTCAR_H", "POTCAR_C"],
    "fp_incar": "./INCAR_methane"
}
```

## License

MIT