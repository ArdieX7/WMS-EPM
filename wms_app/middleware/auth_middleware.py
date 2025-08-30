"""
Middleware di autenticazione centralizzato per FastAPI
Gestisce automaticamente l'autenticazione JWT per tutte le route protette
"""
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from typing import Optional, Callable, Any
import logging
from wms_app.database.database import get_db
from wms_app.services.jwt_service import JWTService
from wms_app.services.auth_service import AuthService
from wms_app.models.auth import User

logger = logging.getLogger(__name__)

class AuthMiddleware:
    """Middleware centralizzato per autenticazione JWT"""
    
    def __init__(self):
        self.security = HTTPBearer(auto_error=False)
        
        # Route che NON richiedono autenticazione
        self.public_routes = {
            "/",
            "/login",
            "/api/auth/login", 
            "/api/auth/refresh",
            "/api/auth/logout",
            "/static",
            "/favicon.ico",
            "/docs",
            "/redoc",
            "/openapi.json"
        }
    
    def is_public_route(self, path: str) -> bool:
        """Controlla se una route è pubblica"""
        # Exact match
        if path in self.public_routes:
            return True
        
        # Prefix match per static files
        for public_route in self.public_routes:
            if path.startswith(public_route + "/") or path.startswith(public_route):
                return True
        
        return False
    
    async def __call__(self, request: Request, call_next: Callable) -> Any:
        """Middleware principale"""
        path = request.url.path
        
        # Skip autenticazione per route pubbliche
        if self.is_public_route(path):
            response = await call_next(request)
            return response
        
        # Per API routes, usa autenticazione JWT
        if path.startswith("/api/"):
            return await self.handle_api_auth(request, call_next)
        
        # Per HTML pages, usa autenticazione con redirect
        return await self.handle_page_auth(request, call_next)
    
    async def handle_api_auth(self, request: Request, call_next: Callable) -> Any:
        """Gestisce autenticazione per API endpoints"""
        try:
            logger.info(f"🔐 API Auth middleware per: {request.url.path}")
            
            # Ottieni token dall'header Authorization
            auth_header = request.headers.get("authorization")
            logger.info(f"📡 Auth header presente: {bool(auth_header)}")
            
            if not auth_header or not auth_header.startswith("Bearer "):
                logger.warning(f"❌ Token mancante per {request.url.path}")
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Token di accesso richiesto"},
                    headers={"WWW-Authenticate": "Bearer"}
                )
            
            token = auth_header.split(" ")[1]
            
            # Verifica token JWT
            payload = JWTService.verify_access_token(token)
            if not payload:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Token non valido o scaduto"},
                    headers={"WWW-Authenticate": "Bearer"}
                )
            
            # Ottieni utente dal database
            db: Session = next(get_db())
            try:
                user = JWTService.get_user_from_token(db, token)
                if not user:
                    return JSONResponse(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        content={"detail": "Utente non trovato o disattivato"}
                    )
                
                # Aggiungi utente alla request per uso nei dependency
                request.state.current_user = user
                request.state.jwt_payload = payload
                
            finally:
                db.close()
            
            # Procedi con la richiesta
            response = await call_next(request)
            return response
            
        except Exception as e:
            logger.error(f"Errore in API auth middleware: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Errore interno del server"}
            )
    
    async def handle_page_auth(self, request: Request, call_next: Callable) -> Any:
        """Gestisce autenticazione per pagine HTML"""
        try:
            # Per le pagine HTML, controlliamo prima se c'è un token valido
            # Il frontend JavaScript gestirà l'autenticazione dettagliata
            
            # Se non c'è autenticazione, lasciamo che il frontend gestisca
            # Questo elimina il flash bianco permettendo al JS di controllare
            response = await call_next(request)
            
            # Aggiungi header per indicare che l'autenticazione è richiesta
            if path not in self.public_routes:
                response.headers["X-Auth-Required"] = "true"
            
            return response
            
        except Exception as e:
            logger.error(f"Errore in page auth middleware: {e}")
            # In caso di errore, procedi comunque
            return await call_next(request)

# Dependency per ottenere l'utente corrente dalle API
def get_current_user_from_middleware(request: Request) -> User:
    """Dependency per ottenere l'utente corrente dal middleware"""
    if not hasattr(request.state, 'current_user'):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utente non autenticato"
        )
    
    return request.state.current_user

# Dependency per controllo permessi
def require_permission(permission_name: str):
    """Dependency factory per controllare permessi specifici"""
    def permission_checker(request: Request):
        current_user = get_current_user_from_middleware(request)
        db: Session = next(get_db())
        try:
            if not AuthService.user_has_permission(db, current_user, permission_name):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permesso richiesto: {permission_name}"
                )
            return current_user
        finally:
            db.close()
    
    return permission_checker

# Dependency per controllo ruoli
def require_role(role_name: str):
    """Dependency factory per controllare ruoli specifici"""
    def role_checker(request: Request):
        current_user = get_current_user_from_middleware(request)
        if not AuthService.user_has_role(current_user, role_name):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Ruolo richiesto: {role_name}"
            )
        return current_user
    
    return role_checker