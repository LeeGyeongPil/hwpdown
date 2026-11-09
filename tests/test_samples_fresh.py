from hwpdown.samples.build import build_samples


def test_committed_samples_match_builder(samples):
    for name, data in build_samples().items():
        assert (samples / name).read_bytes() == data, (
            f"samples/{name} is stale; run `uv run hwpdown samples build samples`"
        )


def test_builder_is_deterministic():
    assert build_samples() == build_samples()
