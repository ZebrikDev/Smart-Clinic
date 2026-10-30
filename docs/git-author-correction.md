# Stage 2 Git identity correction

On 2026-10-30, Shon explicitly authorized correcting the author and committer
of the seven Stage 2 commits below to `ZebrikDev <shon.sk.tech@gmail.com>`,
using the email already associated with his earlier GitHub commits. The original
identity was the local machine default. This changes Git attribution metadata;
it does not replace the factual account of AI assistance in AI_USAGE.md.

For every pair, the complete file tree, commit message, author timestamp and
committer timestamp are identical. Parent hashes change to maintain the same
linear order. The original Red, Green and Refactor states and captured Red output
are preserved. The Stage 1 history and `main` are outside the correction.

| Commit | Original SHA | Corrected SHA |
|---|---|---|
| Preserve reviewed Smart Clinic M1 and M2 | `550ab9316e6a94859ba7a4d7032a8d2750e89b0d` | [4788a6d362dd6eb307476a94e7eaef3cf5606b6e](https://github.com/ZebrikDev/Smart-Clinic/commit/4788a6d362dd6eb307476a94e7eaef3cf5606b6e) |
| test: record Red for closest slot selection | `679aafd6e4430c55b12490f0e9dbb6685687b586` | [6d2e55af73126fcd2bca25b3112eec685ce80e9d](https://github.com/ZebrikDev/Smart-Clinic/commit/6d2e55af73126fcd2bca25b3112eec685ce80e9d) |
| feat: implement closest slot selection (Green) | `60d2d3c02a3136612ef1d58f0e401bbd5506eddb` | [97dde5106213a1aa090bc0610416435e465e8498](https://github.com/ZebrikDev/Smart-Clinic/commit/97dde5106213a1aa090bc0610416435e465e8498) |
| refactor: express closest selection with a ranking key | `5e8ba6d8e8b71ca68cb1a4db0fd504b31fb78608` | [ab5ebde75af843c3651800d3e2bc64dcaf4f9709](https://github.com/ZebrikDev/Smart-Clinic/commit/ab5ebde75af843c3651800d3e2bc64dcaf4f9709) |
| docs: record M3 strategy verification and TDD history | `72cd2840290c576b5c724ffd71db842f91eda7f1` | [0b786c7509e965b9d4efbc72db4b33602c2d0b54](https://github.com/ZebrikDev/Smart-Clinic/commit/0b786c7509e965b9d4efbc72db4b33602c2d0b54) |
| Implement Google Calendar client, factory and configuration | `c86172f03a9be05ac6e930ba175256388ede3f20` | [0329d9ba90157f82b1a30c25c8b9f84b6c1a3223](https://github.com/ZebrikDev/Smart-Clinic/commit/0329d9ba90157f82b1a30c25c8b9f84b6c1a3223) |
| Implement appointment service and FIFO waiting-list backfill | `ad68d8e26c13d61b5a8f3c5f98b6ba6cce3b077c` | [4709a90e85028b5167ffbd75958bbf3f9b5b2d83](https://github.com/ZebrikDev/Smart-Clinic/commit/4709a90e85028b5167ffbd75958bbf3f9b5b2d83) |

Historical AI_USAGE.md entries retain the original hashes as records of those
earlier checkpoints. Use the corrected hashes above for the current branch.
A separate documentation commit updates README references and records this
mapping, without changing implementation, tests or data. A local backup branch
and verified Git bundle preserve the original history. Publication is restricted
by an explicit lease to the previously verified Stage 2 tip; `main` is not pushed.
