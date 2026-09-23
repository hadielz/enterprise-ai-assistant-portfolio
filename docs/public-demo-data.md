# Public Demo Data Policy - R4

The public Portfolio v1.0 repository uses **synthetic reference organization data**.
It must not contain personal test personas or document metadata that could be
mistaken for a real employee/author.

## R4 cleanup

- authentication normalization examples use synthetic `demo-*` personas;
- database model examples use synthetic identifiers;
- `data/documents/ai_agent_policy.pdf` retains its visible generic policy content
  but its Author/Creator metadata is synthetic;
- the PDF visual rendering was compared before/after metadata sanitation and the
  page content did not change.

## Automated guard

`python scripts/security/repository_guard.py` checks:

- common private-key/provider/GitHub-token shapes in public text files;
- every PDF in `data/documents` has empty or explicitly synthetic Author and Creator metadata.

This is intentionally a repository release guard, **not** a DLP product.

## R4 acceptance

The final repository guard was executed from the bounded backend container and
returned:

```text
Public repository guard passed.
```

The source/docs/demo-assets review and the sanitized PDF metadata review were also
completed during R4 integration. No release-blocking personal/demo-data issue
remained.

**Result: PASS.**