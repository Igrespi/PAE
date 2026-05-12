import sqlite3
import json
from datetime import date, datetime

def main():
    db = r"C:\Users\igres\Desktop\PythonProject\instance\prl.db"
    con = sqlite3.connect(db)
    cur = con.cursor()

    output = {}

    # 1. Administradores (users)
    try:
        users = cur.execute('SELECT id, username, email, dni, telefono, nombre, is_admin, created_at FROM users ORDER BY id').fetchall()
        output['admins'] = [{"id": u[0], "username": u[1], "email": u[2], "dni": u[3], "telefono": u[4], "nombre": u[5], "is_admin": bool(u[6]), "created_at": str(u[7])} for u in users]
    except Exception as e:
        output['admins'] = f"Error: {e}"

    # 2. Empleados
    try:
        emps = cur.execute('SELECT id, nombre, apellidos, dni, email, telefono, puesto, departamento, fecha_alta, activo, created_at FROM employees ORDER BY id').fetchall()
        output['employees'] = [{"id": e[0], "nombre": e[1], "apellidos": e[2], "dni": e[3], "email": e[4], "telefono": e[5], "puesto": e[6], "departamento": e[7], "fecha_alta": str(e[8]), "activo": bool(e[9]), "created_at": str(e[10])} for e in emps]
    except Exception as e:
        output['employees'] = f"Error: {e}"

    # 3. Clientes
    try:
        clients = cur.execute('SELECT id, nombre, email, telefono, notas, created_at FROM clients ORDER BY id').fetchall()
        output['clients'] = [{"id": c[0], "nombre": c[1], "email": c[2], "telefono": c[3], "notas": c[4], "created_at": str(c[5])} for c in clients]
    except Exception as e:
        output['clients'] = f"Error: {e}"


    con.close()

    print("--- BASE DE DATOS ACTUAL ---")
    print(json.dumps(output, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
