from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List
from wms_app.database.database import get_db
from wms_app.routers.auth import require_role, get_current_user
from wms_app.models.auth import User, Role, Permission
from wms_app.schemas.auth import UserCreate, UserUpdate, User as UserSchema, RoleCreate, Role as RoleSchema
from wms_app.services.auth_service import AuthService

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="wms_app/templates")

@router.get("/", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Dashboard amministrativo - controllo permessi lato client con protezione sicura"""
    return templates.TemplateResponse("admin.html", {"request": request, "active_page": "admin"})

@router.get("/api/users", response_model=List[dict])
async def get_all_users(current_user = Depends(require_role("admin")), db: Session = Depends(get_db)):
    """Ottiene tutti gli utenti - solo per admin"""
    try:
        users = db.query(User).all()
        users_data = []
        for user in users:
            users_data.append({
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat(),
                "roles": [{"id": role.id, "name": role.name, "description": role.description} for role in user.roles]
            })
        
        print(f"Caricati {len(users_data)} utenti")
        return users_data
        
    except Exception as e:
        print(f"Errore caricamento utenti: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Errore database: {str(e)}")

@router.get("/api/roles", response_model=List[dict])
async def get_all_roles(current_user = Depends(require_role("admin")), db: Session = Depends(get_db)):
    """Ottiene tutti i ruoli con i loro permessi - solo per admin"""
    try:
        roles = db.query(Role).all()
        roles_data = []
        for role in roles:
            # Carica i permessi reali dal database
            permission_names = [perm.name for perm in role.permissions]
            roles_data.append({
                "id": role.id,
                "name": role.name,
                "description": role.description or "",
                "permissions": permission_names
            })
        
        print(f"✅ Caricati {len(roles_data)} ruoli con permessi")
        for role_data in roles_data:
            print(f"  - {role_data['name']}: {len(role_data['permissions'])} permessi")
        
        return roles_data
        
    except Exception as e:
        print(f"❌ Errore caricamento ruoli: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Errore database: {str(e)}")

@router.post("/api/users", response_model=UserSchema)
async def create_user(user_data: UserCreate, current_user = Depends(require_role("admin")), db: Session = Depends(get_db)):
    """Crea un nuovo utente - solo per admin"""
    try:
        user = AuthService.create_user(
            db=db,
            username=user_data.username,
            email=user_data.email,
            password=user_data.password,
            role_names=user_data.role_names
        )
        return user
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/api/users/{user_id}", response_model=UserSchema)
async def update_user(user_id: int, user_data: UserUpdate, current_user = Depends(require_role("admin")), db: Session = Depends(get_db)):
    """Aggiorna un utente - solo per admin"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    
    # Aggiorna i campi
    if user_data.username is not None:
        # Verifica che l'username non sia già in uso
        existing = db.query(User).filter(User.username == user_data.username, User.id != user_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Username già in uso")
        user.username = user_data.username
    
    if user_data.email is not None:
        # Verifica che l'email non sia già in uso
        existing = db.query(User).filter(User.email == user_data.email, User.id != user_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email già in uso")
        user.email = user_data.email
    
    if user_data.is_active is not None:
        user.is_active = user_data.is_active
    
    if user_data.role_names is not None:
        # Aggiorna i ruoli
        roles = db.query(Role).filter(Role.name.in_(user_data.role_names)).all()
        user.roles = roles
    
    db.commit()
    db.refresh(user)
    return user

@router.delete("/api/users/{user_id}")
async def delete_user(user_id: int, current_user = Depends(require_role("admin")), db: Session = Depends(get_db)):
    """Elimina un utente - solo per admin"""
    # Non permettere di eliminare se stesso
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Non puoi eliminare il tuo stesso account")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    
    db.delete(user)
    db.commit()
    return {"message": "Utente eliminato con successo"}


@router.post("/api/roles", response_model=RoleSchema)
async def create_role(role_data: RoleCreate, current_user = Depends(require_role("admin")), db: Session = Depends(get_db)):
    """Crea un nuovo ruolo - solo per admin"""
    # Verifica che il nome del ruolo non esista già
    existing_role = db.query(Role).filter(Role.name == role_data.name).first()
    if existing_role:
        raise HTTPException(status_code=400, detail="Nome ruolo già esistente")
    
    # Crea il ruolo
    role = Role(name=role_data.name, description=role_data.description)
    db.add(role)
    db.flush()  # Per ottenere l'ID del ruolo
    
    # Assegna i permessi se specificati
    if role_data.permissions:
        permissions = db.query(Permission).filter(Permission.name.in_(role_data.permissions)).all()
        role.permissions = permissions
    
    db.commit()
    db.refresh(role)
    return role

@router.put("/api/roles/{role_id}")
async def update_role(role_id: int, role_data: dict, current_user = Depends(require_role("admin")), db: Session = Depends(get_db)):
    """Aggiorna un ruolo e i suoi permessi - solo per admin"""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Ruolo non trovato")
    
    # Verifica che non si stia modificando i ruoli di sistema se hanno utenti assegnati
    if role.name in ["admin", "operatore", "cliente"] and role.users:
        if role_data.get("name") != role.name:
            raise HTTPException(status_code=400, detail="Non puoi modificare il nome dei ruoli di sistema con utenti assegnati")
    
    # Aggiorna nome e descrizione
    if "name" in role_data and role_data["name"] != role.name:
        # Verifica che il nuovo nome non esista già
        existing = db.query(Role).filter(Role.name == role_data["name"], Role.id != role_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Nome ruolo già esistente")
        role.name = role_data["name"]
    
    if "description" in role_data:
        role.description = role_data["description"]
    
    # Aggiorna permessi se specificati
    if "permissions" in role_data:
        permission_names = role_data["permissions"]
        permissions = db.query(Permission).filter(Permission.name.in_(permission_names)).all()
        role.permissions = permissions
    
    db.commit()
    db.refresh(role)
    return {"message": "Ruolo aggiornato con successo", "role": role}

@router.delete("/api/roles/{role_id}")
async def delete_role(role_id: int, current_user = Depends(require_role("admin")), db: Session = Depends(get_db)):
    """Elimina un ruolo - solo per admin"""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Ruolo non trovato")
    
    # Non permettere di eliminare ruoli di sistema
    if role.name in ["admin", "operatore", "cliente"]:
        raise HTTPException(status_code=400, detail="Non puoi eliminare i ruoli di sistema")
    
    # Non permettere di eliminare ruoli con utenti assegnati
    if role.users:
        raise HTTPException(status_code=400, detail=f"Impossibile eliminare il ruolo: {len(role.users)} utenti sono ancora assegnati")
    
    db.delete(role)
    db.commit()
    return {"message": "Ruolo eliminato con successo"}

@router.get("/api/permissions", response_model=List[dict])
async def get_all_permissions(current_user = Depends(require_role("admin")), db: Session = Depends(get_db)):
    """Ottiene tutti i permessi disponibili raggruppati per sezione - solo per admin"""
    permissions = db.query(Permission).all()
    
    # Raggruppa per sezione
    sections = {}
    for perm in permissions:
        if perm.section not in sections:
            sections[perm.section] = []
        sections[perm.section].append({
            "id": perm.id,
            "name": perm.name, 
            "description": perm.description,
            "action": perm.action
        })
    
    return [{"section": section, "permissions": perms} for section, perms in sections.items()]