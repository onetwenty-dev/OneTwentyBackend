-- New migration to add dob column to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS dob DATE;

-- Migrate existing dob from additional_data if it exists
UPDATE users 
SET dob = (additional_data->>'dob')::DATE 
WHERE additional_data ? 'dob' AND dob IS NULL;
