#!/bin/sh
# Run shellcheck over the four pre-correction snippets, default and all optional checks.
cd "$(dirname "$0")" || exit 2
printf '#!/bin/bash\nset -e\nsudo suricata-update --verbose 2>&1 | tee /var/log/suricata-update.log\n' > pipe.sh
printf '#!/bin/bash\ngpg --symmetric --cipher-algo AES256 totp-seeds.txt > totp-backup.gpg\n' > gpg.sh
printf '#!/bin/bash\ncurl -sO https://packages.wazuh.com/4.9/docker-compose.yml\n' > curl.sh
printf '#!/bin/bash\npihole -a adlist add https://example.invalid/list\npihole -g\n' > pihole.sh
shellcheck --version | head -2
for f in pipe gpg curl pihole; do
  echo "== $f default"; shellcheck "$f.sh"; echo "exit=$?"
  echo "== $f -o all"; shellcheck -o all "$f.sh"; echo "exit=$?"
done
