#!/bin/bash
# Creates a local self-signed certificate for development code signing

CERT_NAME="ClubCalendar Development"

# Check if certificate already exists
if security find-identity -v -p codesigning 2>/dev/null | grep -q "$CERT_NAME"; then
    echo "Certificate '$CERT_NAME' already exists"
    exit 0
fi

echo "Creating self-signed development certificate..."

# Create certificate config
cat > /tmp/cert.config << CERTEOF
[ req ]
default_bits       = 2048
distinguished_name = req_distinguished_name
prompt             = no
[ req_distinguished_name ]
CN = $CERT_NAME
[ extensions ]
keyUsage = critical, digitalSignature
extendedKeyUsage = codeSigning
CERTEOF

# Generate key and certificate
openssl req -x509 -newkey rsa:2048 -keyout /tmp/dev-key.pem -out /tmp/dev-cert.pem \
    -days 365 -nodes -config /tmp/cert.config -extensions extensions 2>/dev/null

# Create p12 bundle (no password for import)
openssl pkcs12 -export -out /tmp/dev-cert.p12 -inkey /tmp/dev-key.pem -in /tmp/dev-cert.pem \
    -passout pass: 2>/dev/null

# Import to keychain
security import /tmp/dev-cert.p12 -k ~/Library/Keychains/login.keychain-db -P "" -T /usr/bin/codesign 2>/dev/null

# Clean up temp files
rm -f /tmp/cert.config /tmp/dev-key.pem /tmp/dev-cert.pem /tmp/dev-cert.p12

echo ""
echo "Certificate created! Now you need to trust it:"
echo "1. Open Keychain Access"
echo "2. Find '$CERT_NAME' in 'login' keychain under 'Certificates'"
echo "3. Double-click it, expand 'Trust', set 'Code Signing' to 'Always Trust'"
echo ""
echo "After trusting, run: make dev"
