---
name: write-tests
description: Testing best practices and tenets — load before writing any tests.
---

<testing-tenets>
### Testing Tenets

<tests-must-be-meaningful priority="1">
When writing tests, make sure they're not "empty"—don't over-mock, and don't mock away the core of what you're testing.
False security is worse than having no tests at all.
Don't test implementation, test behavior.
The behavior under test should be based on—and faithfully reflect—the original spec or plan, not the implementation, to avoid circularity.
Fewer tests that are more focused, precise, and substantial are better than a larger number of meatless tests.
Insubstantial tests usually fall under the category of fooling one's self petitio principii–style—essentially, even if indirectly, by mocking aspects of the outcome you're supposed to be testing.
</tests-must-be-meaningful>

<tests-must-be-informative priority="2">
Make use of `assert`'s second positional argument to help the developer understand the error.
<negative-example description="uninformative assert expression">
`assert foo`
</negative-example>
<positive-example description="informative assert expression">
`assert foo, f"Expected 'foo' to be truthy. Got: {foo=!r}"`
</positive-example>
</tests-must-be-informative>

<tests-must-not-cause-exceptions-themselves priority="2">
Tests must be robust. Test that cause errors "on accident" overshadow the behavior under test.
<negative-example description="hard-coding a symbol path is brittle" example-id="1">
`with patch("module.function"): ...`
</negative-example>
<positive-example description="using the actual symbol is robust" example-id="1">
```
import module.function
with patch(module.function): ...
```
</positive-example>
<negative-example description="Raises a `KeyError` if the key isn't present, which is not the behavior under test. Fails for the wrong reason." example-id="2">
`assert my_dict["nested"]["key"] == "value", ...`
</negative-example>
<positive-example example-id="2">
`assert my_dict.get("nested", {}).get("key") == "value", ...`
</positive-example>
</tests-must-not-cause-exceptions-themselves>

</testing-tenets>
