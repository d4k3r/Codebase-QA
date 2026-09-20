**Overall verdict: NEEDS MATERIAL REVISION.**

I recommend **38 cases: 3 accepted unchanged, 35 accepted after edits, and 7 rejected**. Several edits are metadata corrections or additional evidence alternatives. The material problems are incomplete call-chain evidence, overstated multi-evidence requirements, misleading long-chunk annotations, duplicated benchmark facts, and two incorrect or overbroad answer rubrics.

The corrected pool would be useful **development material**. It should not be presented as an independent measure of generalisation beyond DEV1 and HOLDOUT.

**Identity and methodology**

The inspected candidate was:

- File: `backend/evaluation/datasets/codebase_qa_v2_dev2_candidates_v1.json`
- Version: `codebase-qa-v2-dev2-candidates-v1.0.0`
- Count: **45**
- Verified canonical hash, using the project’s canonicalisation:
  `4ed6388ba299dbf7ae9dbbbca01d72cf46b4520dd26895605732d88463a872d6`
- Frozen source revision for every implementation judgment:
  `7a3b7b05087793975ae0a84d85e7d691d9f3352e`

I compared the candidates with all 40 DEV1 questions and the actual frozen 34-case HOLDOUT V1, including their rubrics and evidence. I also checked the separate source-coverage dataset.

The audit combined frozen-source inspection, source-only validation, static inspection of accepted chunking/indexing and evidence-matching rules, and offline tokenisation of source chunks. Validation tooling was inspected before its safe functions were used; the preparation entry point that writes review files was not run. Test source was inspected as potential alternative evidence.

All original paths, line bounds and anchors passed source validation. That does **not** establish semantic sufficiency: several passing labels omit necessary facts, and one spans two accepted chunks in a way that prevents a single chunk from satisfying its anchors.

No retrieval outputs or performance measurements informed these decisions.

**All 45 decisions**

In the tables below, IDs omit the common `dev2-` prefix.

Category abbreviations:

- **S** — `semantic_conceptual`
- **A** — `architecture`
- **X** — `cross_module_behavior`
- **C** — `configuration_constants`
- **M** — `multiple_required_evidence`
- **N** — `difficult_near_matches`
- **I** — `exact_identifier`
- **U** — `unanswerable_insufficient_context`

Overlap uses **NONE / LOW / MATERIAL**, abbreviated **N / L / M**. “Units” gives the labelled count and recommended count after correction; rejected cases show the defensible count if reconsidered. “Late” describes evidence position, not demonstrated retrieval difficulty.

| ID | Category | Decision | Answerability | Evidence verdict | DEV1 | HOLDOUT | Units | Long-chunk verdict | Reason |
|---|---|---|---|---|---|---|---|---|---|
| multi-01 | X→S | **EDIT** | Yes | Expand caller context | N | L | 2→2 | Core distinction early | Two functions, but no cross-module boundary |
| multi-02 | X→S | **EDIT** | Yes | Three requirements unnecessary | L | L | 3→1 | Counter late | Ask directly about the two counters |
| multi-03 | M | **EDIT** | Yes | Publication evidence incomplete | L | L | 2→2 | Late | Include transaction publication |
| multi-04 | M | **EDIT** | Yes | Correct; add alternative | L | L | 2→2 | Boundary-crossing | Mismatch is early; deletion/order proof extends later |
| multi-05 | X | **EDIT** | Yes | Strengthen question’s two-part requirement | L | N | 2→2 | Setting early | Explicitly ask environment variable and use site |
| multi-06 | M | **REJECT** | Yes | Three units overprescribed | L | N | 3→2 | Late | Redundant statistics exercise beside multi-02 |
| multi-07 | X | **EDIT** | Yes | Missing dispatch connection | L | L | 3→4 | Config branch late | Connect discovery admission to actual chunker |
| multi-08 | M | **EDIT** | Yes, after narrowing | “Malformed” is too broad | L | L | 2→2 | Service check late | Specify no choices or empty content |
| architecture-01 | A | **EDIT** | Yes | Flag definition omitted | N | N | 2→2 | No | Include required confirmation argument |
| architecture-02 | A→S | **EDIT** | Yes, with qualification | Order assumption unstated | N | N | 1 | No | Hash identity is a helper-level concept |
| architecture-03 | A | **EDIT** | Yes | Missing pre-query call order; exception error | N | N | 1→2 | Late validator check | Prove validation occurs before case searches |
| architecture-04 | A | **REJECT** | Yes | Sufficient | M | N | 2→2 | No | Recombines two DEV1 database-setup facts |
| architecture-05 | A→C | **EDIT** | Yes | One unit crosses accepted chunks | N | N | 1→2 | Settings portion early | Split path definition from Settings use |
| architecture-06 | A→S | **EDIT** | Yes | Narrow claim to dataset validation | N | N | 1 | No | Validator lookup, not runtime architecture |
| semantic-01 | S | **ACCEPT** | Yes | Sufficient; valid test alternative | L | N | 1 | Oversized alternative is not diagnostic | Useful skip-versus-stop distinction |
| semantic-02 | S→A | **EDIT** | Yes | Strengthen beyond placeholder trivia | L | N | 1→2 | Provider call crosses boundary | Test no-context orchestration |
| semantic-03 | S | **EDIT** | Yes | Narrow to global ordering mechanism | N | N | 1 | Final sort late | Distinguish final path order from traversal order |
| semantic-04 | S | **EDIT** | Yes | Strengthen question and caller span | L | L | 2→2 | No | Make validator and enforcement connection necessary |
| semantic-05 | S | **EDIT** | Yes | Missing eventual empty return | L | L | 1 | Late | Guard alone does not prove complete outcome |
| semantic-06 | S | **EDIT** | Qualified | Preservation claim incomplete | N | N | 1→2 | Flush logic late | Whitespace-only groups can be dropped |
| exact-01 | C | **EDIT** | Yes | Correct; add value alternative | N | N | 2→2 | No | Explicit constant/value/use question |
| exact-02 | C | **EDIT** | Yes | Correct | N | N | 1 | No | HOLDOUT overlap metadata correction only |
| exact-03 | C | **EDIT** | Yes | Rubric asks unnecessary extras | N | N | 1 | No | Focus on healthcheck command and target |
| exact-04 | C | **EDIT** | Yes | Correct bounds; improve wording/tags | L | N | 1 | Late | Explicit retry-setting diagnostic |
| exact-05 | I | **EDIT** | Yes | Correct; narrow rubric/add test | N | N | 1 | No | Async label, not all symbol classifications |
| near-01 | N | **REJECT** | Needs nonempty-module qualification | One chunk suffices | L | L | 1 | Late | Reuses fallback and companion facts |
| near-02 | N | **EDIT** | Yes | Correct | L | L | 1 | Relevant checks early | DEV1 overlap metadata correction only |
| near-03 | N | **EDIT** | Yes; rubric polarity wrong | Missing two call-chain links | L | L | 2→4 | New retrieval unit early | Answer is **Yes**, not “No” |
| near-04 | N | **EDIT** | Yes | Correct; add test alternative | L | N | 1 | Relevant checks early | Good distinction between safe HTTP messages |
| near-05 | N | **EDIT** | Yes | Correct | N | L | 1 | No | DEV1 overlap correction; modest difficulty |
| long-01 | S | **EDIT** | Yes | Correct | N | N | 1 | Genuinely late | HOLDOUT overlap metadata correction only |
| long-02 | S | **REJECT** | Yes for specified shapes | Same service evidence as multi-08 | L | N | 1 | Genuinely late | Strictly weaker duplicate |
| long-03 | S | **REJECT** | Yes | Correct | M | N | 1 | Genuinely late | Repeats DEV1 fail-closed discovery fact |
| long-04 | C | **ACCEPT** | Yes | Sufficient | L | N | 1 | Genuinely late | Useful operator constraint |
| long-05 | A→S | **EDIT** | Yes, with availability qualification | Tighten report-field span | N | N | 1 | Genuinely late | Metadata enumeration is not architecture |
| mixed-01 | X | **ACCEPT** | Yes | Three meaningful locations | L | N | 3→3 | Both long-function spans early | Genuine route/schema/service propagation |
| mixed-02 | X | **REJECT** | Yes | Sufficient | L | M | 2→2 | No | Recombines HOLDOUT port and database-URL facts |
| mixed-03 | X | **EDIT** | Yes | Configuration handoff missing | L | L | 2→5 | Setting alias late | Trace documented key through actual wiring |
| mixed-04 | S | **EDIT** | Yes | Correct | N | N | 1 | No | Remove unjustified mixed-signal tag |
| mixed-05 | S | **EDIT** | Yes | Missing execution/no-fallback proof | L | L | 1 | Late implementation; short alternative | Remove mixed tag; expand/add evidence |
| ordinary-01 | S | **EDIT** | Yes | Correct; add test alternative | L | L | 1 | Prefix already previews policy | Useful ordinary question, not clean truncation probe |
| ordinary-02 | S | **EDIT** | Yes | Correct | N | N | 1 | No | DEV1 overlap metadata correction only |
| ordinary-03 | S | **REJECT** | Yes | Correct | L | M | 1 | Straddles boundary | Decomposes HOLDOUT syntax-error case |
| unanswerable-01 | U | **EDIT** | Unanswerable as labelled | Absence sufficiently supported | N | L | 0 | N/A | HOLDOUT overlap metadata correction only |
| unanswerable-02 | U | **EDIT** | Unanswerable as labelled | Absence sufficiently supported | L | N | 0 | N/A | DEV1 overlap metadata correction only |

**Exact proposed corrections**

These are proposed edits only. Unmentioned fields remain unchanged. Apply the overlap classifications from the decision table to the corresponding metadata.

All line ranges below refer exclusively to the frozen revision. To avoid repeating long paths:

- `L` = `backend/app/services/repository_loader.py`
- `C` = `backend/app/services/chunker.py`
- `T` = `backend/app/services/text_chunker.py`
- `S` = `backend/app/services/storage.py`
- `B` = `backend/app/services/embeddings.py`
- `G` = `backend/app/services/rag.py`
- `R` = `backend/app/services/retrieval.py`
- `Cfg` = `backend/app/config.py`
- `Api` = `backend/app/api/routes.py`
- `Sch` = `backend/app/schemas.py`
- `Ev` = `backend/app/evaluation.py`

Semicolons between evidence locations below indicate separate required units. Locations explicitly called alternatives belong inside the same unit.

1. **multi-01**

   Keep the question and answer. Change category to `semantic_conceptual`.

   Keep root resolution at `L:31–39`. Expand the traversal unit to `L:73–109`, covering `resolve_repository_root(repository_path)`, both `follow_symlinks=False` classifications, and `visit(root)`. This makes the invocation relationship explicit.

   Retain `multi_evidence`. Do not add `long_chunk`: the distinguishing no-follow checks occur within the retained prefix.

2. **multi-02**

   **Question:** “Do `python_files_discovered` and `rows_stored` count the same thing when indexing includes configuration files?”

   **Rubric:** “No. `python_files_discovered` counts discovered paths whose suffix is `.py`. `rows_stored` counts prepared database rows, with one row constructed per prepared chunk, including chunks from configuration sources. Neither statistic is a count of all discovered files.”

   Replace the three units with one, `index-count-semantics`, at `S:55–89`, anchored by the row-building loop, `python_files_discovered=sum`, and `rows_stored=len(rows)`.

   Change category to `semantic_conceptual`; remove `multi_evidence`; add `long_chunk`. Clear the multi-evidence rationale and set its single/multiple-unit annotation consistently with a single-unit case. Retain `mixed_source`.

   The mixed-source storage test is useful corroboration, but it does not directly assert the `rows_stored` field and is not a complete substitute for this revised rubric.

3. **multi-03**

   Keep the question and answer.

   Extend fallback evidence to `C:131–146`. Extend publication evidence to `S:55–79`, including `db.commit()`. The original second span stops at row construction and does not establish publication.

   Keep two units; add `long_chunk`.

4. **multi-04**

   Keep the question, answer and existing two implementation units.

   Add `backend/tests/test_api.py:136–155` as an alternative to the HTTP-error unit; it establishes `StorageError` → HTTP 500.

   Replace `early_source` with `boundary_crossing`. Retain `long_chunk`. The mismatch guard is early, but establishing its position before deletion requires the later part of storage.

5. **multi-05**

   **Question:** “Which environment variable controls the FastAPI title, and where is that setting applied?”

   **Rubric:** “`APP_NAME` populates `Settings.app_name`; `main.py` passes `get_settings().app_name` as the FastAPI title.”

   Keep `Cfg:30` and `backend/app/main.py:8–10` as separate units. Add `.env.example:4–5`, containing `APP_NAME=Codebase QA V2`, as an alternative for the environment-setting unit.

   This wording makes both locations necessary. The original question could largely be answered from app construction alone.

6. **multi-07**

   Keep the question and answer.

   Keep the three existing units and add a fourth, `python-chunker-dispatch`, at `S:36–43`, anchored by the `.py` branch and `chunk_python_file`.

   The four requirements are: configuration sampling, configuration-only admission branch, dispatch to the Python chunker, and full Python UTF-8 reading. Add `long_chunk`.

   Do not extend the answer into a claim that discovery screens whole configuration files for NUL bytes.

7. **multi-08**

   **Question:** “If a completion has no choices or empty answer content, how does `/ask` report the failure?”

   **Rubric:** “An empty choices list triggers the missing-answer `RAGGenerationError`; falsy message content triggers the separate empty-answer `RAGGenerationError`. The `/ask` route translates either into HTTP 502 with the generic detail `LLM generation failed.`”

   Keep `G:136–142`; `Api:113–115`. Add `backend/tests/test_api.py:210–224` as an alternative to the HTTP translation unit.

   Retain `multi_evidence` and `long_chunk`; remove `across_long_chunks`. Only the service-side distinction is late in its chunk.

   “Malformed completion” was too broad: the implementation does not catch every conceivable malformed shape—for example, `choices=None` can produce a different exception.

8. **architecture-01**

   Keep the question.

   **Rubric:** “Preparation requires `--confirm-write`, compares it with the expected confirmation constant, and rejects a mismatch before calling `index_repository`. The scorer marks its transaction read-only before calling `evaluate_dataset`.”

   Expand preparation evidence to `backend/scripts/prepare_evaluation_corpus.py:13–30`; retain `backend/scripts/evaluate_retrieval.py:49–65` separately.

   Do not require the literal confirmation string as an additional answer fact: its definition is outside the preparation-function chunk.

9. **architecture-02**

   Keep the question. Change category to `semantic_conceptual`.

   **Rubric:** “For the same ordered source records, `compute_index_manifest` hashes repository, path, symbol metadata, line bounds and content, while excluding row IDs and vectors. Changing only those excluded values leaves the manifest unchanged.”

   Use `Ev:206–224`. Do not imply invariance under arbitrary reordering of input records.

10. **architecture-03**

    Keep the question.

    **Rubric:** “Before iterating over cases and calling search, evaluation validates repository scope, nonempty corpus rows, expected chunk count, manifest hash and chunking identifier. Blank corpus scope raises `EvaluationError`; the listed corpus mismatches raise `CorpusManifestMismatch`.”

    Keep `Ev:227–262` and add a separate `evaluation-preflight-order` unit at `Ev:529–544`, showing the validation call before the case loop and `search_code`.

    Add `multi_evidence` and `long_chunk`. Merely labelling the validator does not prove when it executes.

11. **architecture-05**

    Keep the question and answer. Change category to `configuration_constants`.

    Replace the crossing unit with:

    - `env-path-definition`: `Cfg:11–12`, covering `Path(__file__).resolve().parents[2]` and `ENV_FILE`.
    - `settings-env-path`: `Cfg:18–24`, covering `env_file=ENV_FILE`.

    Add `backend/tests/test_config.py:9–13` as an alternative to the second unit.

    Add `multi_evidence`. Do not add `long_chunk`: the relevant Settings use is near the beginning.

    This is a necessary representation fix. The original `Cfg:11–23` unit combines module-companion and class anchors that cannot all occur in one accepted chunk.

12. **architecture-06**

    **Question:** “How does dataset validation reject cases assigned to a different repository from the declared corpus?”

    **Rubric:** “`EvaluationDataset.validate_cases` compares each case’s repository with the corpus repository and raises `ValueError` listing mismatched case IDs.”

    Keep `Ev:95–109`. Change category to `semantic_conceptual`.

    This describes a dataset-construction check, without implying an additional runtime enforcement layer.

13. **semantic-02**

    **Question:** “When no retrieved chunk fits the context budget, does answer generation stop or still call the provider, and with what context?”

    **Rubric:** “With valid configuration and successful retrieval, `build_context` returns `No repository context was retrieved.` and an empty included-chunk list. `answer_question` still constructs the prompt and calls the provider; there is no early return for this no-fitting-context condition.”

    Use two units: `G:42–67`; `G:119–130`.

    Change category to `architecture`; add `multi_evidence` and `long_chunk`.

    This replaces a weak fixed-string lookup with a useful orchestration question.

14. **semantic-03**

    **Question:** “How does discovery guarantee repository-relative POSIX path ordering, rather than merely the order produced by walking each directory?”

    **Rubric:** “After traversal, it sorts the collected paths using `path.relative_to(root).as_posix()` as the key.”

    Replace the broad span with `L:107–109`. Add `long_chunk`.

    Per-directory sorting may be mentioned as background, but is not an additional required answer fact.

15. **semantic-04**

    **Question:** “Where is each encoded vector checked for dimensionality, and how is that check enforced before batch embeddings are returned?”

    **Rubric:** “`_validate_vectors` checks every vector against `EMBEDDING_DIMENSION` and raises `EmbeddingError` on a mismatch. `embed_texts` invokes this validator before returning the encoded batch.”

    Keep `B:39–46`; expand the caller unit to `B:48–68`.

    Keep two units and `multi_evidence`. Do not require the numeric dimension without adding its definition as evidence.

16. **semantic-05**

    Keep the question and answer.

    Expand evidence to `C:131–194`, covering the fallback guard, empty iteration, no-op companion flush, and final `return chunks`. Add `long_chunk`.

    The original guard alone does not show that the eventual result is an empty list.

17. **semantic-06**

    **Question:** “How does config chunking preserve original blank/comment lines, and when can a whitespace-only group be dropped?”

    **Rubric:** “Line pieces preserve original characters, including line endings, and emitted groups join those pieces without reconstructing text. Comments are non-whitespace and are retained in emitted groups. An entirely whitespace-only file produces no chunks, and a pending group containing only whitespace is discarded when flushed; therefore not every blank character is guaranteed to survive independently of chunk boundaries.”

    Use two units: `T:11–22`; `T:46–76`.

    Add `multi_evidence` and `long_chunk`.

    This qualifies the preservation claim without discarding the useful original-text behaviour.

18. **exact-01**

    **Question:** “Which constant controls the `batch_size` passed to `model.encode`, and what is its value?”

    **Rubric:** “`DEFAULT_BATCH_SIZE` is 32, and `embed_texts` supplies that constant as `model.encode`’s `batch_size`.”

    Keep `B:9–10`; `B:54–62`. Add `backend/tests/test_embeddings.py:26–35` as an alternative supporting the value supplied to the encoder, within the first unit.

    Keep `exact_token` and `multi_evidence`. The test alone does not identify the constant and therefore does not collapse the complete question to one unit.

19. **exact-02**

    Question, rubric, evidence, category and tags are correct. Change HOLDOUT overlap to `NONE`.

    HOLDOUT’s engine/session wiring case does not test `autoflush` or `autocommit`.

20. **exact-03**

    **Question:** “What command is configured under Compose’s `healthcheck.test`, and which database/user does it probe?”

    **Rubric:** “The `CMD-SHELL` healthcheck invokes `pg_isready` using the configured `POSTGRES_USER` and `POSTGRES_DB`.”

    Keep `docker-compose.yml:13–17`. The five-second interval and ten retries may be mentioned, but should not be required answers to this question.

    Retain `exact_token`.

21. **exact-04**

    **Question:** “What values does Settings allow for `LLM_MAX_RETRIES`, including the default and maximum?”

    **Rubric:** “An integer from 0 through 5 inclusive; the default is 2.”

    Keep `Cfg:45–50`. Add `long_chunk`; retain `exact_token`.

22. **exact-05**

    Keep the question.

    **Rubric:** “An async top-level function receives the structural label `async_function`.”

    Keep `C:34–39`; add `backend/tests/test_chunker.py:36–45` as an alternative in the same unit.

    The regular-function and class labels should be optional explanatory detail, not additional required claims.

23. **near-02**

    Content, category and tags are correct. Change DEV1 overlap to `LOW`: DEV1 already distinguishes source-read failures from general source errors, although this candidate asks about a new configuration-file boundary.

24. **near-03**

    Keep the question.

    **Rubric:** “Yes. With an otherwise valid request, an empty query fails `SearchRequest`’s minimum-length constraint. A whitespace-only query satisfies that length constraint, is forwarded through the search route and `search_code`, and is rejected when `embed_query` strips it.”

    Use four units:

    - `Sch:35–40`
    - `Api:82–90`
    - `R:33–49`
    - `B:71–76`

    Retain `multi_evidence` and `distractor`. Do not add `long_chunk`; the new retrieval-function evidence is early.

    The original leading **“No” is incorrect** and contradicts its own explanation.

25. **near-04**

    Keep the question, answer and `Api:64–73`.

    Add `backend/tests/test_api.py:158–190` as an alternative in the same unit. The parametrisation and assertions establish both distinct safe messages and HTTP 400.

    Do not label this a truncation probe.

26. **near-05**

    Keep content, category and tags. Change DEV1 overlap to `NONE`.

    DEV1’s table/vector identity question does not test these nullability constraints. This remains a relatively easy record-disambiguation case, not a claim of demonstrated ranking difficulty.

27. **long-01**

    Keep content, category and tags. Change HOLDOUT overlap to `NONE`.

    Missing AST end metadata is different from the HOLDOUT’s decorator, companion and parse/path-error facts.

28. **long-05**

    **Question:** “What metadata can I use to reproduce an evaluation run and identify its source/model configuration?”

    **Rubric:** “The report records dataset identity/status and hashes, case-set hash, corpus manifest and pinned source revision, repository, application Git revision/dirty status, embedding identity/dimension, resolved model revision and effective limit when available, chunking identifier, candidate depth, context budget and package versions.”

    Tighten evidence to `Ev:612–634`. Change category to `semantic_conceptual`.

    Distinguish the declared corpus source revision from the application’s current Git revision. Do not require optional metadata to be populated in every environment.

29. **mixed-03**

    **Question:** “For an unauthenticated local OpenAI-compatible server, how does `LLM_API_KEY` get from the documented placeholder setting into the created client?”

    **Rubric:** “The example instructs the operator to use the placeholder accepted by that server. `LLM_API_KEY` populates `Settings.llm_api_key`; `_required_llm_config` extracts and strips it; `answer_question` passes the resulting key to `_create_client`; that helper supplies it as the OpenAI client’s `api_key` option.”

    Use five units:

    - `.env.example:9–13`
    - `Cfg:37`
    - `G:70–82`
    - `G:107–122`
    - `G:85–93`

    Retain `mixed_semantic_exact` and `multi_evidence`; add `long_chunk`.

    Do not claim that every local server accepts any arbitrary placeholder.

30. **mixed-04**

    Keep question, answer and evidence.

    Remove `mixed_semantic_exact`; change DEV1 overlap to `NONE`. The question is a conceptual rendering question without a meaningful code-shaped lexical constraint.

31. **mixed-05**

    Keep the question.

    **Rubric:** “A supplied nonblank repository becomes a SQL equality predicate. The service executes that scoped query and returns its rows; zero matching rows do not trigger an unscoped retry.”

    Expand implementation evidence to `R:45–82`. Add `backend/tests/test_retrieval.py:67–78` as an alternative in the same unit.

    Remove `mixed_semantic_exact`; add `long_chunk`, with an explicit annotation that a complete short alternative exists. The original span establishes the predicate but omits execution and the absence of a fallback.

32. **ordinary-01**

    Keep the question.

    **Rubric:** “No. The accepted policy emits top-level classes as class chunks; their methods remain inside those class chunks rather than becoming separate chunks.”

    Keep `C:131–190`. Add `backend/tests/test_chunker.py:10–33` as an alternative, including the assertions that the method text is present inside the class chunk and that no separate method-named chunk exists.

    Do not add `long_chunk`: the implementation is oversized, but its opening docstring already previews the relevant top-level policy.

33. **ordinary-02**

    Keep content, category and tags. Change DEV1 overlap to `NONE`.

    Sharing RAG’s module-level chunk with a context-budget constant does not make this prompt instruction the same fact.

34. **unanswerable-01**

    Keep question, answerability, missing-information rationale and empty gold requirements. Change HOLDOUT overlap to `LOW`, reflecting the related—but distinct—repository-size quota question.

35. **unanswerable-02**

    Keep question, answerability, missing-information rationale and empty gold requirements. Change DEV1 overlap to `LOW`, reflecting the related source-list propagation case.

For the corrected multi-evidence cases, set `one_unit_sufficient=False` and make the rationale describe the independent contributions listed below. Do not retain stale evidence IDs in `oversized_evidence_ids` after replacing or adding units.

**Why the seven rejected cases should leave this pool**

| ID | Rejection reason |
|---|---|
| **multi-06** | Factually valid, but concentrates another question on the same late statistics construction used by multi-02. Three mandatory units also overstate necessity: an API contract test can replace schema-plus-copy requirements. Retain multi-02’s clearer counter-semantics question. |
| **architecture-04** | The vector-extension initializer and SQLAlchemy table initializer are already the complete subjects of DEV1 `path-01` and `path-03`. Combining them does not supply enough new development signal. |
| **near-01** | Reuses multi-03’s module fallback and HOLDOUT `holdout-semantic-03`’s companion behaviour. Also needs a nonempty-AST qualification: “no top-level definitions” alone includes comment-only/empty modules. |
| **long-02** | Uses exactly the completion-validation region retained by multi-08, which adds the meaningful service-to-HTTP relationship. Being late does not justify a second copy. |
| **long-03** | Repeats DEV1 `semantic-01`’s fail-closed discovery behaviour. Late placement is not a new question/evidence relationship. |
| **mixed-02** | Its answer substantially recombines HOLDOUT `holdout-config-03` and `holdout-cross-01`: configurable host port plus local database URL. It is a sensible operational question, but too close to existing validation facts for this new pool. |
| **ordinary-03** | Decomposes the syntax-error branch already required by `holdout-near-02`. Adding the parser-message detail does not sufficiently distinguish the intent and primary evidence. |

`mixed-02` is the closest editorial call among these rejections. Its port-change scenario is useful, but I recommend excluding it under the requested conservative treatment of recombined HOLDOUT facts.

**Multi-evidence audit**

The generator’s 16 proposed cases are not equivalent to 16 independently justified multi-evidence questions.

| Original proposed case | Labelled units | Independent assessment | Recommended result |
|---|---:|---|---|
| multi-01 | 2 | Root normalisation and entry classification are separate functions; both matter | 2 |
| multi-02 | 3 | Counter construction alone answers the revised question; discovery/dispatch overrequired | **1; remove tag** |
| multi-03 | 2 | Fallback representation and database publication are separate functions | 2; extend publication |
| multi-04 | 2 | Storage ordering and HTTP translation contribute different facts | 2 |
| multi-05 | 2 | Original wording largely answerable from app construction | 2 after explicitly asking alias plus use |
| multi-06 | 3 | Schema and route-copy labels are overprescribed; API test can substitute | 2 if resurrected; reject |
| multi-07 | 3 | Existing units contribute different facts, but actual dispatch is missing | **4** |
| multi-08 | 2 | Error creation and translation are meaningfully distinct | 2 after narrowing |
| architecture-01 | 2 | Write-enabled preparation and read-only scoring are separate entry points | 2 |
| architecture-04 | 2 | Extension creation and table creation genuinely differ | 2, but reject for DEV1 duplication |
| semantic-04 | 2 | Original “what happens” wording needs only the validator | 2 after asking enforcement relationship |
| exact-01 | 2 | Constant definition and encoder use are separate chunks | 2 |
| near-03 | 2 | Endpoints of a chain are present; route/service links missing | **4** |
| mixed-01 | 3 | Request field, route forwarding and service forwarding all contribute | 3 |
| mixed-02 | 2 | Environment example and Compose mapping are distinct | 2, but reject for overlap |
| mixed-03 | 2 | Documentation and client option do not establish the handoff | **5** |

Four corrected cases additionally need multi-evidence status:

| Case | Required targets | Units |
|---|---|---:|
| architecture-03 | Corpus validator + its position before case searches | 2 |
| architecture-05 | Module-level environment path + Settings use | 2 |
| semantic-02 | Empty-context construction + provider-call continuation | 2 |
| semantic-06 | Original line-piece construction + grouping/flush behaviour | 2 |

This yields **16 genuinely justified multi-evidence cases after correction**. The equality with the original advertised count is coincidental.

These counts use meaningfully separate accepted chunks. Nested helpers within `chunk_python_file`, `chunk_config_file` or discovery are not counted as separate retrieval targets merely because they occupy different line spans. Alternative implementation/test evidence remains inside its corresponding unit.

**Long-chunk and truncation audit**

The cached sentence-transformer configuration establishes an effective sequence limit of **256 tokens**. The tokenizer’s own larger generic maximum is not the encoder’s effective limit. With the two special tokens, approximately **254 content tokens** remain.

The following are offline token counts of frozen accepted source chunks, not model inference or retrieval measurements:

| Key | Accepted chunk identity | Tokens, including special tokens |
|---|---|---:|
| L | `repository_loader.py`, function `discover_python_files`, 66–109 | 392 |
| S | `storage.py`, function `index_repository`, 46–89 | 384 |
| C | `chunker.py`, function `chunk_python_file`, 102–194 | 776 |
| I | `api/routes.py`, function `index_local_repository`, 53–79 | 288 |
| K | `config.py`, class `Settings`, 15–60 | 561 |
| G | `rag.py`, function `answer_question`, 96–142 | 436 |
| A | `api/routes.py`, function `ask_repository`, 97–122 | 283 |
| V | `evaluation.py`, function `validate_corpus_manifest`, 227–262 | 368 |
| E | `evaluation.py`, function `evaluate_dataset`, 516–643 | 1,282 |
| T | `text_chunker.py`, function `chunk_config_file`, 25–76 | 449 |
| R | `retrieval.py`, function `search_code`, 33–82 | 458 |
| RT | `tests/test_rag.py`, context-bound test, 32–62 | 268 |

The generator’s **26 cases / 32 units** were reproducible under its symbol-containment diagnostic. Actual span intersection adds **architecture-05**, giving **27 cases / 33 units**: its original span crosses the module companion and Settings class and was missed by that diagnostic.

All original oversized/intersecting cases are assessed below. Positions are approximate one-based **content-token** positions; ranges describe the relevant region, not an assertion that every token in the range is needed.

| Case | Oversized location and evidence position | Independent truncation assessment |
|---|---|---|
| multi-01 | L; key no-follow checks around 193 and 235 | Core distinction fits in prefix |
| multi-02 | S; statistics around 330–382 | Meaningful late counter evidence |
| multi-03 | C around 292–440; corrected S includes commit around 254–290 | Meaningful late/boundary evidence |
| multi-04 | S around 87–329; I around 212–268 | Guard early, ordering/translation proof crosses boundary |
| multi-05 | K around 147–176 | Not a truncation probe; short `.env.example` alternative |
| multi-06 | S around 330–382; I response copy around 269–286 | Late, but redundant and rejected |
| multi-07 | L branch around 231–323; C read around 141–202 | Configuration-specific admission extends beyond prefix |
| multi-08 | G around 349–434; A around 144–195 | Service check late; HTTP evidence early |
| architecture-03 | V; final identifier check around 303 | Meaningfully late; added caller evidence is early in E |
| architecture-05 | K use near the beginning | Physical intersection only; original unit also unmatchable |
| semantic-01 | Primary `build_context` is 250 tokens; RT assertions around 231–254 | Complete short primary; oversized test does not create meaningful truncation |
| semantic-03 | L final sort around 371–390 | Meaningfully late |
| semantic-05 | C guard starts around 292; complete outcome later | Meaningfully late |
| semantic-06 | T grouping/flush region around 220–445 | Guard crosses boundary; join/flush logic later |
| exact-04 | K around 394–432 | Meaningfully late |
| near-01 | C around 292–647 | Late, but rejected for redundancy |
| near-02 | T around 67–208 | Relevant distinctions fit in prefix |
| near-04 | I around 104–167 | Relevant distinctions fit in prefix |
| long-01 | C around 643–765 | Strong late implementation location |
| long-02 | G around 349–434 | Strong late location, but duplicate |
| long-03 | L around 324–359 | Strong late location, but DEV1 duplicate |
| long-04 | K around 353–393 | Strong late constraint location |
| long-05 | E originally around 890–1,280; corrected span around 910–1,179 | Strong late report-construction location |
| mixed-01 | A around 1–75; G around 1–128 | Both forwarding facts fit in prefixes |
| mixed-05 | R original around 126–316; corrected proof extends through return | Late implementation, but complete short test alternative |
| ordinary-01 | C body around 292–767 | Opening docstring previews top-level policy; not a clean truncation test |
| ordinary-03 | C around 203–291 | Straddles boundary, but rejected for HOLDOUT overlap |

The edits introduce additional oversized relationships:

- **semantic-02:** provider-call evidence in G is around 198–309; the completion call begins near the content boundary.
- **mixed-03:** `LLM_API_KEY`’s Settings alias is around 291–321. Its caller span in G is early.
- **near-03:** the added `search_code` unit is in an oversized function, but its relevant embedding call is early. No long tag is justified.

Alternative evidence changes the interpretation:

- `build_context` is **250 tokens**: semantic-01 has a complete short implementation target.
- The new mixed-05 test is **137 tokens** and completely supports the no-global-fallback behaviour.
- The class/method test added to ordinary-01 is **336 tokens**, with decisive assertions late; nevertheless the implementation’s early docstring already previews the policy.
- The near-04 test is **260 tokens**, but its decisive assertions are around 226–249 and fit.
- The malformed-completion test is **264 tokens** and covers no choices, not the entire no-choices-versus-empty-content distinction.
- The discovery-classification test is **240 tokens**, but asserts the base repository-path error, not the exact `RepositoryReadError` subclass. It is partial corroboration for long-03, not a complete equivalent for its exact-class rubric.

The five deliberately late cases therefore resolve as follows:

| Case | Decision | Reason |
|---|---|---|
| long-01 | Edit metadata, retain | Late guard is real; useful, though somewhat artificial defensive-invariant diagnostic |
| long-02 | Reject | Late position does not justify duplicating multi-08 |
| long-03 | Reject | Late position does not erase DEV1 duplication |
| long-04 | Accept | Real operator constraint, genuinely late |
| long-05 | Edit, retain | Real late metadata; correct category and qualify optional values |

After edits, **25 retained cases have at least one oversized acceptable location, across 32 required units**. That is distinct from the **16 recommended `long_chunk` cases**:

`multi-02`, `multi-03`, `multi-04`, `multi-07`, `multi-08`, `architecture-03`, `semantic-02`, `semantic-03`, `semantic-05`, `semantic-06`, `exact-04`, `long-01`, `long-04`, `long-05`, `mixed-03`, `mixed-05`.

Of these, mixed-05 has a complete short alternative. For the other 15, this audit did not identify a complete short alternative covering the revised implementation requirement. This is a source-position finding—not proof of retrieval failure or a claim that truncated embeddings cannot retrieve the chunk.

**Mixed semantic/exact and distractor quality**

Only two retained cases merit `mixed_semantic_exact`:

- **mixed-01:** the `/ask` route term identifies a concrete API boundary, while the question requires understanding repository-scope propagation.
- **mixed-03:** `LLM_API_KEY` identifies the configuration channel, while the question requires understanding documentation, validation and client construction.

`mixed-02` is genuinely mixed in form but rejected for overlap. `mixed-04` and `mixed-05` are ordinary conceptual questions; prose mentioning source identity or scoped search does not itself justify the tag.

The retained distractor cases have defensible competing concepts:

| Case | Useful competition | Why the gold is preferred |
|---|---|---|
| near-02 | Python versus configuration path/read handling; general versus read-specific source error | The question specifies config chunking and distinguishes outside-root from read failure |
| near-03 | Schema string length, repository-scope normalisation, and query whitespace validation | The field is `query`, and the question asks about two actual validation stages |
| near-04 | Service error creation versus HTTP error translation | The question asks for client-facing messages, making the route or its test decisive |
| near-05 | Parsed/API records versus stored ORM constraints | “Stored” and nullability point to the database model |

Near-03 and near-04 are the strongest ordering diagnostics. Near-05 is useful but comparatively easy. No measured difficulty is asserted.

**Independent audit of the two unanswerable cases**

| Case | Plausibility and inspected areas | Absence finding | Remaining uncertainty |
|---|---|---|---|
| **unanswerable-01** | A developer may reasonably seek a per-file resource limit before indexing a large repository. Inspected frozen discovery, Python reading/parsing, storage orchestration, Settings, entry points, documentation and repository-wide size-limit references. | No configured/enforced maximum byte size per individual Python source file was found. Python source is read in full. The config discovery sample, config chunk character cap and embedding input limit are different mechanisms. | External OS/container limits could exist outside the repository, but would not answer this repository implementation question. |
| **unanswerable-02** | A developer may reasonably ask whether answer citations are checked before trusting them. Inspected context construction, system prompt, full answer-generation path, response schemas, `/ask` serialisation and citation/validation references. | No post-generation parser or validator checks answer-text file citations against returned sources. The backend checks completion shape/content and returns generated text plus the context’s source list. Prompt instructions and source-list propagation are not citation validation. | A provider could behave conservatively, but that is not a repository-implemented validation step. Future evaluation discussion is not runtime enforcement. |

Both negatives are defensible at the frozen revision. They should remain `source_answerable=false` with no invented positive evidence units.

**DEV1, HOLDOUT and within-DEV2 overlap**

My independent overlap distribution differs from the automatic diagnostic:

| Comparison | NONE | LOW | MATERIAL |
|---|---:|---:|---:|
| All 45 vs DEV1 | 18 | 25 | 2 |
| All 45 vs HOLDOUT | 27 | 16 | 2 |
| Recommended 38 vs DEV1 | 18 | 20 | 0 |
| Recommended 38 vs HOLDOUT | 23 | 15 | 0 |

The material overlaps are:

- **architecture-04 → DEV1 `path-01` + `path-03`:** complete database-initialisation facts recombined.
- **long-03 → DEV1 `semantic-01`:** the same fail-closed discovery intent and error branch.
- **mixed-02 → HOLDOUT `holdout-config-03` + `holdout-cross-01`:** port mapping and local connection-target facts recombined.
- **ordinary-03 → HOLDOUT `holdout-near-02`:** the same syntax-error location branch, extracted into a narrower question.

Important retained distinctions include:

- **multi-08:** HOLDOUT already asks about provider-failure HTTP status, but DEV2 adds a concrete completion-validation trigger and its translation.
- **multi-07:** HOLDOUT covers configuration sampling; DEV2 asks the different Python-versus-config admission/decoding relationship.
- **near-03:** HOLDOUT covers blank repository scope; DEV2 covers empty versus whitespace-only **query** across schema and embedding validation.
- **exact-04 / long-04:** DEV1 covers settings-to-client wiring; these ask validation bounds, not that wiring.
- **unanswerable-01:** per-file admission limits and per-repository quotas are related but independently implementable policies.

Within DEV2, the strongest redundancies are removed:

- `multi-02` / `multi-06`: statistics construction.
- `multi-08` / `long-02`: identical completion-validation region.
- `multi-03` / `near-01`: module fallback, with near-01 also recycling HOLDOUT companion behaviour.

Some retained clusters remain correlated:

- `semantic-01` / `semantic-02`: selection behaviour versus no-context generation policy.
- `multi-03` / `semantic-05` / `ordinary-01` / `long-01`: fallback publication, comment-only emptiness, class granularity and missing metadata.
- `exact-04` / `long-04`: adjacent retry/timeout bounds in Settings.
- `architecture-02` / `architecture-03` / `architecture-06`: manifest construction, corpus preflight and dataset repository consistency.

These are different facts, but successes on them should not be interpreted as independent evidence of broad module coverage.

**Dataset-level assessment and recommended composition**

Every retained source location is **eligible under the accepted indexing policy**. There is no DEV2 frontend/out-of-allowlist problem analogous to the earlier source-coverage challenge. This is a static eligibility judgment; I did not query a database to verify actual indexed membership.

The main representation defect is architecture-05’s original cross-chunk unit, corrected above.

The recommended category distribution is:

| Category | Original 45 | Recommended 38 |
|---|---:|---:|
| semantic_conceptual | 14 | 15 |
| architecture | 7 | 3 |
| cross_module_behavior | 7 | 4 |
| configuration_constants | 5 | 6 |
| difficult_near_matches | 5 | 4 |
| multiple_required_evidence | 4 | 3 |
| exact_identifier | 1 | 1 |
| unanswerable_insufficient_context | 2 | 2 |
| **Total** | **45** | **38** |

The corrected set contains:

- **36 answerable / 2 unanswerable**
- **16 genuinely multi-evidence**
- **16 meaningfully long-position-related**, including one with a complete short alternative
- **60 required evidence units**
- **70 acceptable spans**, counting alternatives separately
- **24 distinct evidence files**, including added test alternatives

The important tag counts are:

| Tag | Count |
|---|---:|
| `multi_evidence` | 16 |
| `long_chunk` | 16 |
| `exact_token` | 5 |
| `distractor` | 4 |
| `failure_boundary` | 4 |
| `later_source` | 3 |
| `provider_config` | 3 |
| `repository_scope` | 3 |
| `mixed_semantic_exact` | 2 |
| `context_selection` | 2 |
| `evaluation_safety` | 2 |
| `ordinary_developer_question` | 2 |
| `reproducibility` | 2 |
| `unanswerable` | 2 |

Other retained topical tags each occur once. Remove `early_source` from multi-04 and `across_long_chunks` from multi-08; add `boundary_crossing` to multi-04. Preserve the three surviving original `later_source` tags on long-01, long-04 and long-05.

Concentration remains material:

- RAG evidence appears in **7** retained cases.
- Python chunker evidence appears in **6**.
- Routes and Settings each appear in **5**.
- Storage and evaluation code each appear in **4**.
- Five cases directly concern evaluation infrastructure: architecture-01, architecture-02, architecture-03, architecture-06 and long-05.

Semantic cases increase to **15/38, or 39.5%**, because several “architecture” labels were overstated. That is acceptable for DEV2; relabelling weak architecture questions honestly is preferable to maintaining artificial symmetry.

The pool mixes ordinary configuration/schema questions with stronger relationship questions. Its best new development signal comes from dispatch, validation-stage differences, error creation-to-translation, configuration handoffs and empty-context orchestration. It is backend-heavy and concentrated on the application’s retrieval/indexing machinery. It should be described accordingly, not as representative of general full-stack codebase Q&A.

**Final IDs**

**A. ACCEPT unchanged — 3**

`dev2-semantic-01`, `dev2-long-04`, `dev2-mixed-01`.

**B. EDIT, then accept — 35**

- `dev2-multi-01`, `dev2-multi-02`, `dev2-multi-03`, `dev2-multi-04`, `dev2-multi-05`, `dev2-multi-07`, `dev2-multi-08`
- `dev2-architecture-01`, `dev2-architecture-02`, `dev2-architecture-03`, `dev2-architecture-05`, `dev2-architecture-06`
- `dev2-semantic-02`, `dev2-semantic-03`, `dev2-semantic-04`, `dev2-semantic-05`, `dev2-semantic-06`
- `dev2-exact-01`, `dev2-exact-02`, `dev2-exact-03`, `dev2-exact-04`, `dev2-exact-05`
- `dev2-near-02`, `dev2-near-03`, `dev2-near-04`, `dev2-near-05`
- `dev2-long-01`, `dev2-long-05`
- `dev2-mixed-03`, `dev2-mixed-04`, `dev2-mixed-05`
- `dev2-ordinary-01`, `dev2-ordinary-02`
- `dev2-unanswerable-01`, `dev2-unanswerable-02`

Of these, **exact-02, near-02, near-05, long-01, mixed-04, ordinary-02, unanswerable-01 and unanswerable-02** need only tag/overlap metadata changes. Their questions and evidence do not need rewriting.

**C. REJECT — 7**

`dev2-multi-06`, `dev2-architecture-04`, `dev2-near-01`, `dev2-long-02`, `dev2-long-03`, `dev2-mixed-02`, `dev2-ordinary-03`.

**D. Source-coverage challenge transfers — none**

No retained case needs separation because of an unsupported source type.

**Remaining human judgments**

The principal editorial judgments are whether to tolerate mixed-02’s recombination of HOLDOUT facts, whether the defensive AST-metadata question long-01 merits its diagnostic slot, and how much weight to assign correlated Settings/chunker questions. My recommendation is to exclude mixed-02 and retain the other distinct diagnostics with the qualifications above.

Actual retrieval difficulty, current database membership and model sensitivity to late evidence remain deliberately unmeasured. Once the proposed edits are applied by a separate implementation step, the revised dataset should receive a new canonical hash and another source/annotation consistency check.

**No DEV2 retrieval, reranking or retrieval-metric evaluation was run. No project files were changed. No commit or push was performed. DEV2 was not finalised or frozen.**