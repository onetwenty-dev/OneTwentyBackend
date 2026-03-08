-- DDL: Doctor Profiles Table
-- Stores extended profile info for users with role='doctor'

CREATE TABLE IF NOT EXISTS doctor_profiles (
    user_id        INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    specialty      VARCHAR(255),
    license_number VARCHAR(100),
    clinic_name    VARCHAR(255),
    clinic_address TEXT,
    phone          VARCHAR(50),
    bio            TEXT,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_doctor_profiles_user ON doctor_profiles(user_id);
