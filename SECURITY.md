# Security policy

Do not report credentials, private server identifiers, household data, or exploitable details in a public issue. Contact the maintainers through the private vulnerability reporting feature of the hosting forge once available. Until then, do not submit sensitive reports in public; remove secrets from local history and rotate exposed credentials immediately.

The bootstrap does not accept credentials in arguments, persists only non-secret Discord IDs, and avoids logging response bodies. Keep the local state and data directories private. Report the affected version, impact, and a safe reproduction that uses a fake Discord transport.
