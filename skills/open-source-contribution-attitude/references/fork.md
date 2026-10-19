# Create and maintain forks

Fork maintenance has two directions: upstream changes we must handle, and our changes we must manage. A fork can be ahead and behind simultaneously. Apply this classification to every fork and every link in a fork chain.

The goal is to preserve wanted behavior while minimizing the custom code we maintain. Prefer upstream implementations when they provide equivalent or better guarantees.

## Define each node before triage

Create a root `FORK.md` whenever creating a fork, including a fork of another fork. Each node we control must declare:

1. **Purpose and justification:** what the node serves and why it needs to exist separately from its parent.
2. **Responsibility boundary:** what belongs here, what belongs in the parent, and what belongs in downstream nodes.
3. **Place in the chain:** its parent and known children, with repository URLs, local paths where applicable, and references to their root documentation.

Read these boundaries across the chain before routing a change. Triage depends on declared responsibilities, not assumptions based on the current checkout.

### Keep chain references bidirectional

In root Markdown documentation, reference both up and down the chain. Use `FORK.md` as the default home. Each child identifies its parent, and each parent we control identifies its known children.

Repeat the chain map where needed, even at the cost of duplication. An agent must be able to discover the surrounding chain from any node. Keep duplicated maps and relationship references aligned when creating, moving, or retiring a node. Do not require changes to an external upstream's documentation.

## Categories and protocols

| Category | Meaning | Protocol |
|---|---|---|
| **Intentional product drift** | Behavior we deliberately want to differ from upstream. | Preserve the behavior in the repository whose product boundary requires it. Deliberately excluded upstream features are not missing updates. |
| **General improvement** | A reusable capability upstream would reasonably want too, independent of our product domain. | Put it as far up our chain as we control. Consider an upstream contribution. Replace our implementation when upstream supplies equivalent or better behavior, even if the implementation differs. |
| **Bug fix** | A correction to a defect in upstream's own behavior. | Follow the general-improvement protocol. |
| **Unfortunate necessity** | A difference we accept only because it currently enables behavior that serves our intentional product drift. | Record which intentional product drift it supports and what would make it unnecessary. Keep it easy to remove down the road should opportunity arise. Remove it when another solution preserves the wanted behavior without this difference. |
| **Behind upstream** | Relevant upstream work we have not adopted. | Fetch and compare the selected code. Prefer alignment and adoption of upstream over custom code. Explain a larger migration before proceeding. Already-merged upstream fixes are not personal drift. |
| **Undocumented drift** | A difference whose reason we have not established. | Suspect an accident. Ask Gilad whether he knows about it, then classify it or get his decision. Do not silently preserve it. |

Undocumented drift is a temporary category. Its protocol ends by assigning a known category or removing the difference.

### Unfortunate necessity supports intentional product drift

**The product difference is wanted. The extra drift needed to support it is not.** This is not simply another name for every improvement or fix we hope upstream will adopt.

For example, tool-output-kit's `read_many_files` should use vstack's appearance. Vstack exposes no registration API for that personal tool, so the vstack fork carries `vstack-fork-read-many-files.ts`.

The adapter is an unfortunate necessity. Remove it when another solution lets the personal tool own its renderer while using vstack's style. The replacement need not be a particular upstream fix.

## Route and complete the work

Shared improvements move up. Intentional product drift belongs to the product whose boundary requires it. The repository where an agent starts does not determine ownership.

1. Before implementing, classify the change and identify its owning repository. Confirm both with Gilad.
2. Check current upstream before building. Adopt an existing solution rather than duplicate it. Preserve intentional product behavior on top where needed.
3. Check further up our fork chain too. Merge an existing capability down, or deploy it if production alone is behind.
4. Build general improvements and bug fixes in the highest repository we control. Move misplaced ones up from downstream repositories.
5. Record each difference in its owner's drift log using the project's ID convention. Include what, why, affected code, and links to related drift.
6. Propagate verified work down the chain. Get authorization before reaching production. Follow the project's verification and deployment protocol.
7. Finish every affected repository's commit and push obligations. Keep logs true and report the category and chain-wide Git state. Public contributions still require Gilad's draft review.

## Revisit existing drift

At each upstream sync, check our general improvements and bug fixes against current upstream. When upstream replaces one, adopt its implementation, delete ours, and mark the entry retired with the date and upstream commit.

Revisit unfortunate necessities against their removal conditions. Preserve the wanted product behavior, not an obsolete adapter or workaround.

Upstream contributions are a lower-priority route to retiring general improvements and bug fixes. Check existing issues and PRs, prove the problem on current upstream, and follow the parent skill's contribution attitude.

## Source policies

- Assistant-ui chain: `~/dev/assistant-ui/FORK.md`, shared with Avidor's app and deployment project.
- Vstack renderer: `~/dev/vstack/pi-extensions/pi-tool-renderer/FORK.md`.
