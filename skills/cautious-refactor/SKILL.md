---
name: cautious-refactor
description: How to know when to refactor on-the-go
---

If you hit a design or architecture issue that’s causing real friction for you, and reworking it: (1) would not become a project in and of itself, and (2) would not introduce risk for breaking something, then go ahead and refactor it. I’d rather your do that than performing acrobatics to work around a past design decision that no longer helps anyone. And remember: find what to remove before you add. Find what complexity or redundancy to collapse before you abstract. Tree-shake the current design/implementation.
