# Evaluation V2: DEV and proposed holdout

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

The new JSON under `backend/evaluation/datasets/codebase_qa_v2_holdout_candidates_v1.json`
is a **machine-prepared source-grounded HOLDOUT CANDIDATE pending human review**,
not a frozen evaluation set. It contains 50 candidates, five per category.
Its canonical candidate SHA-256 is
`4b43650c5d60643d197fe33005823ce9c8f9570746d958dce0b845bf12ea88e7`.
There are 45 answerable and five plausible unanswerable candidates; 14
answerable cases require multiple independently described evidence units.
Some frontend TypeScript source is answerable in the Git tree but is outside
the current indexed Python/config allowlist. Keep that distinction visible in
the later evaluation rather than changing labels to fit the index.

Run source-only validation and generate the review package from `backend/`:

```bash
.venv/bin/python -m scripts.prepare_holdout_review
```

This command checks the DEV file identity, validates all candidate paths,
line spans and content anchors against the pinned Git revision, flags exact
and normalised question duplicates, likely textual paraphrases, and DEV
gold-span overlap, then writes `docs/holdout-review.md`. It imports no
retrieval, embedding, database, or provider service and performs no indexing
or retrieval. A shared file or broad-span overlap is a warning, not proof of
duplicate question intent. Unanswerable labels require human confirmation
against the frozen corpus.

Human freeze protocol:

1. Review each candidate's question, rubric, evidence excerpts, DEV warnings,
   and answerability. Mark ACCEPT, REJECT, or EDIT with notes. In particular,
   review route cases that share broad DEV function spans and candidates that
   require frontend files not present in the current index.
2. Prefer genuinely distinct facts and realistic multi-module questions over
   perfect numerical balance. Target about 40 cases: roughly four per
   category, with several unanswerable and at least eight well-justified
   multi-evidence cases. Reject weak or duplicative entries even if fewer
   than 40 survive.
3. Apply edits to a **new** reviewed/frozen dataset; rerun source validation.
   Record reviewer/date, frozen source revision, dataset and case-set hashes,
   and an explicit corpus manifest. The generated candidate file is not that
   frozen dataset.
4. Only after review and freeze, in a later batch, run dense, hybrid RRF, and
   hybrid+reranker-20 once on the same prepared corpus and report all results,
   including source/index coverage. Do not use holdout results to choose labels,
   depth, model, or serving defaults.

**No retrieval mode or retrieval metric has been run on these candidates
during their construction.**
