#!/bin/bash
# Creates and trusts a local development certificate for code signing
# This eliminates keychain permission prompts during development

set -e

CERT_NAME="ClubCalendar Development"
KEYCHAIN="$HOME/Library/Keychains/login.keychain-db"

# Check if certificate already exists and is trusted
if security find-identity -v -p codesigning 2>/dev/null | grep -q "$CERT_NAME"; then
    echo "Certificate '$CERT_NAME' already exists"
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
basicConstraints = critical, CA:false
EOF

# Generate key and certificate
openssl genrsa -out "$TMPDIR/key.pem" 2048 2>/dev/null
openssl req -new -key "$TMPDIR/key.pem" -out "$TMPDIR/cert.csr" -config "$TMPDIR/cert.conf" 2>/dev/null
openssl x509 -req -in "$TMPDIR/cert.csr" -signkey "$TMPDIR/key.pem" -out "$TMPDIR/cert.pem" \
    -days 365 -extfile "$TMPDIR/cert.conf" -extensions codesign 2>/dev/null

# Export as p12 with legacy algorithm for macOS compatibility
openssl pkcs12 -export \
    -legacy \
    -inkey "$TMPDIR/key.pem" \
    -in "$TMPDIR/cert.pem" \
    -out "$TMPDIR/cert.p12" \
    -passout pass:temp123 2>/dev/null

# Import to keychain
security import "$TMPDIR/cert.p12" -k "$KEYCHAIN" -P "temp123" -T /usr/bin/codesign -T /usr/bin/security 2>/dev/null

# Set the certificate to be trusted for code signing (requires admin password)
echo ""
echo "Trusting certificate for code signing (requires admin password):"
sudo security add-trusted-cert -d -r trustRoot -p codeSign -k "$KEYCHAIN" "$TMPDIR/cert.pem"

echo ""
echo "Certificate '$CERT_NAME' created and trusted"
