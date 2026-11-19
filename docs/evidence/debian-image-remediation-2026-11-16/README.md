# Cloud Run image remediation

The [Debian reconciliation](debian-triage.json) covers all **104 blocking matches**
in the tested Debian image. It groups 20 installed binaries into nine source
packages and 40 advisory IDs. Each row records the installed version, the Debian
13 repository version and the vendor advisory. The advisory feed and original
Grype report are bound by SHA-256 in the reconciliation.

Debian lists all 40 source-package advisory pairs as open for Debian 13. The
tracker feed records zero fixed versions for those pairs in that release. The
current Distroless builder and runtime tags still resolve to the existing digests.
See the [Debian Security Tracker](https://security-tracker.debian.org/tracker/)
and the [original scan summary](../gcp-owner-2026-11-16/scan-comparison.json).

The replacement candidate uses a publisher-signed Wolfi base with pinned Python
3.13 and system packages, the existing Python lockfile, and the existing encoder
archive. Syft identified 35 Wolfi APK packages, 117 Python packages, and seven
npm packages. With the same Grype database and policy as the original scan, the
candidate passed with **zero blocking matches**, three Medium matches and one
Low match. The intentionally vulnerable metadata control detected 27 blocking
matches. See the [signed base, image IDs, evidence hashes, and smoke results](wolfi-candidate.json).

The candidate passed all six offline workflows as a nonroot Linux amd64 image.
The local startup returned HTTP 200 and blocked the application-file read.
The cloud entrypoint returned HTTP 200 on its health route and rejected unsigned
requests on four application paths. Those tests used synthetic configuration.
The draft PR rebuilds and rescans the committed recipe with the same package
pins. Owner acceptance and live Google IAP verification remain pending.
