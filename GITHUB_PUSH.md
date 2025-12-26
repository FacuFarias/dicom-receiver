# Instrucciones para Push a GitHub

## 📋 Estado Actual

El repositorio local está completamente preparado y listo para subirse a GitHub.

**Ubicación:** `/home/ubuntu/DICOMReceiver`  
**URL remoto:** `https://github.com/FacuFarias/dicom-receiver.git`  
**Rama:** `master`  
**Commits:** 1 (v1.0 stable)  

## 🚀 Para Subir a GitHub

### Paso 1: Autenticación

**Opción A - Usando Personal Access Token (Recomendado):**

1. Ve a GitHub → Settings → Developer settings → Personal access tokens
2. Genera un nuevo token con permisos `repo`
3. Copia el token

**Opción B - Usando SSH:**

1. Genera clave SSH (si no tienes): `ssh-keygen -t ed25519 -C "tu-email@example.com"`
2. Agrega la clave pública en GitHub → Settings → SSH Keys

### Paso 2: Hacer Push

**Con HTTPS:**
```bash
cd /home/ubuntu/DICOMReceiver
git push -u origin master
# Te pedirá usuario y contraseña/token
```

**Con SSH:**
```bash
cd /home/ubuntu/DICOMReceiver
git branch -M main
git push -u origin main
```

## ✅ Lo que se subirá

- ✓ 50 archivos
- ✓ Todas las carpetas (tests, good_bd, dicom_storage, pixel_extraction)
- ✓ Documentación completa
- ✓ Código fuente

## 📝 Verificación

Después del push, verifica:

```bash
# Ver estado
git status

# Ver commits
git log --oneline

# Ver remoto
git remote -v
```

## 🔒 Archivos Ignorados (en .gitignore)

Estos archivos NO se subirán:
- `dicom_storage/` (archivos DICOM)
- `__pycache__/`
- `*.log`
- `.env`
- Archivos compilados Python

## 📞 Soporte

Si tienes problemas:
1. Verifica las credenciales de GitHub
2. Asegúrate de tener permisos en el repositorio
3. Intenta con SSH si HTTPS falla
4. Revisa la conexión a internet

---

**Versión:** 1.0  
**Estado:** Listo para subir
