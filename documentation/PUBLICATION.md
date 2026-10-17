# Public-source publication boundary

Reviewed on 17 October 2026. Only the files listed in publication-manifest.json are approved by this local review. The manifest records normalized UTF-8 SHA-256 hashes so that additions and edits require a fresh review.

The reviewed set contains application code, generic worksheet schemas, public dependency references, user instructions, and synthetic test/demo data. No personal records, identified people, contact details, identity documents, credentials, private endpoints, or confidential business datasets were identified. Historical plans, local review notes, spreadsheets, exports, screenshots, archives, local settings and dependency/build directories are excluded. Existing local private files are preserved.

C4 is treated here as highly confidential information. No organization-specific classification policy was provided; this review is not a formal C4 compliance certification. Pattern checks and manual inspection cannot prove the absence of all sensitive information.

## Verify before publication

From the repository root, run:

```powershell
python scripts/check_publication.py
```

After staging the intended files, run:

```powershell
python scripts/check_publication.py --staged
git diff --cached --stat
git diff --cached
```

Both publication checks must pass. Do not regenerate the manifest simply to bypass a changed-file failure: inspect the changes for sensitive information first. Do not force-add excluded files. The checker detects tracked files even when ignore rules would otherwise hide them. It checks index contents in staged mode, including rejecting symlinks/submodules.

This local checkout had no commits, tracked files or configured remotes at review time. Before making a commit, configure a public-safe Git author name and a GitHub-provided private commit email; commit metadata can otherwise disclose personal information even when file contents are clean. Remote repository settings, remote history, release uploads and GitHub account metadata are outside this file review.

Publish source through Git, never upload the entire workspace folder. A static-site deployment must publish only a freshly built static-dashboard/dist directory and must not copy private inputs there. Build dependencies and hosting require separate security validation. The Python service has no application authentication and must not publicly serve real financial records.

Validation: candidate text and literal/endpoint review, secret/PII pattern scanning, workbook archive inspection, ignore checks, and 18 passing frontend unit tests. The publication checker also rejects an added unreviewed probe file in a negative check.
