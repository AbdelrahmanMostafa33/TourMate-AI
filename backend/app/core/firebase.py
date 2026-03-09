import firebase_admin
from firebase_admin import credentials, auth
from app.core.config import settings

cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS)
firebase_admin.initialize_app(cred)

def verify_token(token: str) -> dict:
   
    try:
        decoded = auth.verify_id_token(token)
        return decoded
    except Exception as e:
        return None