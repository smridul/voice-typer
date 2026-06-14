#!/bin/sh

# Xcode Cloud runs this automatically right after cloning the repo.
# It recreates ios/Config/LocalSecrets.xcconfig (gitignored) from a secret
# environment variable defined in the Xcode Cloud workflow settings.
#
# Required env var (set it in App Store Connect > Xcode Cloud > your workflow
# > Environment, and mark it as "Secret"):
#   GROQ_API_KEY

set -e

REPO="${CI_PRIMARY_REPOSITORY_PATH:-$(cd "$(dirname "$0")/.." && pwd)}"
XCCONFIG="$REPO/ios/Config/LocalSecrets.xcconfig"

mkdir -p "$REPO/ios/Config"

cat > "$XCCONFIG" <<EOF
GROQ_API_KEY = ${GROQ_API_KEY}
EOF

echo "Wrote $XCCONFIG"
