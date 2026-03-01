import os
import sys

# Add current directory to path so we can import 'app'
sys.path.append(os.getcwd())

from app.db.session import get_db_connection
from app.services.auth import AuthService
from app.services.entries import EntriesService
from app.repositories.user import UserRepository
from app.repositories.entries import EntriesRepository
from app.schemas.auth import UserCreate, UserLogin
from app.core import security
from app.core.config import settings

def help_me():
    print("Available Imports:")
    print("  - AuthService, EntriesService")
    print("  - UserRepository, EntriesRepository")
    print("  - UserCreate, UserLogin")
    print("  - get_db_connection()")
    print("  - security, settings")
    print("\nExample:")
    print("  repo = UserRepository()")
    print("  user = repo.get_by_email('test@example.com')")

print("----------------------------------------------------------------")
print("OneTwenty SaaS Shell (like django shell)")
print("----------------------------------------------------------------")
help_me()
print("")

# Launch interactive shell
import code
code.interact(local=locals())
