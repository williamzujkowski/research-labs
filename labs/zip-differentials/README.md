# ZIP API observations

Question: can indexed and streaming readers accept identical bytes while observing different entries?
This is the first bounded feasibility pilot for [blog proposal #591](https://github.com/williamzujkowski/williamzujkowski.github.io/issues/591).

## Method

Three parser/API combinations across **two implementations**:

1. CPython `zipfile.ZipFile.infolist()` and `open(ZipInfo)`.
2. OpenJDK `ZipFile.entries()` and immediate `getInputStream(entry)`.
3. OpenJDK `ZipInputStream.getNextEntry()` and sequential entry reads.

The Dockerfile pins the actual CPython and Temurin distributions by digest. Each run records their
full version strings. Java's indexed reader is opened immediately after enumeration to preserve
its handling of duplicate records; arbitrary later name lookup is a different experiment.

All entries are stored, unencrypted ASCII text with flat relative filenames. A byte sequence,
`REVIEW-ME` followed by a newline, is the benign marker. The checker reports whether any completely
read entry contains it. This is an intentionally simple policy demonstration, not antivirus.

| Fixture | Deliberate change |
| --- | --- |
| control | One ordinary entry, matching local and central records |
| duplicate-marker-first | Two `note.txt` records; marker first |
| duplicate-marker-last | Same two payloads, reversed local/central order |
| central-order-reversed | Two distinct names; central-directory order reverses local order |
| local-central-name-conflict | Local name `local.txt`, central name `index.txt` |
| local-entry-absent-from-index | Local marker entry has no central-directory record |

The final two archives deliberately violate consistency requirements; successful API iteration does
not mean format validity. The omitted record conflicts with APPNOTE §4.3.2. This is about handling
of a fixed inconsistent input, not evidence that conforming archives generally cause data loss.

Each adapter gets a fresh process, 10 seconds, 20 entries and 1 MiB of decoded content. The full
container gets 2 CPUs, 512 MiB memory, 128 processes and a 16 MiB temporary filesystem. Corpus size
is fixed at one control plus five variants; no tuning loop or fuzzer runs. Initial feasibility has
a one-working-day ceiling. Failure to find useful disagreement ends this pilot rather than growing
it until a preferred result appears.

The report retains raw adapter stdout/stderr and ordered per-entry hashes. It separates success,
success-with-warning, parser rejection, timeout, limit-exceeded and adapter-error. A rejection is
never converted into a successful empty archive or a clean marker verdict. Completed entries before a failure
are retained in raw observations; bytes of the failing entry are not retained. Rejected runs do not participate in accepted-result comparison.
`accepted_entry_sequence_disagreement` includes name, order, size, hash and marker differences;
therefore an order-only difference is not automatically a content or policy difference.
`accepted_marker_decisions` records the narrower policy result.

There is **no extraction stage**: final filesystem overwrite behavior is not measured. Both
same-name entries stay in the observations, and duplicate ordering alone demonstrates no bypass.
The pilot cannot support a scanner-to-extractor claim without a separately specified consumer.

## Sources and provenance

Accessed 2026-09-13:

- Yufan You, Jianjun Chen, Qi Wang and Haixin Duan, [*My ZIP isn't your ZIP: Identifying and
  Exploiting Semantic Gaps Between ZIP Parsers*](https://www.usenix.org/conference/usenixsecurity25/presentation/you),
  USENIX Security 2025, pp. 431–450. This motivates the question; its reported findings are not ours.
- [Paper artifact appendix](https://www.usenix.org/system/files/usenixsecurity25-appendix-you.pdf)
  and [ZipDiff reference revision](https://github.com/ouuan/ZipDiff/tree/d5d9c36eb7dd1a4b911ca6ca0a93ecc3d7eaee4f).
  No upstream code, corpus, figures or paper text is vendored here; the generator and adapters are original.
- [PKWARE APPNOTE](https://pkware.cachefly.net/webdocs/casestudies/APPNOTE.TXT), record layouts §4.3
  and correspondence requirement §4.3.2. The specification is linked, not redistributed.
- [Python 3.12 zipfile API](https://docs.python.org/3.12/library/zipfile.html): passing a `ZipInfo`
  object distinguishes duplicate-name members.
- [Java 21 ZipInputStream](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/util/zip/ZipInputStream.html):
  reads local headers, without reading the central-directory entry metadata.
- [Java 21 ZipFile](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/util/zip/ZipFile.html).
- [Docker runtime documentation](https://docs.docker.com/engine/containers/run/), for the wrapper's
  isolation and resource controls.

Publication gate: a reader-relevant accepted-input disagreement, or a meaningful negative result
tied to a verified historical expectation, plus editorial/source review. The lab's existence and
a successful CI run do not establish a new vulnerability or authorize publication of a blog post.
