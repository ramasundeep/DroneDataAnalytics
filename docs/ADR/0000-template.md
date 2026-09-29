# ADR NNNN: <short decision title in the imperative, e.g. "Use X for Y">

| Field | Value |
|---|---|
| Status | Proposed |
| Date | YYYY-MM-DD |
| Deciders | <names or roles, e.g. "CDPL founding engineering"> |
| Supersedes | — (or `NNNN-old-title.md`) |
| Superseded by | — |

> Copy this file to `docs/ADR/NNNN-kebab-title.md`, take the next free number
> from the index in [README.md](README.md), fill in every section, delete these
> quoted instructions, and add a row to the index table in the same PR.

## Context

What forces are at play? Describe the problem, the constraints that come from
the founding brief ([00_ORIGIN_PROMPT.md](../00_ORIGIN_PROMPT.md)) or from
earlier ADRs, and the facts that matter (numbers, versions, file paths). Write
for a competent engineer who has never met the founder and was not in the
room. Name only open-source projects and open-data programmes; never a
company or a client.

Reference real repository paths in backticks, e.g. `services/recorder/db/001_init.sql`.

## Decision

State the decision in one or two sentences first ("We will ..."), then the
details a reader needs to implement it correctly:

- the concrete choice, with versions pinned where relevant;
- the rules that follow from it (what code must and must not do);
- where the decision is enforced (schema, test, CI job, compose file).

## Status (Phase 0)

What of this decision is implemented today, what is tested (and how), and
what is not yet built or not yet verified (with the roadmap phase that will
deliver it). Never claim something was run if it was not. Mark code that has
never been compiled as UNVERIFIED BUILD.

## Consequences

### Positive

- ...

### Negative

- ...

### Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| ... | low / medium / high | ... |

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| ... | ... |

Give each serious alternative a sentence or two of honest reasoning. "We did
not think of it" is acceptable if true; "it is worse" without a reason is not.

## Revisit when

Concrete, observable triggers, not "if things change". For example:

- a measured number crosses a threshold (e.g. "p95 ingest latency > 50 ms at 4 vehicles");
- an upstream project ships or drops something specific;
- a roadmap phase reaches its acceptance test and the assumption fails.

## References

- Related ADRs: [NNNN](NNNN-title.md)
- Specs: `docs/0X_....md`
- Code: `path/to/file`
