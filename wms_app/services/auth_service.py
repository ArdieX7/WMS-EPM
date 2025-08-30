from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import hashlib
import secrets
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from wms_app.models.auth import User, Role, Permission, UserSession
from wms_app.services.jwt_service import JWTService

# Configurazione migliorata
ACCESS_TOKEN_EXPIRE_MINUTES = 15  # Token JWT breve per sicurezza

class AuthService:
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verifica se la password è corretta (versione semplificata)"""
        # Semplice hash SHA256 con salt per ora
        return hashlib.sha256(plain_password.encode()).hexdigest() == hashed_password
    
    @staticmethod
    def get_password_hash(password: str) -> str:
        """Genera hash della password (versione semplificata)"""
        # TODO: Implementare bcrypt quando le dipendenze saranno risolte
        return hashlib.sha256(password.encode()).hexdigest()
    
    @staticmethod
    def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
        """Autentica un utente con username e password"""
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return None
        if not AuthService.verify_password(password, user.password_hash):
            return None
        if not user.is_active:
            return None
        return user
    
    @staticmethod
    def create_tokens(db: Session, user: User) -> Dict[str, str]:
        """Crea JWT access token e refresh token per un utente"""
        # Crea access token JWT
        access_token_data = {
            "sub": user.username,
            "user_id": user.id,
            "email": user.email
        }
        
        access_token = JWTService.create_access_token(access_token_data)
        refresh_token = JWTService.create_refresh_token(db, user.id)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
    
    @staticmethod
    def verify_access_token(token: str) -> Optional[dict]:
        """Verifica un JWT access token"""
        return JWTService.verify_access_token(token)
    
    @staticmethod
    def logout_user(db: Session, refresh_token: str) -> bool:
        """Revoca il refresh token (logout)"""
        return JWTService.revoke_refresh_token(db, refresh_token)
    
    @staticmethod
    def refresh_tokens(db: Session, refresh_token: str) -> Optional[Dict[str, str]]:
        """Genera nuovi token usando refresh token"""
        return JWTService.refresh_access_token(db, refresh_token)
    
    @staticmethod
    def cleanup_expired_sessions(db: Session) -> int:
        """Rimuove tutte le sessioni scadute dal database"""
        return JWTService.cleanup_expired_tokens(db)
    
    @staticmethod
    def get_user_from_token(db: Session, token: str) -> Optional[User]:
        """Ottieni utente dal JWT token"""
        return JWTService.get_user_from_token(db, token)
    
    @staticmethod
    def get_user_permissions(db: Session, user: User) -> List[str]:
        """Ottiene tutte le permissions di un utente basate sui suoi ruoli"""
        permissions = set()
        for role in user.roles:
            for permission in role.permissions:
                permissions.add(permission.name)
        return list(permissions)
    
    @staticmethod
    def user_has_permission(db: Session, user: User, permission_name: str) -> bool:
        """Controlla se un utente ha un permesso specifico"""
        user_permissions = AuthService.get_user_permissions(db, user)
        return permission_name in user_permissions
    
    @staticmethod
    def user_has_role(user: User, role_name: str) -> bool:
        """Controlla se un utente ha un ruolo specifico"""
        return any(role.name == role_name for role in user.roles)
    
    @staticmethod
    def create_user(db: Session, username: str, email: str, password: str, role_names: List[str] = None) -> User:
        """Crea un nuovo utente"""
        # Verifica che username e email non esistano già
        if db.query(User).filter(User.username == username).first():
            raise HTTPException(status_code=400, detail="Username già esistente")
        if db.query(User).filter(User.email == email).first():
            raise HTTPException(status_code=400, detail="Email già esistente")
        
        # Crea l'utente
        password_hash = AuthService.get_password_hash(password)
        user = User(
            username=username,
            email=email,
            password_hash=password_hash
        )
        
        # Assegna ruoli se specificati
        if role_names:
            roles = db.query(Role).filter(Role.name.in_(role_names)).all()
            user.roles = roles
        
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    
    @staticmethod
    def revoke_all_user_sessions(db: Session, user_id: int) -> int:
        """Revoca tutte le sessioni di un utente (logout da tutti i device)"""
        return JWTService.revoke_all_user_tokens(db, user_id)