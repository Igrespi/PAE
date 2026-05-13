# PAE
Instrucciones para cargar librerias:

1) Abrir powershell en la carpeta PythonProject
2) Poner los siguientes comandos:
  py -m venv .venv
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass     (Si te da opciones, pon que sí)
  .\.venv\Scripts\Activate.ps1
  
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
  
  python run_tunnel.py
