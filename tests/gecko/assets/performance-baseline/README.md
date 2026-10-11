These are the immutable production observation assets from 1.5.16 (`835d59991218eda70c7a4fdd73ea9d7ae6052688`).
The real Gecko performance integration test loads them only in the `.test` package
and compares them with current assets on controlled loopback documents.
They must never be added to production assets or invoked against real accounts.
`source.json` records byte counts and SHA-256; changing the baseline requires an explicit review.
