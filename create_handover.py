import os
import shutil

files_to_copy = [
    "backend/db/__init__.py",
    "backend/db/connection.py",
    "backend/db/schema.py",
    "backend/db/repositories.py",
    "backend/auth/__init__.py",
    "backend/auth/google_auth.py",
    "backend/auth/session_manager.py",
    "backend/auth/dependencies.py",
    "backend/services/__init__.py",
    "backend/services/logging_service.py",
    "backend/services/persistence_service.py",
    "backend/services/rollback_service.py",
    "backend/auth_routes.py",
    "backend/user_routes.py",
    "backend/app.py",
    "requirements.txt",
    "frontend/index.html",
    "frontend/app.js",
    "frontend/index.css",
    "test_infrastructure.py",
    ".env" # Include the env configuration (member 4 needs to see Google setup)
]

dest_dir = "Member1_Handover"

if not os.path.exists(dest_dir):
    os.makedirs(dest_dir)

for file in files_to_copy:
    src = file
    dst = os.path.join(dest_dir, file)
    
    # Create subdirectories if they don't exist
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    
    if os.path.exists(src):
        shutil.copy2(src, dst)
        print(f"Copied {src}")
    else:
        print(f"Could not find {src}")

print("Handover folder creation complete!")
