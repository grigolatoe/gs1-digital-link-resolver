# Release signing

Every tagged release of this project is published with a detached PGP
signature over a plain-text manifest listing the release artefacts and
their cryptographic digests. Verifying the signature gives you the same
trust anchor that NLnet evaluators received with the NGI Zero Commons
Fund application: a single Ed25519 PGP key under the maintainer's
direct control.

## Signing key

| Field | Value |
|---|---|
| Owner | Edmondo Grigolato `<edmondo.grigolato@grigolato.it>` |
| Fingerprint | `47DE71F021C986123851E8AD65A8E29C92A63D38` |
| Algorithm | Ed25519 (signing) + cv25519 (encryption subkey) |
| Created | 2026-02-04 |
| Expires | 2029-02-03 |
| Public key | Attached to the release as `signing-key.asc`, also retrievable from any major keyserver by fingerprint |

The same fingerprint was attached to the NGI Zero Commons Fund
resubmission on 2026-05-19 (reference `2026-06-1fc`).

## What is signed

For each release tag `vX.Y.Z` a file `SIGNATURES-vX.Y.Z.txt` is
attached to the GitHub Release. The file lists, in plain text:

- The git commit SHA the release was built from.
- Every published container image reference and its `sha256:` digest.
- The platform(s) for which the image was built.
- A free-form notes field (e.g. compiler version, build host).

Alongside it, `SIGNATURES-vX.Y.Z.txt.asc` carries the detached PGP
signature produced with the key above.

## How to verify a release

```bash
# 1. Import the maintainer's public key (one-time setup).
#    Either fetch from a keyserver:
gpg --keyserver hkps://keys.openpgp.org --recv-keys 47DE71F021C986123851E8AD65A8E29C92A63D38

#    Or download signing-key.asc from the release page and import:
gpg --import signing-key.asc

# 2. Download the signed manifest + signature from the release page.
#    (Replace X.Y.Z with the release you want to verify.)
RELEASE=v0.2.0
gh release download "$RELEASE" \
  --repo grigolatoe/gs1-digital-link-resolver \
  --pattern "SIGNATURES-${RELEASE}.txt*"

# 3. Verify the signature.
gpg --verify "SIGNATURES-${RELEASE}.txt.asc" "SIGNATURES-${RELEASE}.txt"
# Expected: Good signature from "Edmondo Grigolato <edmondo.grigolato@grigolato.it>"
#           Primary key fingerprint: 47DE 71F0 21C9 8612 3851  E8AD 65A8 E29C 92A6 3D38

# 4. Pull the image and confirm its digest matches the signed manifest.
docker pull ghcr.io/grigolatoe/gs1-digital-link-resolver:0.2.0
docker inspect --format '{{index .RepoDigests 0}}' \
  ghcr.io/grigolatoe/gs1-digital-link-resolver:0.2.0
# Expected output's @sha256:... must match the digest listed in SIGNATURES-v0.2.0.txt
```

If any of those steps disagree — different fingerprint, failed signature,
mismatched digest — **do not run the image**. Open an issue at
<https://github.com/grigolatoe/gs1-digital-link-resolver/issues> and we
will investigate.

## Why PGP instead of cosign

Cosign / sigstore would be a strictly better long-term answer: it
publishes signatures into the OCI registry alongside the image and
supports keyless OIDC verification. We may add a parallel cosign trust
anchor in a later release.

For v0.2.0 we picked PGP because:

- The key already anchors the maintainer's identity for the NLnet
  application and for the project's GitHub commits, so verifiers don't
  have to trust a new key.
- Verification needs only `gpg`, which every Linux/macOS developer and
  every EU public-sector security review already has installed.
- Detached signatures over a plain-text manifest are auditable by
  hand — anyone can read what was signed without running additional
  tooling.

## Reproducing a signing run (maintainer notes)

```bash
RELEASE=v0.2.0
git checkout "$RELEASE"
COMMIT=$(git rev-parse HEAD)

cat > "SIGNATURES-${RELEASE}.txt" <<EOF
Project: gs1-digital-link-resolver
Release: ${RELEASE}
Git commit: ${COMMIT}
Built by: Edmondo Grigolato <edmondo.grigolato@grigolato.it>

# Container images (linux/amd64)
ghcr.io/grigolatoe/gs1-digital-link-resolver:${RELEASE#v}  sha256:<digest>
ghcr.io/grigolatoe/gs1-digital-link-resolver:latest        sha256:<same digest>
EOF

gpg --armor --detach-sign \
    --local-user 47DE71F021C986123851E8AD65A8E29C92A63D38 \
    --output "SIGNATURES-${RELEASE}.txt.asc" \
    "SIGNATURES-${RELEASE}.txt"

gpg --verify "SIGNATURES-${RELEASE}.txt.asc" "SIGNATURES-${RELEASE}.txt"

gh release upload "$RELEASE" \
  "SIGNATURES-${RELEASE}.txt" \
  "SIGNATURES-${RELEASE}.txt.asc"
```
