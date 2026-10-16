# Security policy

## Supported versions

Security fixes target current `main` and the latest AC4 prerelease (currently
2.2.1 Beta). Older builds and inherited AC5 versions are not maintained here.
The project has no formal security audit or guaranteed response time.

## Report privately

For memory corruption, unsafe file handling, malicious mod behavior or other
security concerns, do not post exploit details, credentials or private files in
a normal issue. Crashes without a suspected security impact can use the bug form.

Use **Report a vulnerability** on the Security tab if GitHub offers that option.
If that option is unavailable, contact the maintainer through an existing private
channel. If you do not have one, open **Private contact request** from the issue
chooser and ask [PresidentRaptor](https://github.com/PresidentRaptor) for a private
security-reporting route. Include no technical or personal details in that request.

Once a private route is established, provide the affected version, impact,
reproduction steps and a minimal synthetic example when possible. Do not send
an ISO or extracted game assets. Coordinate disclosure with the maintainer while
a fix is investigated; do not assume a response deadline has been agreed.

## Downloads and mods

Use releases from this repository and verify SHA256SUMS.txt. The current Windows
installer is unsigned: its checksum identifies the file but is not a publisher
signature or proof that software is safe. Native mod DLLs run arbitrary code in
the game process; only enable code you trust. Keep backups of saves before testing.
