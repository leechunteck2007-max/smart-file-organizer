# Security policy

Only the current alpha is maintained; fixes may require upgrading.

For vulnerabilities involving file loss, unsafe path access or privacy exposure, use this repository's **Security → Advisories → Report a vulnerability** when private reporting is available. Do not publish exploit details, credentials or personal files in issues. If the private-report button is unavailable, request a private maintainer contact in an issue without describing the vulnerability. No personal contact address is published.

Include app/Windows versions, synthetic reproduction, expected/actual behavior and safety impact. Sanitize paths, identities and content. Maintainers should investigate with synthetic fixtures and coordinate a fix before disclosure; no response-time guarantee is made.

The standalone build is unsigned. Validate ZIP downloads against release SHA-256 checksums. No remote update or dependency download occurs inside the organizer.
