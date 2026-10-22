---
name: Local report export
description: Decisions for SilverPaws beta PDF exports and report language
---

The beta's report download should remain dependency-free and work from the local browser state. Keep saved raw measurements visibly separate from plain-language interpretation, and preserve experimental/no-diagnosis language plus source and licensing metadata when available.

**Why:** The beta is local-first and may be used offline; report recipients also need to distinguish measured values from cautious interpretation.

**How to apply:** Extend the existing browser-side report builder when adding report fields or sections. Do not silently turn missing source or licensing data into an attribution claim.