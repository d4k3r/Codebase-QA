# Bounded structural chunking experiment

## Controlled comparison

The BEFORE corpus and AFTER corpus use the same source snapshot at Git revision
`7a3b7b05087793975ae0a84d85e7d691d9f3352e`. The same 40 questions and evidence
units, MiniLM model, normalized embeddings, exact cosine retrieval, candidate depth
10, and production context builder were used. The AFTER corpus was prepared only in
the disposable evaluation database. The normal application corpus was not replaced.

The dataset remains a machine-prepared, source-grounded draft pending human review.
Its case-set hash is
`97a85902564bdcfce9e5e85da38c0f1008cb3fc839296f2a3c4871e1f78a26af`.

## Candidate policy

This policy is **not active**. The runnable application and checked-in evaluation
manifest use the accepted Batch 2A source-coverage policy
`python-ast-symbols-companions-config-text-v2` described in
[`source-coverage.md`](source-coverage.md). The details below preserve the rejected
candidate methodology for future comparison.

The model input limit is 256 tokenizer tokens including special tokens. Structural
children target at most 224 tokens after adding their parent identity, leaving a
32-token margin. Python chunks at or below 256 tokens remain unchanged.

- Oversized functions and async functions are grouped at consecutive body-statement
  boundaries. The first child keeps the exact decorators/signature and leading body
  statements when they fit together. Later children receive only the parent identity
  as embedding-only text.
- Oversized classes become an exact class header, bounded class-level companion
  statements, and methods. Fitting methods stay whole; oversized methods use the
  function policy with qualified class/method identity.
- Oversized module and `module_companion` regions split at top-level statement
  boundaries.
- Allowlisted config text groups complete lines to the 224-token target. Only an
  individually oversized line is split inside the line.
- A single AST statement that cannot fit remains one exact `*_atomic` chunk and is
  reported as oversized. Source is never regenerated or overlapped.

Persisted content always remains an exact contiguous source slice with truthful line
provenance. Embedding-only parent identity is not returned as source content.

## Measured result

| Metric | BEFORE | AFTER |
|---|---:|---:|
| Indexed chunks | 212 | 281 |
| Chunks above 256 tokens | 35/212 (16.51%) | 8/281 (2.85%) |
| Maximum token count | 1,282 | 679 |
| Median token count | 114 | 129 |
| P95 token count | 537 | 234 |
| Index evidence coverage | 40/40 (100.00%) | 40/40 (100.00%) |
| Hit@1 | 9/36 (25.00%) | 9/36 (25.00%) |
| Hit@3 | 21/36 (58.33%) | 16/36 (44.44%) |
| Hit@5 | 25/36 (69.44%) | 17/36 (47.22%) |
| Hit@10 | 31/36 (86.11%) | 22/36 (61.11%) |
| MRR@10 | 15.5889/36 (43.30%) | 13.3194/36 (37.00%) |
| Micro evidence recall@10 | 31/40 (77.50%) | 22/40 (55.00%) |
| Final-context evidence recall | 31/40 (77.50%) | 22/40 (55.00%) |
| Context sufficiency | 28/36 (77.78%) | 21/36 (58.33%) |
| Selection loss | 0/31 (0.00%) | 0/22 (0.00%) |

All eight remaining oversized chunks are explicitly marked atomic statement chunks.
No evaluated gold evidence remains beyond the embedding boundary, but the additional
structural candidates substantially worsened dense ranking.

At depth 10, `cross-module-03` improved. Ten cases regressed:
`semantic-01`, `semantic-02`, `semantic-04`, `config-01`, `route-04`,
`architecture-03`, `architecture-04`, `cross-module-01`, `multi-01`, and
`multi-02`. The other 29 cases were unchanged. Multiple-required-evidence recovery
fell from 3/8 to 1/8 evidence units.

## Decision: REVISE / REJECT

The representation improvement is real, but corpus growth from 212 to 281 candidates
and evidence fragmentation harmed exact dense ranking more than truncation relief
helped. This candidate policy should not be published as the default chunker without
a narrower design and another controlled evaluation. Later lexical/hybrid work must
remain a separate experiment; no lexical retrieval was added here.
