from dpgen_lsp.features.committee import validate


def _base(**overrides):
    data = {
        "type_map": ["H", "O"],
        "numb_models": 2,
        "train_backend": "pytorch",
        "model_format": "pth",
        "default_training_param": [
            {"model": {"type": "dpa3", "descriptor": {"type": "se_atten", "rcut": 6.0}, "fitting_net": {"type": "ener"}}},
            {"model": {"type": "dpa3", "descriptor": {"type": "se_e2_a", "rcut": 6.0}, "fitting_net": {"type": "ener"}}},
        ],
    }
    data.update(overrides)
    return data


def test_cross_architecture_committee_is_valid():
    assert validate(_base()) == []


def test_committee_length_is_blocking():
    issues = validate(_base(numb_models=4))
    assert any(item["code"] == "committee.length" for item in issues)


def test_committee_signature_mismatch_is_blocking():
    data = _base()
    data["default_training_param"][1]["model"]["descriptor"]["rcut"] = 5.0
    issues = validate(data)
    assert any(item["code"] == "committee.cutoff" for item in issues)


def test_dpa4_requires_pytorch_and_pt2_for_lammps():
    data = _base(
        numb_models=1,
        train_backend="tensorflow",
        model_format="pb",
        default_training_param={"model": {"type": "dpa4", "descriptor": {"rcut": 6.0}}},
    )
    codes = {item["code"] for item in validate(data)}
    assert "model.backend.incompatible" in codes


def test_dpa4_and_dpa4c_cannot_mix():
    data = _base(
        train_backend="pytorch",
        default_training_param=[
            {"model": {"type": "dpa4", "descriptor": {"rcut": 6.0}}},
            {"model": {"descriptor": {"type": "dpa4c", "rcut": 6.0}}},
        ],
    )
    assert any(item["code"] == "model.family.mixed" for item in validate(data))


def test_dpa4c_compile_options_must_be_under_training():
    data = _base(
        train_backend="pytorch-exportable",
        model_format="pt2",
        default_training_param={"model": {"enable_tf32": True, "descriptor": {"type": "dpa4c", "rcut": 6.0}}},
        numb_models=1,
    )
    assert any(item["code"] == "model.compile_scope" for item in validate(data))
