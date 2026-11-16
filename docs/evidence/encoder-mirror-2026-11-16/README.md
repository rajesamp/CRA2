# Approved encoder build asset

On 2026-11-16 the owner approved publishing the existing verified encoder archive.
The [GitHub Release](https://github.com/rajesamp/CRA2/releases/tag/build-deps-bge-small-en-v1.5-3858004b3822)
contains the original archive, `SHA256SUMS`, provenance and the upstream
FlagEmbedding MIT license. It is a build dependency, not an application release.
The tag is anchored to the already-public main commit recorded in the release.

The archive is 76,692,531 bytes, with SHA-256
`3858004b3822f64f940280874b8f2d2dc25b34a4f3eb3cdf617bdceeb21ed9ed`.
GitHub's uploaded-asset digest and an independent anonymous download both match.
The archive bytes and existing extracted-file checksum policy are unchanged.

[Fresh-cache verification](clean-cache.json) started without an extracted model.
All seven installed files passed their expected hashes, including the existing
tokenizer-limit normalization. The offline setup built 57 documents, 68 chunks
and 384-dimensional embeddings. No model-provider invocation was used.

The repository Actions variable `CRA2_MODEL_ARCHIVE_URL` was set and read back
successfully. Both `week2-4` and `container-security` already consume that variable.
Their checks still verify the exact archive and extracted files before use.

GitHub CI execution is pending at this record's creation. The previously recorded
Debian vulnerability findings remain release blockers; artifact availability does
not waive that gate. No Cloud Run deployment, invitation or access grant occurred.

Evidence: [release and asset metadata](release.json), [provenance](encoder-provenance.json),
[checksums](SHA256SUMS), [upstream license](LICENSE.FlagEmbedding.txt).
