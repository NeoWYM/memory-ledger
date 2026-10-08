---
name: alpha-migration
description: Move the sample batch job to the new scheduler
metadata:
  node_type: memory
  type: project
  status: observing
  observe_until: 2026-03-10
  checkpoints:
    - 2026-03-12 | confirm the nightly run succeeded
    - 2026-03-15 | compare run time against the old scheduler
    - 2026-04-01 | decide whether to retire the old scheduler
---

See [[reference_glossary]] for terms.
