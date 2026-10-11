# Assurance specs

One file per benchmark case, named after the case id. Each file is written from that case's
**documented contract**: the target's docstring, the downstream callers, and the catalog goal in
`src/verifix/agent_harness.py`. Specs are never derived from any agent's patch. They are committed
before any experiment that uses them.

A spec file can define:

* `mr_*(rng)` / `contract_*(rng)`: metamorphic relations and contracts. They are run by the
  sandboxed probe (`relations` mode) against the patched worktree, with a seeded
  `random.Random`. A relation fails by raising `AssertionError`, whose message is the
  counterexample.
* `INPUT_GENERATORS = {qualname: fn(rng) -> {"args": [...], "kwargs": {...}}}`: these supply
  differential-fuzzing inputs for functions whose parameters cannot be generated from annotations
  alone.
* `DRIVERS = {qualname: "<source defining drive(module, inp)>"}`: these drive stateful classes
  for differential fuzzing. The source is executed inside the probe. A driver may be shared by
  several qualnames, and in that case it runs only once.

Only the standard library may be imported at module level. The orchestrator imports this file to
read the generators and does not have the case repository on `sys.path`.
