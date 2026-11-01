# Deviations from PLAN.md (addendum 35)

1. `make_bank.py` was generalised (prefixed terms, SKOS example/note, freeze guard) after the DCAT bank was frozen; regeneration of the DCAT bank with the new script is byte-identical (sha256 cf7db0a0...), checked before the SSN bank was written. The DCAT CSV itself was not changed.
2. The pipeline's baseline command `build-a` works per top-level section and skips a section whose model-written Turtle does not parse (logged in `<domain>/work/build.log`, counted in `PROGRESS.md`); this is the pipeline's own behaviour and is not repaired.
3. Concurrency of the extractor: 4 workers through a wrapper that overrides the pipeline's fixed default of 8 (`S4_CONCURRENCY`); request bodies unchanged.
