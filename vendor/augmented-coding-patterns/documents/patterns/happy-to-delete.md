---
authors: [ivett_ordog]
---

# Happy to Delete

## Problem
Humans are naturally precious about code, especially code they wrote themselves. This attachment makes us reluctant to delete failed attempts and start fresh. With AI-generated code, this instinct is counterproductive—the code is cheap to regenerate, yet we treat it as if it took hours to write by hand. This leads to forcing fixes on fundamentally flawed implementations instead of simply reverting and trying again.

## Pattern
Embrace the disposability of AI-generated code:

- **Treat AI code as cheap exploration**: Unlike hand-written code, AI can regenerate solutions in seconds
- **Revert freely**: When an attempt goes wrong, don't force fixes—revert and try again
- **Start fresh with lessons learned**: Each failed attempt teaches you what to specify better in the next prompt
- **Use git liberally**: Commit before AI changes, making reversion effortless
- **Recognize diminishing returns early**: If iteration 2-3 isn't improving, delete and restart

The willingness to delete removes the pressure to "make it work" and paradoxically leads to better outcomes faster.

## Example

**Bad**: AI generates a refactoring that misses key requirements. You spend 30 minutes across 5 iterations trying to patch it up. The code gets messier with each fix attempt.

**Good**: AI generates a refactoring that misses key requirements. You immediately revert, refine your prompt with clearer constraints, and try again. The second attempt gets it right in one go because you learned from the first failure.

**Example prompt for reverting**:
```
Your solution [describe the problem]. A better approach would be [describe the better approach].
Please `git reset --hard` and try again.
```

The explicit `git reset --hard` instruction is important—without it, AI often tries to regenerate the original code from memory instead of properly reverting.
