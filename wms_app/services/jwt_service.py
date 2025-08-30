"""
JWT Service moderno per WMS EPM
Sistema di autenticazione basato su JWT standard con refresh token
"""
import jwt
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from wms_app.models.auth import User, UserSession

# Configurazione JWT sicura
SECRET_KEY = "wms_epm_jwt_secret_2025_super_secure_key"  # TODO: Spostare in variabile ambiente
REFRESH_SECRET_KEY = "wms_epm_refresh_secret_2025_ultra_secure"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15  # Token breve per sicurezza
REFRESH_TOKEN_EXPIRE_DAYS = 7    # Refresh token più lungo

class JWTService:
    """Service per gestione JWT moderna e sicura"""
    
    @staticmethod
    def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Crea un JWT access token"""
        to_encode = data.copy()
        
        # Imposta scadenza
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        # Claims standard JWT
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        })
        
        # Genera JWT
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def create_refresh_token(db: Session, user_id: int) -> str:
        """Crea un refresh token e lo salva nel database"""
        # Genera token sicuro
        refresh_token = secrets.token_urlsafe(32)
        expire_time = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        
        # Rimuovi vecchi refresh token per questo utente (max 1 per utente)
        db.query(UserSession).filter(UserSession.user_id == user_id).delete()
        
        # Salva nuovo refresh token
        session = UserSession(
            token=refresh_token,
            user_id=user_id,
            expires_at=expire_time
        )
        db.add(session)
        db.commit()
        
        return refresh_token
    
    @staticmethod
    def verify_access_token(token: str) -> Optional[Dict[str, Any]]:
        """Verifica un JWT access token"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            
            # Verifica che sia un access token
            if payload.get("type") != "access":
                return None
                
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.JWTError:
            return None
    
    @staticmethod
    def verify_refresh_token(db: Session, refresh_token: str) -> Optional[User]:
        """Verifica un refresh token dal database"""
        session = db.query(UserSession).filter(UserSession.token == refresh_token).first()
        
        if not session:
            return None
        
        # Controlla scadenza
        if datetime.utcnow() > session.expires_at:
            # Token scaduto - rimuovilo
            db.delete(session)
            db.commit()
            return None
        
        return session.user
    
    @staticmethod
    def refresh_access_token(db: Session, refresh_token: str) -> Optional[Dict[str, str]]:
        """Genera nuovo access token usando refresh token"""
        user = JWTService.verify_refresh_token(db, refresh_token)
        
        if not user or not user.is_active:
            return None
        
        # Crea nuovo access token
        access_token_data = {
            "sub": user.username,
            "user_id": user.id,
            "email": user.email
        }
        
        new_access_token = JWTService.create_access_token(access_token_data)
        
        # Opzionalmente rota il refresh token per maggiore sicurezza
        new_refresh_token = JWTService.create_refresh_token(db, user.id)
        
        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer"
        }
    
    @staticmethod
    def revoke_refresh_token(db: Session, refresh_token: str) -> bool:
        """Revoca un refresh token (logout)"""
        session = db.query(UserSession).filter(UserSession.token == refresh_token).first()
        
        if session:
            db.delete(session)
            db.commit()
            return True
        
        return False
    
    @staticmethod
    def revoke_all_user_tokens(db: Session, user_id: int) -> int:
        """Revoca tutti i token di un utente"""
        count = db.query(UserSession).filter(UserSession.user_id == user_id).count()
        db.query(UserSession).filter(UserSession.user_id == user_id).delete()
        db.commit()
        return count
    
    @staticmethod
    def cleanup_expired_tokens(db: Session) -> int:
        """Pulisci tutti i token scaduti"""
        expired_count = db.query(UserSession).filter(
            UserSession.expires_at < datetime.utcnow()
        ).count()
        
        db.query(UserSession).filter(
            UserSession.expires_at < datetime.utcnow()
        ).delete()
        db.commit()
        
        return expired_count
    
    @staticmethod
    def get_user_from_token(db: Session, token: str) -> Optional[User]:
        """Ottieni utente dal JWT access token"""
        payload = JWTService.verify_access_token(token)
        
        if not payload:
            return None
        
        username = payload.get("sub")
        if not username:
            return None
        
        user = db.query(User).filter(User.username == username).first()
        return user if user and user.is_active else None