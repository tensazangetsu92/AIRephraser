# PostgreSQL backup and restore

These scripts are for the future Docker Compose deployment on one VPS. They
create a PostgreSQL custom-format dump (`pg_dump -Fc`), validate it with
`pg_restore --list`, retain the newest 14 daily files locally and can copy the
verified file to an independent encrypted remote through `rclone crypt`.

## One-time server setup

After the project is deployed to `/opt/humary` and the Compose file exists:

```bash
sudo install -d -m 700 /var/backups/humary
sudo install -d -m 700 /etc/humary
sudo chmod 750 /opt/humary/deploy/backup/backup-postgres.sh
sudo chmod 750 /opt/humary/deploy/backup/restore-postgres.sh
sudo cp /opt/humary/deploy/backup/backup.env.example /etc/humary/backup.env
sudo chmod 600 /etc/humary/backup.env
sudoedit /etc/humary/backup.env

sudo cp /opt/humary/deploy/backup/humary-db-backup.service /etc/systemd/system/
sudo cp /opt/humary/deploy/backup/humary-db-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now humary-db-backup.timer
```

For the current staging deployment, set these values in `/etc/humary/backup.env`:

```bash
COMPOSE_FILE=/opt/humary/docker-compose.yml
COMPOSE_ENV_FILE=/opt/humary/deploy/compose.staging.env
COMPOSE_PROJECT_NAME=humary-staging
POSTGRES_SERVICE=db
```

Run the first backup manually and inspect its result:

```bash
sudo systemctl start humary-db-backup.service
sudo systemctl status humary-db-backup.service
sudo ls -lah /var/backups/humary
```

View its logs:

```bash
sudo journalctl -u humary-db-backup.service --since today
```

## Independent copy

A backup that stays only on the same VPS does not protect against losing that
VPS. Configure `rclone` with a **crypt remote** that points to storage separate
from the VPS, then set `BACKUP_RCLONE_REMOTE` in `/etc/humary/backup.env`.
The crypt remote encrypts filenames and file contents before the copy leaves
the VPS; keep its rclone configuration and password recovery material separate.
Choose a storage location appropriate for the personal-data requirements of the
project.

## Restore test

Before trusting backups, create a separate test database and set
`POSTGRES_DB` in a temporary copy of `/etc/humary/backup.env` to that database.
Never run the restore against the live database:

```bash
sudo -i
source /etc/humary/backup.env
CONFIRM_RESTORE=YES /opt/humary/deploy/backup/restore-postgres.sh \
  /var/backups/humary/humary-postgres-YYYYMMDDTHHMMSSZ.dump
```

The restore command intentionally requires `CONFIRM_RESTORE=YES` because it
uses `--clean` and replaces existing database objects.
