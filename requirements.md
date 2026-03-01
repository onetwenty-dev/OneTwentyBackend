# Requirements Document

## Introduction

OneTwenty is a multi-tenant cloud-based SaaS solution that provides a unified interface for continuous glucose monitoring (CGM) data management across all major CGM brands. The platform addresses the fragmented experience Type 1 diabetics face with proprietary apps, limited sharing capabilities, and irregular features of different CGM brands.

Built from scratch (not a fork), the platform follows the OneTwenty API protocol for compatibility while introducing multi-tenant architecture, AI-powered analysis, hardware integrations, and comprehensive sharing features for patients, families, and healthcare providers.

## Glossary

- **CGM**: Continuous Glucose Monitor - a wearable device that tracks blood glucose levels continuously
- **Platform**: The multi-tenant diabetes management SaaS system
- **Patient**: A Type 1 diabetic user who uploads and manages their CGM data
- **Family Member**: A user with read-only access to a patient's data for monitoring purposes
- **Doctor**: A healthcare provider with access to multiple patients' data through a specialized dashboard
- **Tenant**: An isolated data space for a patient and their authorized users
- **Uploader**: A service component that retrieves CGM data from device manufacturers and pushes to our server/DB
- **Treatment**: A logged event such as insulin dose, carbohydrate intake, or exercise
- **OneTwenty_API**: The API protocol used by the open-source OneTwenty project
- **Real_Time_Sync**: Data synchronization occurring at 1-3 minute intervals
- **Widget**: A persistent UI component displaying glucose data on device home screens
- **Desk Clock**: Custom hardware device displaying real-time glucose readings
- **AI Agent**: An AI system that analyzes glucose patterns and assists with logging

## Requirements

### Requirement 1: CGM Data Integration

**User Story:** As a patient, I want to automatically upload data from my CGM device, so that I don't have to manually enter glucose readings.

#### Acceptance Criteria

1. THE Platform SHALL provide built-in uploaders for Libre, Vitatok, Linx, Trackky, and Dexcom CGM brands
2. WHEN a patient connects their CGM account, THE Uploader SHALL authenticate with the manufacturer's API
3. THE Uploader SHALL retrieve new glucose readings at intervals specified by the manufacturer's API limits
4. WHEN new CGM data is received, THE Platform SHALL store it in the patient's tenant with timestamps
5. IF an uploader fails to retrieve data, THEN THE Platform SHALL log the error and retry with exponential backoff
6. THE Platform SHALL follow the OneTwenty API protocol for CGM data storage and retrieval

### Requirement 2: Treatment Logging via PWA

**User Story:** As a patient, I want to log treatments (insulin, carbs, exercise) through a mobile app, so that I can track factors affecting my glucose levels.

#### Acceptance Criteria

1. THE Platform SHALL provide a PWA that works offline and syncs when connectivity is restored
2. WHEN a patient logs a treatment, THE PWA SHALL store it locally and sync to the server within 1-3 minutes
3. THE PWA SHALL support logging insulin doses with type (bolus/basal) and units
4. THE PWA SHALL support logging carbohydrate intake with grams and meal type
5. THE PWA SHALL support logging exercise with type, duration, and intensity
6. WHEN treatments are synced, THE Platform SHALL associate them with the nearest glucose readings
7. THE PWA SHALL be installable on iOS and Android devices

### Requirement 3: Real-Time Monitoring Widgets

**User Story:** As a patient or family member, I want to see current glucose levels on my device home screen, so that I can monitor without opening the app.

#### Acceptance Criteria

1. THE Platform SHALL provide always-on widgets for iOS and Android home screens
2. WHEN new glucose data is available, THE Widget SHALL update within 3 minutes
3. THE Widget SHALL display current glucose value, trend arrow, and time of last reading
4. THE Widget SHALL use color coding (green/yellow/red) to indicate glucose range status
5. IF glucose data is stale (>15 minutes old), THEN THE Widget SHALL display a warning indicator
6. THE Widget SHALL support multiple size configurations (small, medium, large)

### Requirement 4: Persistent Notifications

**User Story:** As a patient or family member, I want to receive alerts for critical glucose levels, so that I can take immediate action.

#### Acceptance Criteria

1. WHEN glucose levels fall below a configured low threshold, THE Platform SHALL send a high-priority notification
2. WHEN glucose levels rise above a configured high threshold, THE Platform SHALL send a high-priority notification
3. THE Platform SHALL allow patients to configure custom threshold values for low and high alerts
4. THE Platform SHALL support notification delivery via push notifications, SMS, and email
5. WHEN a notification is sent, THE Platform SHALL log the alert event with timestamp and glucose value
6. THE Platform SHALL prevent notification spam by enforcing a minimum interval between repeated alerts

### Requirement 5: Blood Glucose Desk Clock Integration

**User Story:** As a patient, I want to display my current glucose reading on a desk clock device, so that I can monitor my levels while working without checking my phone.

#### Acceptance Criteria

1. THE Platform SHALL provide an API endpoint for desk clock devices to retrieve current glucose readings
2. WHEN a desk clock requests data, THE Platform SHALL authenticate the device using a secure token
3. THE Platform SHALL return the most recent glucose value, trend, and timestamp in a lightweight format
4. THE Desk_Clock SHALL poll for new glucose data at 1-5 minute intervals
5. IF the desk clock loses connectivity, THEN THE Platform SHALL queue updates for delivery when reconnected

### Requirement 6: AI-Powered Glucose Analysis

**User Story:** As a patient, I want AI analysis of my glucose patterns, so that I can understand trends and receive personalized insights.

#### Acceptance Criteria

1. THE Platform SHALL analyze glucose data to identify patterns such as dawn phenomenon, post-meal spikes, and overnight stability
2. WHEN a patient requests analysis, THE AI_Agent SHALL generate insights based on at least 7 days of data
3. THE Platform SHALL provide a chat interface for patients to ask questions about their glucose data
4. WHEN a patient asks a question, THE AI_Agent SHALL respond with answers grounded in their actual data
5. THE AI_Agent SHALL cite specific time periods and glucose values when providing insights
6. THE Platform SHALL not provide medical advice or treatment recommendations without appropriate disclaimers

### Requirement 7: Agentic AI Logging

**User Story:** As a patient, I want to log my entire day's activities in one prompt, so that I can quickly catch up on treatment logging without multiple manual entries.

#### Acceptance Criteria

1. THE Platform SHALL accept natural language input describing multiple treatments and activities
2. WHEN a patient submits a day summary, THE AI_Agent SHALL parse it into individual treatment entries
3. THE AI_Agent SHALL extract insulin doses, carbohydrate intake, exercise, and other relevant events
4. THE AI_Agent SHALL infer approximate timestamps based on context (e.g., "breakfast" → morning time)
5. WHEN parsing is complete, THE Platform SHALL present extracted entries for patient confirmation before saving
6. THE Platform SHALL allow patients to edit AI-extracted entries before final submission

### Requirement 8: Voice Assistant Integration

**User Story:** As a patient, I want to log treatments and check glucose levels using voice commands, so that I can interact hands-free while cooking or exercising.

#### Acceptance Criteria

1. THE Platform SHALL integrate with Amazon Alexa for voice command processing
2. THE Platform SHALL integrate with Google Home for voice command processing
3. WHEN a patient asks for current glucose level, THE Voice_Assistant SHALL respond with the most recent reading
4. WHEN a patient logs a treatment via voice, THE Platform SHALL parse the command and create the appropriate entry
5. THE Voice_Assistant SHALL confirm successful logging with spoken feedback
6. THE Platform SHALL authenticate voice commands using account linking with the patient's tenant

### Requirement 9: Fitness Integration

**User Story:** As a patient, I want to automatically import exercise data from fitness apps, so that I can correlate physical activity with glucose changes.

#### Acceptance Criteria

1. THE Platform SHALL integrate with Apple Health for importing workout data
2. THE Platform SHALL integrate with Google Fit for importing workout data
3. THE Platform SHALL integrate with Strava for importing cycling and running activities
4. WHEN new workout data is available, THE Platform SHALL import it within 15 minutes
5. THE Platform SHALL convert fitness app workouts into treatment log entries with type, duration, and intensity
6. THE Platform SHALL associate imported workouts with glucose readings from the same time period

### Requirement 10: Medical Records Storage

**User Story:** As a patient, I want to store medical documents and lab results, so that I have a complete health record in one place.

#### Acceptance Criteria

1. THE Platform SHALL allow patients to upload medical documents in PDF, JPEG, and PNG formats
2. THE Platform SHALL store uploaded documents securely within the patient's tenant
3. THE Platform SHALL support document categorization (lab results, prescriptions, doctor notes, insurance)
4. WHEN a patient searches for documents, THE Platform SHALL return results filtered by category and date
5. THE Platform SHALL allow patients to share specific documents with their doctor through the platform
6. THE Platform SHALL enforce a maximum file size limit of 10MB per document

### Requirement 11: Doctor Portal

**User Story:** As a doctor, I want to view multiple patients' glucose data in a single dashboard, so that I can efficiently monitor all my diabetic patients.

#### Acceptance Criteria

1. THE Platform SHALL provide a specialized doctor portal with multi-patient dashboard view
2. WHEN a patient grants access, THE Doctor SHALL see that patient's data in their dashboard
3. THE Doctor_Portal SHALL display summary cards for each patient showing current glucose, time in range, and recent trends
4. THE Doctor_Portal SHALL allow filtering patients by glucose control metrics (e.g., time in range percentage)
5. THE Doctor_Portal SHALL highlight patients with concerning patterns or frequent alerts
6. WHEN a doctor clicks on a patient card, THE Platform SHALL display detailed glucose graphs and treatment logs
7. THE Platform SHALL log all doctor access to patient data for audit purposes

### Requirement 12: Family Sharing

**User Story:** As a patient, I want to share my real-time glucose data with family members, so that they can help monitor my condition and respond to emergencies.

#### Acceptance Criteria

1. THE Platform SHALL allow patients to invite family members via email or phone number
2. WHEN a family member accepts an invitation, THE Platform SHALL grant them read-only access to the patient's data
3. THE Family_Member SHALL receive the same real-time updates and alerts as the patient
4. THE Platform SHALL allow patients to configure which family members receive which types of alerts
5. THE Platform SHALL allow patients to revoke family member access at any time
6. WHEN a patient's glucose enters a critical range, THE Platform SHALL notify all authorized family members simultaneously

### Requirement 13: Authentication and Authorization

**User Story:** As a platform operator, I want secure authentication and role-based access control, so that patient data remains private and compliant with healthcare regulations.

#### Acceptance Criteria

1. THE Platform SHALL use JWT-based authentication for all API requests
2. WHEN a user logs in, THE Platform SHALL issue a JWT token with tenant ID and role claims
3. THE Platform SHALL support three user roles: Patient, Family_Member, and Doctor
4. THE Platform SHALL enforce role-based permissions on all data access operations
5. THE Platform SHALL require password complexity (minimum 12 characters, mixed case, numbers, symbols)
6. THE Platform SHALL support two-factor authentication via SMS or authenticator apps
7. WHEN a user fails authentication 5 times, THE Platform SHALL temporarily lock the account for 15 minutes

### Requirement 14: Data Export and Portability

**User Story:** As a patient, I want to export my glucose data in standard formats, so that I can use it with other tools or share it with healthcare providers.

#### Acceptance Criteria

1. THE Platform SHALL support exporting glucose data in CSV format
2. THE Platform SHALL support exporting glucose data in JSON format compatible with OneTwenty
3. THE Platform SHALL support exporting glucose data in PDF format with graphs and statistics
4. WHEN a patient requests an export, THE Platform SHALL generate the file within 60 seconds
5. THE Platform SHALL include all glucose readings, treatments, and notes in the export
6. THE Platform SHALL allow patients to specify date ranges for exports

### Requirement 15: Public API with Custom Subdomains

**User Story:** As a developer or patient, I want to access my glucose data through a public API with custom subdomain and API secrets, so that I can build custom integrations and applications.

#### Acceptance Criteria

1. THE Platform SHALL provide a public API following the OneTwenty API protocol
2. WHEN a patient enables API access, THE Platform SHALL provision a custom subdomain (e.g., patientslug.platform.com)
3. THE Platform SHALL generate API secrets (tokens) for authenticating API requests
4. THE Platform SHALL allow patients to create multiple API secrets with different permission scopes
5. WHEN an API request is received, THE Platform SHALL authenticate using the provided API secret
6. THE Platform SHALL support API rate limiting to prevent abuse (e.g., 1000 requests per hour per token)
7. THE Platform SHALL provide API documentation with examples for common operations
8. THE Platform SHALL allow patients to revoke API secrets at any time

### Requirement 16: Data Backup and Recovery

**User Story:** As a platform operator, I want automated backups of all patient data, so that data can be recovered in case of system failures.

#### Acceptance Criteria

1. THE Platform SHALL perform automated backups of all databases every 6 hours
2. THE Platform SHALL retain backup snapshots for at least 30 days
3. WHEN a backup is created, THE Platform SHALL verify its integrity before marking it complete
4. THE Platform SHALL store backups in a geographically separate location from primary data
5. THE Platform SHALL support point-in-time recovery for any timestamp within the retention period
6. THE Platform SHALL document and test disaster recovery procedures quarterly
