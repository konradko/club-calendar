#!/bin/bash
# Creates a local self-signed code-signing certificate.
#
# We sign with a stable identity so the keychain ACLs set up on first launch
# stay matched across rebuilds — that's what prevents the "ClubCalendar wants
# to access key X" prompts. We deliberately do NOT mark the cert as a trusted
# code-signing root: trust is only consulted by Gatekeeper (spctl), and macOS
# only invokes Gatekeeper for apps carrying a com.apple.quarantine xattr —
# something locally built apps never have. Skipping the trust step means
# `make dmg` no longer prompts for the admin/Touch ID password on every run.

set -e

CERT_NAME="ClubCalendar Development"
KEYCHAIN="$HOME/Library/Keychains/login.keychain-db"

if security find-identity -v -p codesigning 2>/dev/null | grep -q "$CERT_NAME"; then
    echo "Certificate '$CERT_NAME' already exists"
    exit 0
fi

# No *valid* identity — but an expired or broken cert with the same name may
# still be lingering (find-identity -v lists valid identities only). Purge
# stale copies first: a duplicate CN makes `codesign --sign "$CERT_NAME"`
# ambiguous, and signing with a *different* identity than the previous build
# resets the calendar (TCC) grant and orphans the app's keychain items.
PURGED=0
while security find-certificate -c "$CERT_NAME" "$KEYCHAIN" >/dev/null 2>&1; do
    security delete-certificate -c "$CERT_NAME" "$KEYCHAIN" 2>/dev/null || break
    PURGED=$((PURGED + 1))
    [ "$PURGED" -ge 10 ] && break
done
if [ "$PURGED" -gt 0 ]; then
    echo "Removed $PURGED stale/expired '$CERT_NAME' certificate(s)."
    echo "NOTE: the signing identity is rotating. On next launch macOS will"
    echo "re-prompt once for Calendar access, and old keychain items may ask"
    echo "'ClubCalendar wants to access ...' — click Always Allow, or run"
    echo "'make macos-reset-all' to start clean (requires re-onboarding)."
fi

echo "Creating development certificate..."

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

cat > "$TMPDIR/cert.conf" << EOF
[req]
distinguished_name = req_dn
x509_extensions = codesign
prompt = no

[req_dn]
CN = $CERT_NAME

[codesign]
keyUsage = critical, digitalSignature
extendedKeyUsage = codeSigning
basicConstraints = critical, CA:false
EOF

openssl genrsa -out "$TMPDIR/key.pem" 2048 2>/dev/null
openssl req -new -key "$TMPDIR/key.pem" -out "$TMPDIR/cert.csr" -config "$TMPDIR/cert.conf" 2>/dev/null
# 10-year validity: when this cert expires, every build silently rotates to a
# new identity, which resets the TCC calendar grant and triggers a keychain
# prompt per stored item. Long validity keeps installs and updates seamless.
openssl x509 -req -in "$TMPDIR/cert.csr" -signkey "$TMPDIR/key.pem" -out "$TMPDIR/cert.pem" \
    -days 3650 -extfile "$TMPDIR/cert.conf" -extensions codesign 2>/dev/null

openssl pkcs12 -export \
    -legacy \
    -inkey "$TMPDIR/key.pem" \
    -in "$TMPDIR/cert.pem" \
    -out "$TMPDIR/cert.p12" \
    -passout pass:temp123 2>/dev/null

security import "$TMPDIR/cert.p12" -k "$KEYCHAIN" -P "temp123" -T /usr/bin/codesign -T /usr/bin/security 2>/dev/null

echo "Certificate '$CERT_NAME' created"
