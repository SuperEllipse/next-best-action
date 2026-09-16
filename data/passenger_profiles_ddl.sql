-- Snowflake schema for the IROP demo passenger profiles.
-- Matches live table: CUSTOMER_DB.PROFILES.PASSENGER_PROFILES
-- Column order matches data/passenger_profiles.csv exactly.

CREATE DATABASE IF NOT EXISTS CUSTOMER_DB;
CREATE SCHEMA IF NOT EXISTS CUSTOMER_DB.PROFILES;

CREATE OR REPLACE TABLE CUSTOMER_DB.PROFILES.PASSENGER_PROFILES (
    customer_id                VARCHAR,
    full_name                  VARCHAR,
    loyalty_tier               VARCHAR,
    lifetime_spend_usd         FLOAT,
    lifetime_flights           NUMBER(38, 0),
    preferred_seat             VARCHAR,
    preferred_lounge             VARCHAR,
    past_disruptions_count     NUMBER(38, 0),
    last_disruption_outcome    VARCHAR,
    base_retention_propensity  FLOAT
);

-- Example load (adjust stage/path for your account):
--
-- CREATE OR REPLACE FILE FORMAT CUSTOMER_DB.PROFILES.csv_format
--   TYPE = CSV
--   SKIP_HEADER = 1
--   FIELD_OPTIONALLY_ENCLOSED_BY = '"';
--
-- PUT file://passenger_profiles.csv @CUSTOMER_DB.PROFILES.%passenger_stage;
--
-- COPY INTO CUSTOMER_DB.PROFILES.PASSENGER_PROFILES (
--     customer_id,
--     full_name,
--     loyalty_tier,
--     lifetime_spend_usd,
--     lifetime_flights,
--     preferred_seat,
--     preferred_lounge,
--     past_disruptions_count,
--     last_disruption_outcome,
--     base_retention_propensity
-- )
-- FROM @CUSTOMER_DB.PROFILES.%passenger_stage/passenger_profiles.csv
-- FILE_FORMAT = CUSTOMER_DB.PROFILES.csv_format;
