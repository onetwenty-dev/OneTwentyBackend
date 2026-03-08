-- DDL: Patient Invite Codes Table
-- Doctors generate short-lived codes; patients submit them to connect

CREATE TABLE IF NOT EXISTS patient_invites (
    id         SERIAL PRIMARY KEY,
    doctor_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    code       VARCHAR(8) UNIQUE NOT NULL,       -- 6-char alphanumeric invite code
    expires_at TIMESTAMP NOT NULL,               -- 24-hour TTL by default
    used_at    TIMESTAMP,                        -- NULL = unused
    patient_id INTEGER REFERENCES users(id),     -- populated when claimed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_patient_invites_code   ON patient_invites(code);
CREATE INDEX IF NOT EXISTS idx_patient_invites_doctor ON patient_invites(doctor_id);
