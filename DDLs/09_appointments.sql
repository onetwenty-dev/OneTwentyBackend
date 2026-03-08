-- DDL: Appointments Table
-- Manages scheduled doctor-patient appointments

CREATE TABLE IF NOT EXISTS appointments (
    id           SERIAL PRIMARY KEY,
    doctor_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    patient_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    scheduled_at TIMESTAMP NOT NULL,
    duration_min INTEGER NOT NULL DEFAULT 30,
    type         VARCHAR(50) NOT NULL DEFAULT 'Follow-up',  -- 'Follow-up', 'Urgent', 'Review', 'Initial'
    notes        TEXT,
    status       VARCHAR(20) NOT NULL DEFAULT 'scheduled',  -- 'scheduled', 'completed', 'cancelled'
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT check_appt_different_users CHECK (doctor_id != patient_id)
);

CREATE INDEX IF NOT EXISTS idx_appointments_doctor      ON appointments(doctor_id);
CREATE INDEX IF NOT EXISTS idx_appointments_patient     ON appointments(patient_id);
CREATE INDEX IF NOT EXISTS idx_appointments_scheduled   ON appointments(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_appointments_status      ON appointments(status);
