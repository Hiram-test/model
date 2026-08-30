# GitHub publication error log

## E-GH-PUBLISH-001 — branch search argument mismatch

- Date: 2026-08-30 UTC.
- Action: read-only search for an existing result branch.
- Error: the first connector call used `repository_full_name`/`first`; the action required `owner`/`repo_name`/`page_size`.
- Impact: no repository mutation occurred.
- Resolution: read the exact action contract and repeated the search with the required arguments; no matching branch existed.

## E-GH-PUBLISH-002 — pull-request search argument mismatch

- Date: 2026-08-30 UTC.
- Action: read-only search for an existing CCX result pull request.
- Error: the first connector call used `top_k`; the action required `topn`.
- Impact: no repository mutation occurred.
- Resolution: repeated the search using `topn`; no matching pull request existed.

## E-GH-PUBLISH-003 — anonymous HTTPS dry-run cannot authenticate

- Date: 2026-08-30 UTC.
- Action: `git push --dry-run` from a filtered local clone.
- Error: the local Git transport had no interactive username/token and stopped before any ref update.
- Impact: no branch, commit or repository object was changed.
- Resolution: publish through the authenticated GitHub connector using Git blobs, a single tree, one commit, one branch ref and a draft pull request.

## E-GH-PUBLISH-004 — checksum audit launched from the wrong directory

- Date: 2026-08-30 UTC.
- Action: pre-publication `sha256sum -c` review.
- Error: the first review command ran above the staging root although the ledger paths are relative to that root, so all entries were reported missing.
- Impact: read-only command failure; no file or repository mutation occurred.
- Resolution: reran the check from the staging root and then regenerated the public-copy checksums after sanitization.

## E-GH-PUBLISH-005 — initial unreferenced commit superseded by public-copy audit

- Date: 2026-08-30 UTC.
- Action: assembled Git blobs, tree and commit before creating the publication branch.
- Finding: the independent audit identified private conversation text and ephemeral absolute runtime paths in the proposed public view.
- Impact: commit `25df8b70bca88685e564482d60803ff6f5f939e8` was created as an unreferenced Git object; no branch or pull request pointed to it.
- Resolution: stopped before ref creation, removed conversation text, normalized runtime paths, clarified model identity and rebuilt the checksum ledger for a new sanitized commit.

## E-GH-PUBLISH-006 — checksum ledger patch attempted delete-and-add in one operation

- Date: 2026-08-30 UTC.
- Action: replace the public-copy `SHA256SUMS.txt` after path normalization.
- Error: the patch engine rejected a single patch containing both delete and add operations for the same path.
- Impact: local patch validation failure only; the existing ledger remained unchanged and no repository ref existed.
- Resolution: replaced the ledger through one full-file update hunk and reran every checksum.
