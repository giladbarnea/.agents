---
name: "open-source-contribution-attitude"
description: "A description of my preferred approach to opening a PR in a project where I’m a guest."
---

**I bring proof without presuming permission.**

I start as a grateful user with a concrete problem, not as someone correcting the maintainer. I explain what improves the experience and why, while presenting personal preferences as preferences.

Then I show working code, a recording, and tests. That makes the proposal concrete and reduces the maintainer’s work to assess it. **But my investment does not become a claim on their time or their roadmap.** I open the issue and a ready PR together, so the maintainer has one thing to act on: approve, reject, comment, or review.

I also put the experience first and keep implementation details available but secondary. When the maintainer raises a concern, I explain the tradeoff, offer options, and leave the decision with them.

How I write it:

- If an issue already covers the problem, I comment there. I open a new issue only if my solution is materially and directly better than the one discussed there. Example: an issue on slow loads discussed compression; my fix was several times better because it took a fundamentally different approach. Then I acknowledge the existing issue in one understated phrase ("Same cause as #926, where a load takes seconds on loopback.") and do not justify the choice.
- I understate. I show rather than tell, do not try to convince, and let subtext carry the intent. No intensifiers ("fast", "deep"). I offer to align rather than inviting closure: "If another direction fits better, I'm happy to align, please let me know."
- Verification opens with my own hands-on test, side by side with the unmodified version, end to end, marked "I (human) manually tested…".
- I disclose AI plainly, in one line with the model names ("Used Opus 5.5 xhigh in this work."; "A GPT-6 Astra thinking=max review found…"). No tool branding and no session links, in commit messages too.
- The PR title carries the headline result, e.g. "(12x improvement)".
- Each post opens with thanks, a longer line on one and a short one on the other. Minimal, not supplicant: "Thanks for Plannotator. I use it daily and it makes my life easier." and "Thanks for Plannotator."
- Bold paragraph openers end with a colon ("**The cause:**"). Paragraphs have about 2–3 not-long sentences. Verbs are literal, not metaphors ("takes", not "costs").
- I ground the problem in my real setup: device, network, and how I use it ("iPhone 17 Air", "even on 5G", "with `--tailscale`").
- Nothing goes upstream before I review the drafts, even after I say "create a PR".

The attitude is: **“I care about this, I did the work, and I would like to contribute. It is still your project.”**

Real example: https://github.com/juicesharp/rpiv-mono/issues/150
