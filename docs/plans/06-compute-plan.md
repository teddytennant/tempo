# Compute Plan

Full table and assumptions live in `00-master-plan.md` (§ Compute plan & estimates). Summary:

- **Operating assumption:** scarce/uncertain compute — plan around **a few A100-hours + local CPU**
  (16-core nixos-server at 100.106.20.11, no GPU). Treat H200s as upside unlocked only after a cheap
  experiment proves a method works.
- **Binding resource when scaling RL = CPU cores** for forward-model game generation, not GPU FLOPs.
- **Affordable now:** floor agent (CPU), forward-model dev (CPU), **BC spine (a few A100-hours)**.
- **Gated:** self-play RL (micro-experiment must beat BC past ±14pt before renting a high-core host);
  LLM teacher (shelved until H200-class compute is confirmed).
- **Deployment footprint:** <50 MB ONNX net on CPU, single-digit ms/move — GPU size is irrelevant to
  what ships; the only deploy budget is the 10-min CPU game clock.

Re-measure the self-play estimate after the Stage-2 throughput probe. Ping the user when an A100
session is actually needed (BC training, or the self-play micro-experiment).
