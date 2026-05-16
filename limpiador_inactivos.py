import firebase_admin
from firebase_admin import credentials, firestore
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import os
import json

# --- ADAPTACIÓN PARA GITHUB ACTIONS (LEER SECRETOS) ---
# Si corre en GitHub, recreamos los archivos JSON a partir de las variables de entorno
if "FIREBASE_SECRETS_JSON" in os.environ:
    with open("firebase_secrets.json", "w") as f:
        f.write(os.environ["FIREBASE_SECRETS_JSON"])

if "GOOGLE_TOKEN_JSON" in os.environ:
    with open("token.json", "w") as f:
        f.write(os.environ["GOOGLE_TOKEN_JSON"])
# ------------------------------------------------------

# 1. INICIALIZAR SERVICIOS (Firebase y Google Drive API)
if not firebase_admin._apps:
    cred_fb = credentials.Certificate("firebase_secrets.json")
    firebase_admin.initialize_app(cred_fb)

db = firestore.client()

SCOPES = ["https://www.googleapis.com/auth/drive"]
creds_google = None
if os.path.exists('token.json'):
    creds_google = Credentials.from_authorized_user_file('token.json', SCOPES)

if creds_google and creds_google.expired and creds_google.refresh_token:
    creds_google.refresh(Request())

drive_service = build('drive', 'v3', credentials=creds_google)

def ejecutar_limpieza_30_dias():
    print(f"⏰ [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Iniciando revisión diaria de inactividad...")
    
    usuarios_ref = db.collection("usuarios_inventario")
    usuarios = usuarios_ref.get()
    
    fecha_limite = datetime.now() - timedelta(days=30)
    cupos_liberados = 0

    for doc in usuarios:
        datos = doc.to_dict()
        email = datos.get("email")
        sheet_id = datos.get("sheet_id")
        
        ultima_actividad = datos.get("ultima_actividad")
        
        if ultima_actividad:
            ultima_actividad = ultima_actividad.replace(tzinfo=None)
            
            if ultima_actividad < fecha_limite:
                print(f"⚠️ Usuario inactivo detectado: {email} (Última actividad: {ultima_actividad.strftime('%Y-%m-%d')})")
                
                if sheet_id:
                    try:
                        drive_service.files().delete(fileId=sheet_id).execute()
                        print(f"  🗑️ Google Sheet ({sheet_id}) eliminado con éxito.")
                    except Exception as e:
                        print(f"  ❌ No se pudo borrar el archivo de Drive: {e}")
                
                usuarios_ref.document(doc.id).delete()
                print(f"  ✅ Registro de {email} eliminado de Firebase. Cupo liberado.")
                cupos_liberados += 1

    print(f"✨ Proceso terminado. Se liberaron {cupos_liberados} cupos de la plataforma.\n")

if __name__ == "__main__":
    ejecutar_limpieza_30_dias()
    
