# param.json

`param.json` describes the DP-GEN workflow: atom types, initial training data,
exploration configurations, model-deviation jobs, first-principles labeling
style, and engine-specific templates or parameters.

The LSP validates JSON syntax, docs-backed top-level fields, cross-field
relationships such as `mass_map` and `fp_pp_files` alignment with `type_map`,
threshold ordering, and path/glob existence for generated-input preflight.
