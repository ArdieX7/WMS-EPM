# 🔄 Guida Recovery Git - Sovrascrivere Remote con Locale

## 🎯 Obiettivo
Sostituire completamente la versione remote (GitHub) con la tua versione locale aggiornata, dopo aver fatto per errore un pull che ha sovrascritto il tuo lavoro locale.

## ⚠️ IMPORTANTE - Backup Completato
✅ **Backup creato in**: `../WMS_BACKUP_YYYYMMDD/`  
✅ **File superflui spostati in**: `archive_files_to_review/`  
✅ **Repository pulito e pronto**

## 🚀 Strategia di Recovery (3 Opzioni)

### **OPZIONE 1: Force Push Diretto (Consigliato)**

```bash
# 1. Verifica stato attuale
git status
git log --oneline -5

# 2. Aggiungi tutti i file puliti
git add .
git commit -m "🚀 WMS Production Ready - Complete codebase with deployment tools

- ✅ Complete WMS application with all features
- ✅ Production deployment guides and scripts  
- ✅ Docker configuration for VPS deployment
- ✅ Nginx production configuration with SSL
- ✅ Automated backup and monitoring scripts
- ✅ Cleaned repository structure
- 🗂️ Moved test files to archive_files_to_review/

🛠️ Ready for VPS deployment on Hetzner"

# 3. Force push per sovrascrivere remote
git push --force-with-lease origin main

# Se --force-with-lease fallisce, usa:
# git push --force origin main
```

### **OPZIONE 2: Nuovo Branch + Pull Request**

```bash
# 1. Crea nuovo branch con versione corrente
git checkout -b production-ready-wms
git add .
git commit -m "🚀 WMS Production Ready - Complete deployment suite"

# 2. Push nuovo branch
git push origin production-ready-wms

# 3. Su GitHub: crea Pull Request da production-ready-wms a main
# 4. Mergia il PR per sovrascrivere main
```

### **OPZIONE 3: Reset Hard Remote (Solo se sei l'unico collaboratore)**

```bash
# 1. Commit locale
git add .
git commit -m "🚀 WMS Production Ready"

# 2. Reset del branch remote main
git branch -D main  # elimina branch locale main
git checkout -b main  # crea nuovo main dalla versione corrente
git push --force origin main  # forza il push
```

## 🎛️ Comandi Pre-Push

### Verifica Stato Attuale
```bash
# Controlla cosa hai in locale
git status
git log --oneline -3

# Controlla differenze con remote
git fetch origin
git log --oneline HEAD..origin/main  # cosa ha remote che tu non hai
git log --oneline origin/main..HEAD  # cosa hai tu che remote non ha
```

### Test Repository Pulito
```bash
# Verifica che non ci siano file indesiderati
git ls-files | grep -E '\.(log|tmp|pyc|db)$'  # dovrebbe essere vuoto
git ls-files | grep -E '^(test_|debug_)'     # dovrebbe essere vuoto

# Verifica dimensione repository
du -sh .git/
```

## 📋 Checklist Pre-Push

- [ ] ✅ Backup locale completato
- [ ] ✅ File superflui spostati in `archive_files_to_review/`
- [ ] ✅ .gitignore aggiornato
- [ ] ✅ Tutti i file deployment presenti:
  - [ ] `deploy_guide_vps.md`
  - [ ] `DEPLOYMENT_QUICKSTART.md`
  - [ ] `docker-compose.production.yml`
  - [ ] `nginx-production.conf`
  - [ ] `.env.production`
  - [ ] `scripts/setup-server.sh`
  - [ ] `scripts/backup-wms.sh`
  - [ ] `scripts/monitor-wms.sh`

## 🚨 Recovery da Errori

### Se il Force Push Fallisce
```bash
# Verifica conflitti
git fetch origin
git status

# Risolvi forzando (ATTENZIONE: sovrascrive tutto su remote)
git push --force origin main
```

### Se Perdi il Tuo Lavoro Locale
```bash
# Ripristina dal backup
cd /mnt/c
cp -r WMS_BACKUP_YYYYMMDD WMS_EPM_RECOVERED
cd WMS_EPM_RECOVERED

# Ricollega a Git
git remote add origin https://github.com/TUO_ACCOUNT/WMS_EPM.git
git add .
git commit -m "🔄 Recovered from backup"
git push --force origin main
```

### Se Vuoi Mantenere Solo Alcuni Commit Remote
```bash
# Interactive rebase per scegliere commit
git fetch origin
git rebase -i origin/main

# O cherry-pick commit specifici
git cherry-pick COMMIT_HASH
```

## 🎯 Comando Finale Raccomandato

```bash
# UNA RIGA PER FARE TUTTO:
git add . && git commit -m "🚀 WMS Production Ready - Complete deployment suite" && git push --force-with-lease origin main
```

## 🛡️ Sicurezza Post-Push

### Verifica Successo
```bash
# Controlla che tutto sia pushato
git status
git log --oneline origin/main -3

# Verifica su GitHub che i file siano presenti
curl -s https://api.github.com/repos/TUO_ACCOUNT/WMS_EPM/contents | grep name
```

### Setup Protezione Branch (Consigliato per futuro)
Su GitHub:
1. Settings → Branches  
2. Add rule per `main`
3. ✅ Require pull request reviews
4. ✅ Dismiss stale reviews
5. ✅ Require status checks

## 📞 Se Hai Problemi

1. **Non panico**: Il tuo backup è al sicuro
2. **Controlla errore**: `git status` e leggi messaggio
3. **Usa force**: `git push --force origin main` se necessario
4. **Recovery**: Usa backup se qualcosa va male

---

## 🎉 Dopo il Push Riuscito

1. **Verifica su GitHub** che tutti i file siano presenti
2. **Clona in una nuova directory** per test:
   ```bash
   git clone https://github.com/TUO_ACCOUNT/WMS_EPM.git test_clone
   cd test_clone
   ls -la  # verifica struttura
   ```
3. **Elimina `archive_files_to_review/`** se non serve più
4. **Procedi con deployment VPS** usando le guide create!

---
**Creato**: $(date +"%Y-%m-%d %H:%M")  
**Backup in**: `../WMS_BACKUP_*`