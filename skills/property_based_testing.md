---
name: property-based-testing
description: Guidance for property-based testing in Python. Use when writing tests, reviewing code with serialization/validation/parsing patterns, or when property-based testing provides stronger coverage than example-based tests.
---

# Property-Based Testing Guide

Use this skill proactively during development when you encounter patterns where property-based testing (PBT) provides stronger coverage than example-based tests.

## When to Invoke (Automatic Detection)

**Invoke this skill when you detect:**

- **Serialization pairs**: `encode`/`decode`, `serialize`/`deserialize`, `toJSON`/`fromJSON`, `pack`/`unpack`
- **Parsers**: URL parsing, config parsing, protocol parsing, string-to-structured-data
- **Normalization**: `normalize`, `sanitize`, `clean`, `canonicalize`, `format`
- **Validators**: `is_valid`, `validate`, `check_*` (especially with normalizers)
- **Data structures**: Custom collections with `add`/`remove`/`get` operations
- **Mathematical/algorithmic**: Pure functions, sorting, ordering, comparators
- **Cryptographic operations**: key generation, hashing, encryption/decryption pairs

**Priority by pattern:**

| Pattern | Property | Priority |
|---------|----------|----------|
| encode/decode pair | Roundtrip | HIGH |
| Pure function | Multiple | HIGH |
| Validator | Valid after normalize | MEDIUM |
| Sorting/ordering | Idempotence + ordering | MEDIUM |
| Normalization | Idempotence | MEDIUM |
| Builder/factory | Output invariants | LOW |
| encrypt/decrypt | Inverse | HIGH |

## When NOT to Use

Do NOT use this skill for:
- Simple CRUD operations without transformation logic
- One-off scripts or throwaway code
- Code with side effects that cannot be isolated (network calls, database writes)
- Tests where specific example cases are sufficient and edge cases are well-understood
- Integration or end-to-end testing (PBT is best for unit/component testing)

## Property Catalog (Quick Reference)

| Property | Formula | When to Use |
|----------|---------|--------------|
| **Roundtrip** | `decode(encode(x)) == x` | Serialization, conversion pairs |
| **Idempotence** | `f(f(x)) == f(x)` | Normalization, formatting, sorting |
| **Invariant** | Property holds before/after | Any transformation |
| **Commutativity** | `f(a, b) == f(b, a)` | Binary/set operations |
| **Associativity** | `f(f(a,b), c) == f(a, f(b,c))` | Combining operations |
| **Identity** | `f(x, identity) == x` | Operations with neutral element |
| **Inverse** | `f(g(x)) == x` | encrypt/decrypt, compress/decompress |
| **Oracle** | `new_impl(x) == reference(x)` | Optimization, refactoring |
| **Easy to Verify** | `is_sorted(sort(x))` | Complex algorithms |
| **No Exception** | No crash on valid input | Baseline property |

**Strength hierarchy** (weakest to strongest):
No Exception → Type Preservation → Invariant → Idempotence → Roundtrip

## Python Library: Hypothesis

Use **Hypothesis** for property-based testing in Python:

```python
from hypothesis import given, strategies as st

@given(st.text())
def test_decode_inverts_encode(s):
    assert decode(encode(s)) == s

@given(st.lists(st.integers()))
def test_sort_is_idempotent(lst):
    assert sorted(sorted(lst)) == sorted(lst)
```

Key strategies:
- `st.text()`, `st.integers()`, `st.floats()`, `st.lists()`, `st.dictionaries()`
- `st.binary()` for byte strings (relevant for key material)
- `st.one_of()`, `st.builds()` for complex objects
- `st.from_regex()` for pattern-constrained strings

## How to Suggest PBT

When you detect a high-value pattern while writing tests, **offer PBT as an option**:

> "I notice `encode_message`/`decode_message` is a serialization pair. Property-based testing with a roundtrip property would provide stronger coverage than example tests. Want me to use that approach?"

**If codebase already uses a PBT library** (Hypothesis), be more direct:

> "This codebase uses Hypothesis. I'll write property-based tests for this serialization pair using a roundtrip property."

**If user declines**, write good example-based tests without further prompting.

## Red Flags

- Recommending trivial getters/setters
- Missing paired operations (encode without decode)
- Ignoring type hints (well-typed = easier to test)
- Overwhelming user with candidates (limit to top 5-10)
- Being pushy after user declines

## Rationalizations to Reject

Do not accept these shortcuts:

- **"Example tests are good enough"** - If serialization/parsing/normalization is involved, PBT finds edge cases examples miss
- **"The function is simple"** - Simple functions with complex input domains (strings, floats, nested structures) benefit most from PBT
- **"We don't have time"** - PBT tests are often shorter than comprehensive example suites
- **"It's too hard to write generators"** - Hypothesis has excellent built-in strategies; custom generators are rarely needed
- **"The test failed, so it's a bug"** - Failures require validation; a failing property may indicate a bug in the test or the code
- **"No crash means it works"** - "No exception" is the weakest property; always push for stronger guarantees

## Examples

- *User:* "Write tests for the key hashing function."
- *Assistant (in Property-Based Testing mode):* "Since `hash_key`/`verify_key` is an inverse pair, I'll use Hypothesis with a roundtrip property: `verify_key(hash_key(k), k) == True` for all valid keys, plus a property that different keys produce different hashes."

- *User:* "Test the event content serialization."
- *Assistant (in Property-Based Testing mode):* "I'll write a roundtrip property: `deserialize(serialize(event)) == event` for arbitrary event objects, using `st.builds()` to generate valid event structures."
