# Independent review of evidence JSON top-level key guard

Review time: 2026-10-04 Asia/Taipei. Scope: read-only independent review; evidence files only. Token usage source unavailable. No product, guard, project documentation, or host registration was edited.

## Verdict

Request narrow fixes before approval. The original literal missing `cases` access is denied and valid `manual_cases` is allowed by actual manual hook invocation. Existing focused tests pass (75 tests, zero failures), but three new executable counterexamples demonstrate false rejection after dictionary mutation. Automatic host integration was not verified.

## Version and evidence

Reviewed guard SHA256: 79d0448cf7cde6575ddce041f26c4ed7108cb7cf72627ebc5985b241100d3610. Existing modules run: `python3 -m unittest test_evidence_json_key test_fluke_evidence_path test_markdown_prose test_checkpoint_prose test_guards -v` from `/home/cash/.agents/guards`. Output: `independent-tests.log`.

`independent-review-cases.py` and `independent-review-cases.json` retain ten complete semantic payloads, two actual manual hook results, three actual standalone read-only executions, and seven boundary observations. These evidence files describe the reviewed version; a later author fix must receive a separate versioned readback.

## Confirmed findings

1. Alias mutation: `e=d;e.update({'cases':[]});print(d['cases'])` succeeds (exit 0) but is denied. Invalidating `e` alone does not invalidate tracked `d`.
2. Keyword mutation: `mutate=lambda data:data.update({'cases':[]});mutate(data=d);print(d['cases'])` succeeds but is denied. Only positional call arguments are invalidated.
3. Same-expression mutation: the same lambda followed by `print(mutate(d),d['cases'])` succeeds but is denied. Subscript checking runs before unknown call invalidation across the statement.

Each example loads the actual existing JSON artifact and mutates only its in-memory dictionary. No source or artifact write is executed by these cases. Reported to the assigned guard author for a narrow invalidation fix.

## Scope and bounds

Literal imported `Path` / `pathlib.Path`, slash joins, imported `json.loads`, and string top-level loaded subscripts are recognized. Dynamic paths/keys, nested inference, control flow and unknown representations stay outside this narrow rule. Reassignment, direct subscript assignment, ordinary positional mutation and module rebinding controls passed. Commands containing recognized writes are skipped by the JSON rule.

Resolved paths must be under `~/.agents/evidence` or the fixed Fluke workspace's `docs/superpowers/evidence` subtree, and end in `.json`. Mocked exact symlink escape and root prefix collision were excluded. This proves the resolver condition with controlled inputs, not real symlink deployment behavior or a race-free filesystem guarantee.

Observed bounds: command length over 65536 characters skipped; recognized read budget stops inspection after 16 (Fluke reads can count twice, a conservative smaller coverage window); file stat size above 1048576 skipped; read is limited to 1048577 characters; malformed and nonobject JSON skipped. Seven boundary cases passed. Nonregular files are not rejected before `open`; therefore byte limits alone do not prove a wall-time bound if an allowed evidence path is a FIFO or blocking special file. No potentially blocking file was opened during review. The rule also measures command character length rather than encoded bytes. These limitations must not be described as a universal bounded JSON parser.

## Original prose rule

Current `SIMPLIFIED_PROSE` remains active and both related test modules pass. An independent pre-change source snapshot was not available in this review's discovered evidence; the baseline whole-file SHA alone cannot prove that constant unchanged. Historical exact comparison is pending the guard author's snapshot check, and is not claimed here.

## Acceptance boundary

This is manual hook and local test evidence only. It does not establish automatic invocation by the host, registration across applications, or enforcement of all Python JSON accesses. Preserve existing prose checks and root restrictions; apply no broad inference or tooling expansion to resolve the three findings.
