#!/bin/bash
# Creates and trusts a local development certificate for code signing
# This eliminates keychain permission prompts during development

set -e

CERT_NAME="ClubCalendar Development"
KEYCHAIN="$HOME/Library/Keychains/login.keychain-db"

# Check if certificate already exists and is trusted
if security find-identity -v -p codesigning 2>/dev/null | grep -q "$CERT_NAME"; then
    echo "✓ Certificate '$CERT_NAME' already exists and is ready to use"
    exit 0
fi

echo "Creating development certificate..."

# Create a temporary directory
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

# Generate self-signed certificate
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
EOF

openssl req -x509 -newkey rsa:2048 \
    -keyout "$TMPDIR/key.pem" \
    -out "$TMPDIR/cert.pem" \
    -days 365 -nodes \
    -config "$TMPDIR/cert.conf" 2>/dev/null

# Export as p12
openssl pkcs12 -export \
    -inkey "$TMPDIR/key.pem" \
    -in "$TMPDIR/cert.pem" \
    -out "$TMPDIR/cert.p12" \
    -passout pass: 2>/dev/null

# Import to keychain (will prompt for login keychain password if locked)
security import "$TMPDIR/cert.p12" -k "$KEYCHAIN" -P "" -T /usr/bin/codesign -T /usr/bin/security

# Set the certificate to be trusted for code signing
# This requires admin password but only once
echo ""
echo "To complete setup, trust the certificate for code signing."
echo "This requires your admin password (one time only):"
echo ""
security add-trusted-cert -d -r trustRoot -p codeSign -k "$KEYCHAIN" "$TMPDIR/cert.pem"

echo ""
echo "✓ Certificate '$CERT_NAME' created and trusted"
echo "✓ Run 'make dev' to build with the new certificate"
