# Evaluation V2: DEV, frozen primary holdout, and source-coverage challenge

The existing 40-case dataset, `backend/evaluation/datasets/codebase_qa_v2_v1.json`,
is now the **DEV set**. It has already influenced source coverage, chunking,
hybrid retrieval, and reranking decisions. Its results are not an unbiased
estimate of generalisation. Do not edit its questions or gold labels to create
holdout cases.

DEV identity:

- Dataset version: `codebase-qa-v2-v1.1.0`
- Canonical dataset SHA-256: `eb095d8701955216171ad3463f6cfb2d7ce2ce44cf8aef47ceaf00c41edd2a8b`
- Case-set SHA-256: `97a85902564bdcfce9e5e85da38c0f1008cb3fc839296f2a3c4871e1f78a26af`
- Prepared corpus: 212 chunks; manifest SHA-256 `86aa6028950355c88b68d57bb3fc027be3e414acfb5a3ea45e3d2b341d70995b`
- Source snapshot used for holdout anchoring: `7a3b7b05087793975ae0a84d85e7d691d9f3352e` (the accepted Batch 2A source-coverage revision that produced the frozen 212-row corpus). The historical DEV JSON has `source_revision: null`; this commit identifies the checked source tree for the new candidate package, not a retroactive edit to DEV.
- DEV categories: four cases in each of semantic/conceptual, exact identifier,
  configuration/constants, filename/path, decorator/API route, architecture,
  cross-module, multiple evidence, difficult near matches, and unanswerable.

The original
`backend/evaluation/datasets/codebase_qa_v2_holdout_candidates_v1.json`
remains an **unchanged machine-prepared candidate pool** for provenance:
50 proposed cases (five per category), canonical hash
`4b43650c5d60643d197fe33005823ce9c8f9570746d958dce0b845bf12ea88e7`.
The independent read-only audit accepted 19 unchanged, accepted 15 after
specific edits, moved five to a separate source-coverage challenge, and
rejected 11. These decisions, including line-anchored label edits, are encoded
in `backend/scripts/freeze_audited_holdout.py`. No replacement questions were
added merely to reach 40.

## Frozen primary holdout — initial blind run completed

`backend/evaluation/datasets/codebase_qa_v2_holdout_v1.json` is version
`codebase-qa-v2-holdout-v1.0.0`. Status:
**human-reviewed, independently audited, frozen**. It contains 34 cases:
29 source-answerable, five absent-feature/unanswerable, and eight genuinely
multi-evidence. It uses the Batch 2A source revision above and the same 212-row
index manifest. Its first blind dense/hybrid/rerank-20 comparison is now an
immutable historical validation result in
`docs/holdout-v1-initial-blind-evaluation.md`. The questions have been observed;
**do not reuse this set as an unbiased model-selection benchmark** or edit its
questions, labels, or hashes. Dense remains the serving default.

- Dataset hash (canonical payload excluding the self-recorded hash fields):
  `3bb15dafe49667f5b53ab39215c3729fe2b71326d9775e095a05077ec6373c8a`
- Case-set hash:
  `47ffd589172c5d916ade8d8e23d4a30be2dc005c427a97639af6ab51bc544375`
- Category counts: semantic/conceptual 4; exact identifier 4;
  configuration/constants 4; filename/path 2; decorator/API route 3;
  architecture 2; cross-module 3; multiple-required-evidence 4; difficult
  near matches 3; absent-feature/unanswerable 5.
- Every required primary source is within the accepted Batch 2A Python/config
  indexing allowlist. Alternatives within an evidence unit mean equivalent
  acceptable evidence; complementary units remain separately required.

The automatic DEV check found **zero exact, normalised, or high-text-similarity
question duplicates** in the primary set. It still flags 16 accepted cases
for 34 broad source-span/anchor overlaps with DEV. The independent audit
judged the retained overlaps non-material after checking question intent and
evidence; the warnings remain visible rather than being hidden.

## Separate source-coverage challenge

`backend/evaluation/datasets/codebase_qa_v2_source_coverage_challenge_v1.json`
is version `codebase-qa-v2-source-coverage-challenge-v1.0.0` and contains
exactly five source-answerable cases:
`holdout-semantic-05`, `holdout-path-01`, `holdout-path-02`,
`holdout-cross-03`, and `holdout-cross-05`. Dataset hash:
`dc729a0d02c46afb72ba61e593733069647305dd2a03dd1c50bbe19fe51778eb`;
case-set hash:
`969ed3d972e14805b9acec3190e9ab62431ee2963ea81c8a5a90cf1b3c98a4d9`.
Their required frontend source is in the frozen Git tree but outside the
accepted Batch 2A index policy. **Exclude all five from primary retrieval
ranking denominators.** They are a distinct future source-coverage challenge.

## Source-only checks and later protocol

From `backend/`, validate the frozen datasets against the audited decisions
and source tree without writing:

```bash
.venv/bin/python -m scripts.freeze_audited_holdout --check
```

The candidate review artifact remains at `docs/holdout-review.md` as
historical provenance, not the final label authority. Both frozen files
self-record and validate their counts, categories, corpus identity, dataset
hash, and case-set hash. They also carry the original candidate-pool hash.

The predeclared first comparison has happened; do not repeat it for selection
or retune on its outcomes. Score the coverage challenge separately only in a
future source-coverage experiment. Report source/index coverage alongside any
future development-set ranking metrics.

Limitations: one small repository; a question-level rather than source-disjoint
holdout; backend-heavy primary cases; 34 primary cases provide a small sample;
and all five negatives concern absent features. This holdout cannot by itself
establish broad generalisation.

**No retrieval, reranking, or retrieval metric was run on either frozen
dataset during its construction.**

## DEV2 candidate pool

`backend/evaluation/datasets/codebase_qa_v2_dev2_candidates_v1.json` is new
development material grounded in the same accepted Batch 2A source revision.
Its review package is `docs/dev2-review.md`. It is **machine-prepared, pending
independent audit, not frozen, and not scored**. DEV2 deliberately emphasizes
multi-evidence ordering, candidate competition, cross-module behavior, and
oversized source chunks; unlike the former holdout, it is intended for future
development and tuning after review. Candidate overlap classifications against
both DEV1 and the observed HOLDOUT are visible in the JSON and review package.
Source and tokenizer checks do not run retrieval or call an answer provider.
