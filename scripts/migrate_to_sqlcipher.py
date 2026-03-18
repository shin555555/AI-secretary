"""既存の平文SQLiteデータベースをSQLCipher暗号化データベースに移行するスクリプト"""

import os
import secrets
import shutil

import keyring

DB_PATH = "data/secretary.db"
BACKUP_PATH = "data/secretary.db.plaintext.backup"
ENCRYPTED_PATH = "data/secretary_encrypted.db"

KEYRING_SERVICE = "ai-secretary"
KEYRING_KEY_NAME = "db_encryption_key"


def get_or_create_db_key() -> str:
    key = keyring.get_password(KEYRING_SERVICE, KEYRING_KEY_NAME)
    if key:
        return key
    key = secrets.token_hex(32)
    keyring.set_password(KEYRING_SERVICE, KEYRING_KEY_NAME, key)
    return key


def main() -> None:
    if not os.path.exists(DB_PATH):
        print(f"[INFO] {DB_PATH} does not exist. Nothing to migrate.")
        print("[INFO] A new encrypted DB will be created on first server start.")
        return

    # Check if already encrypted
    try:
        import sqlite3

        conn = sqlite3.connect(DB_PATH)
        conn.execute("SELECT count(*) FROM sqlite_master")
        conn.close()
    except Exception:
        print(f"[INFO] {DB_PATH} is already encrypted or corrupted. Skipping migration.")
        return

    print(f"[INFO] Plain SQLite database found: {DB_PATH}")

    db_key = get_or_create_db_key()
    print("[INFO] Encryption key ready (stored in OS keyring)")

    # Backup
    shutil.copy2(DB_PATH, BACKUP_PATH)
    print(f"[OK] Backup created: {BACKUP_PATH}")

    # Clean up previous attempt
    if os.path.exists(ENCRYPTED_PATH):
        os.remove(ENCRYPTED_PATH)

    # Encrypt using sqlcipher3
    import sqlcipher3

    encrypted_conn = sqlcipher3.connect(ENCRYPTED_PATH)
    encrypted_conn.execute(f"PRAGMA key = '{db_key}'")
    encrypted_conn.execute("PRAGMA cipher_compatibility = 4")

    # Attach plaintext DB and copy data
    encrypted_conn.execute(f"ATTACH DATABASE '{DB_PATH}' AS plaintext KEY ''")
    encrypted_conn.execute("SELECT sqlcipher_export('main', 'plaintext')")
    encrypted_conn.execute("DETACH DATABASE plaintext")
    encrypted_conn.commit()

    # Verify
    cursor = encrypted_conn.execute(
        "SELECT count(*) FROM sqlite_master WHERE type='table'"
    )
    table_count = cursor.fetchone()[0]
    encrypted_conn.close()

    print(f"[OK] Encrypted DB created with {table_count} tables")

    # Replace original with encrypted
    try:
        os.remove(DB_PATH)
        shutil.move(ENCRYPTED_PATH, DB_PATH)
        print(f"[OK] Replaced {DB_PATH} with encrypted version")
    except PermissionError:
        print(f"[WARN] Cannot replace {DB_PATH} (file locked by another process)")
        print(f"[INFO] Encrypted DB saved as: {ENCRYPTED_PATH}")
        print()
        print("Please run the following commands manually after stopping the server:")
        print(f"  del {DB_PATH}")
        print(f"  move {ENCRYPTED_PATH} {DB_PATH}")
        print()
        print("=== Migration partially complete ===")
        return

    print()
    print("=== Migration complete ===")
    print(f"  Encrypted DB: {DB_PATH}")
    print(f"  Plaintext backup: {BACKUP_PATH}")
    print("  Encryption key: stored in Windows Credential Manager")
    print()
    print("You can delete the backup after verifying the server works correctly:")
    print(f"  del {BACKUP_PATH}")


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    main()
