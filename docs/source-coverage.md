# Source coverage experiment

This batch changes source representation only. The embedding model, normalization,
exact cosine ranking, candidate depths, context selection, and evaluation gold
evidence stayed fixed. Improved coverage therefore means evidence *can* be indexed;
it does not imply that dense retrieval will rank it well.

## Python companion policy

Top-level functions, async functions, and classes retain their existing exact source
chunks, including decorators. If at least one such symbol exists, consecutive
top-level AST statements outside those symbols are grouped until the next symbol and
emitted as `module_companion`. Imports, assignments, constants, construction,
expressions, and conditional setup are therefore represented without joining regions
across a symbol. Comment/whitespace-only gaps do not create chunks. Modules without a
qualifying symbol retain the existing whole-module fallback.

All Python chunks are exact contiguous slices of the original file. Line ranges come
from AST locations and original source lines; `ast.unparse()` is not used.

## Config-text policy

Four missing evaluation facts justified a narrow allowlist:

- `docker-compose.yml`: the pgvector PostgreSQL image and tag;
- `docker/postgres/init.sql`: vector extension initialization;
- `frontend/vite.config.ts`: the development `/ask` proxy;
- `.env.example`: documented LLM timeout/retry configuration.

YAML/YML and SQL extensions, `.env.example`, and specifically `vite.config.ts` are
accepted as UTF-8 config text. They are greedily split into deterministic contiguous
chunks no larger than 4,000 characters. General TypeScript, `.env`, Markdown, TOML,
other text formats, binaries, and generated/vendor directories remain unsupported.

## Measured result

The same 40 evidence units were evaluated at candidate depth 10. Gold questions and
evidence identities were unchanged; four source spans were moved only to follow their
same definitions after source edits.

| Metric | Before | After |
|---|---:|---:|
| Index evidence coverage | 33/40 (82.50%) | 40/40 (100.00%) |
| All evidence indexed | 29/36 (80.56%) | 36/36 (100.00%) |
| Hit@10 | 29/36 (80.56%) | 31/36 (86.11%) |
| Micro evidence recall@10 | 32/40 (80.00%) | 31/40 (77.50%) |
| Final-context evidence recall | 32/40 (80.00%) | 31/40 (77.50%) |
| Context sufficiency | 28/36 (77.78%) | 28/36 (77.78%) |
| Selection loss | 0/32 (0.00%) | 0/31 (0.00%) |
| Indexed chunks | 118 | 212 |
| Chunks above 256 tokens | 23/118 (19.49%) | 35/212 (16.51%) |

Coverage reached 100%, but retrieval did not improve uniformly: five answerable cases
gained evidence at depth 10, five lost evidence at depth 10, and 26 were unchanged.
This is the intended diagnostic separation: a larger candidate corpus can expose new
facts while also changing dense-vector competition.

Oversized symbols were deliberately not split. The largest observed chunk increased
from 588 to 1,282 tokens, and six evaluated evidence units had at least one required
content anchor beyond the effective 256-token boundary. Chunk-size policy is a later,
separate experiment.
