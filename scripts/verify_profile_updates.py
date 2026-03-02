import json
import psycopg2
from app.core.config import settings
from app.repositories.user import UserRepository
from app.schemas.auth import UserUpdateDetails
from datetime import date

def verify_profile_updates():
    repo = UserRepository()
    email = "ayusht2d@gmail.com" # Existing user from Postman
    
    print(f"Checking user: {email}")
    user = repo.get_by_email(email)
    if not user:
        print("User not found. Please run with a valid user email.")
        return

    user_id = user["id"]
    print(f"Initial Name: {user.get('name')}, DOB: {user.get('dob')}")

    # Test Repository directly
    test_name = "Ayush Verified"
    test_dob = date(2000, 5, 20)
    test_additional = {"verified": True, "diabetes_type": "type1"}
    
    print("Updating via repository...")
    repo.update_user_profile(user_id, name=test_name, dob=test_dob, additional_data_updates=test_additional)
    
    updated_user = repo.get_by_email(email)
    print(f"Updated Name: {updated_user.get('name')}, DOB: {updated_user.get('dob')}")
    print(f"Additional Data: {updated_user.get('additional_data')}")

    assert updated_user["name"] == test_name
    assert str(updated_user["dob"]) == str(test_dob)
    assert updated_user["additional_data"].get("verified") is True
    assert updated_user["additional_data"].get("diabetes_type") == "type1"
    
    print("Profile verification SUCCESS")

if __name__ == "__main__":
    verify_profile_updates()
