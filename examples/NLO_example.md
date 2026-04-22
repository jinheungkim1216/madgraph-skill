# NLO example (reserved slot — out of scope in v1)

NLO workflows (`[QCD]`, `[real=QCD]`, fixed-order, FKS subtraction, aMC@NLO event generation, MadSpin-style decay insertion) are **deliberately deferred** in v1 of this skill.

If a user requests NLO event generation, matched parton showers (MC@NLO, FxFx, MLM), or any feature requiring loop integration beyond loop-induced LO (`[noborn=QCD]`), **stop** and tell them this skill does not cover it yet.

When NLO is added in a later iteration, this file will follow the same structure as `LO_example.md`:

- `new` / `rerun` shape templates with NLO-specific slots (fixed_order mode, scale sets, PDF error sets)
- Value catalog: NLO run_card_fks.dat keys, MadSpin invocation patterns, common tagged processes
- Concrete snippets for non-trivial cases (mode=fixed_order vs mode=noshower vs shower-matched; EW corrections; real emissions)
- Worked walkthrough (e.g., `p p > t t~ [QCD]` at LHC13)
