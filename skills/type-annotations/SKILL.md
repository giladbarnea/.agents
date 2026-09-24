---
name: type-annotations
description: Typing style best practices. Load when writing code.
---

### Typing Style

The following principles apply to any typed language: Python, TypeScript, Rust, etc.
1. Use modern annotations. <no>`Optional[Dict]`</no>, <yes>`dict | None`</yes>.
2. Parametrize container types until you hit a bottom primitive type. <no>`list`</no>, <yes>`list[int]`</yes>. <no>`dict`</no>, <no>`dict[str, list]`</no>, <yes>`dict[str, list[int]]`</yes>.
3. Type all function arguments, return types and variables, as long as it makes sense.
4. Don’t use `Any`. If you don’t know the type, that’s a smell — make a small effort to discover it what it is empirically, then annotate accordingly.
5. Prefer protocols to concrete types. For example, if a function only iterates over a passed value, annotate the argument as `Iterable[...]` rather than `list[...]`. Duck typing is good.
6. Use a dataclass or pydantic model for dicts that play a meaningful role in the code.
7. `Literal["foo", "bar"]` can be helpful.
8. `StrEnum: SAME = "SAME"` can also be helpful.
