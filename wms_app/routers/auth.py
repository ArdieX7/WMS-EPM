from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from wms_app.database.database import get_db
from wms_app.services.auth_service import AuthService
from wms_app.services.jwt_service import JWTService, ACCESS_TOKEN_EXPIRE_MINUTES
from wms_app.schemas.auth import UserLogin, Token, User, UserWithPermissions, RefreshTokenRequest
from wms_app.models.auth import User as UserModel
from wms_app.middleware.auth_middleware import get_current_user_from_middleware

router = APIRouter(prefix="/api/auth", tags=["authentication"])
security = HTTPBearer()

@router.post("/login", response_model=dict)
async def login(user_login: UserLogin, db: Session = Depends(get_db)):
    """Endpoint per il login utente con JWT e refresh token"""
    user = AuthService.authenticate_user(db, user_login.username, user_login.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username o password non corretti",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Crea tokens (access JWT + refresh token)
    tokens = AuthService.create_tokens(db, user)
    
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "token_type": tokens["token_type"],
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60  # secondi
    }

@router.post("/logout")
async def logout(refresh_token_data: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Endpoint per il logout che revoca il refresh token"""
    success = AuthService.logout_user(db, refresh_token_data.refresh_token)
    
    if success:
        return {"message": "Logout effettuato con successo"}
    else:
        return {"message": "Logout effettuato (token già scaduto)"}

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    """Dependency legacy per ottenere l'utente corrente dal token JWT"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token di accesso richiesto",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    user = AuthService.get_user_from_token(db, token)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token non valido o utente non trovato",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user

@router.post("/refresh")
async def refresh_token(refresh_data: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Endpoint per rinnovare i token usando refresh token"""
    new_tokens = AuthService.refresh_tokens(db, refresh_data.refresh_token)
    
    if not new_tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token non valido o scaduto",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return {
        "access_token": new_tokens["access_token"],
        "refresh_token": new_tokens["refresh_token"],
        "token_type": new_tokens["token_type"],
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }

@router.get("/me", response_model=UserWithPermissions)
async def get_current_user_info(current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    """Ottiene le informazioni dell'utente corrente con i suoi permessi"""
    permissions = AuthService.get_user_permissions(db, current_user)
    
    user_dict = {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at,
        "roles": [{"id": role.id, "name": role.name, "description": role.description} for role in current_user.roles],
        "permissions": permissions
    }
    
    return user_dict

# Dependency per controllare se l'utente ha un permesso specifico
def require_permission(permission_name: str):
    def permission_checker(current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
        if not AuthService.user_has_permission(db, current_user, permission_name):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permesso richiesto: {permission_name}"
            )
        return current_user
    return permission_checker

# Dependency per controllare se l'utente ha un ruolo specifico
def require_role(role_name: str):
    def role_checker(current_user: UserModel = Depends(get_current_user)):
        if not AuthService.user_has_role(current_user, role_name):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Ruolo richiesto: {role_name}"
            )
        return current_user
    return role_checker

# Funzione helper per controllare permessi senza sollevare eccezioni
def check_user_permission_soft(request: Request, db: Session, permission_name: str):
    """
    Controlla se l'utente ha un permesso specifico senza sollevare eccezioni.
    Restituisce (user, has_permission) o (None, False) se non autenticato.
    """
    try:
        # Prova a leggere il cookie o session (per ora usiamo approccio semplificato)
        # In questo caso, dato che non abbiamo session, restituiamo sempre False
        # Questo forzerà l'utente a usare l'interfaccia client-side
        return None, False
    except:
        return None, False