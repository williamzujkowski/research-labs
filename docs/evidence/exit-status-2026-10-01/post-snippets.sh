#!/bin/bash
# Run the two inline snippets from the post, as written (gpg given batch passphrase flags).
cd "$(mktemp -d)" || exit 2
export GNUPGHOME="$PWD/.gnupg"; mkdir -m 700 "$GNUPGHOME"
echo 'otpauth://totp/lab:synthetic?secret=JBSWY3DPEHPK3PXP' > seeds.txt
echo 'synthetic' > pass.txt
G='gpg --batch --pinentry-mode loopback --passphrase-file pass.txt'
echo '== snippet 1'
bash -c 'set -eo pipefail; false | tee /dev/null; echo REACHED'; echo "exit=$?"
echo '== snippet 2, good backup'
$G --symmetric --output backup.gpg seeds.txt
$G --decrypt backup.gpg 2>/dev/null | cmp - seeds.txt && echo "backup restores"; echo "exit=$?"
echo '== snippet 2, empty backup (negative control)'
: > backup.gpg
$G --decrypt backup.gpg 2>/dev/null | cmp - seeds.txt && echo "backup restores"; echo "exit=$?"
