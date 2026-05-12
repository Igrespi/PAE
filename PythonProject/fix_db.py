import sqlite3

def run_fix():
    db = r"C:\Users\igres\Desktop\PythonProject\instance\prl.db"
    con = sqlite3.connect(db)
    cur = con.cursor()

    # 1. Eliminar a todos los que no son el admin con id=1
    cur.execute("DELETE FROM users WHERE id != 1;")

    # 2. SQLite no permite DROP COLUMN de manera directa en todas las versiones fácilmente.
    # Así que creamos una tabla nueva sin employee_id, pasamos los datos, y reemplazamos.

    cur.execute("""
    CREATE TABLE users_new (
        id INTEGER NOT NULL PRIMARY KEY,
        username VARCHAR(80) NOT NULL UNIQUE,
        email VARCHAR(120) NOT NULL UNIQUE,
        dni VARCHAR(20),
        telefono VARCHAR(20),
        password_hash VARCHAR(256) NOT NULL,
        nombre VARCHAR(100),
        is_admin BOOLEAN,
        created_at DATETIME
    );
    """)

    cur.execute("""
    INSERT INTO users_new (id, username, email, dni, telefono, password_hash, nombre, is_admin, created_at)
    SELECT id, username, email, dni, telefono, password_hash, nombre, is_admin, created_at
    FROM users;
    """)

    cur.execute("DROP TABLE users;")
    cur.execute("ALTER TABLE users_new RENAME TO users;")

    con.commit()
    con.close()
    print("Limpieza completada correctamente.")

if __name__ == "__main__":
    run_fix()

