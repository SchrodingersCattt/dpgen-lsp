# machine.json

`machine.json` describes execution environments for `train`, `model_devi`, and
`fp` stages. Each stage is represented as a list of task environment objects.

The LSP validates the required stage sections, optional DPDispatcher-backed
machine schema when available, and known Bohrium `scass_type` values as
warnings.
