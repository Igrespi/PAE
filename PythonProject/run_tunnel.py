"""
Arranca la app Flask en modo local.

Uso:
    python run_tunnel.py
"""


def main():
    from app import create_app

    app = create_app()
    port = 5000

    print("=" * 55)
    print("  Gestion PRL - Arranque (modo local)")
    print("=" * 55)
    print(f"  URL local:    http://localhost:{port}")
    print("  URL red:      http://0.0.0.0:5000")
    print()
    print("  Pulsa Ctrl+C para detener.")
    print("=" * 55)
    print()
    app.run(host='0.0.0.0', port=port, debug=False)


if __name__ == '__main__':
    main()
