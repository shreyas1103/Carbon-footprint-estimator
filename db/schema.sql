-- EcoTrack Database Schema
-- Run this against your Supabase PostgreSQL instance

-- Drop tables if they exist (for clean re-runs)
DROP TABLE IF EXISTS insights_history CASCADE;
DROP TABLE IF EXISTS merchant_cache CASCADE;
DROP TABLE IF EXISTS transactions CASCADE;

-- 1. transactions table
-- Purpose: Stores individual financial transactions uploaded by the user.
-- It tracks transaction details along with categorized emission data for carbon footprint analysis.
CREATE TABLE transactions (
    id SERIAL PRIMARY KEY,
    upload_batch_id UUID NOT NULL,
    transaction_date DATE NOT NULL,
    raw_description TEXT NOT NULL,
    cleaned_description TEXT,
    amount NUMERIC(12, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'INR',
    category VARCHAR(50),
    categorization_tier SMALLINT,
    emission_factor_used NUMERIC(10, 4),
    estimated_emissions_kgco2e NUMERIC(12, 4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. merchant_cache table
-- Purpose: Caches categorization and emission factor mapping for merchants to speed up processing of future uploads.
-- This reduces external API calls and improves performance for recurring merchants.
CREATE TABLE merchant_cache (
    id SERIAL PRIMARY KEY,
    merchant_key TEXT UNIQUE NOT NULL,
    category VARCHAR(50) NOT NULL,
    resolved_tier SMALLINT NOT NULL,
    confidence_score NUMERIC(5, 4),
    hit_count INTEGER DEFAULT 1,
    last_used_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. insights_history table
-- Purpose: Records generated insights based on a batch of transactions over a specific period.
-- This allows tracking historical analysis and the model/prompt used to generate the insights.
CREATE TABLE insights_history (
    id SERIAL PRIMARY KEY,
    upload_batch_id UUID NOT NULL,
    period_start DATE,
    period_end DATE,
    insight_text TEXT NOT NULL,
    prompt_summary TEXT,
    model_used VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
-- Rationale:
-- idx_transactions_batch: Speeds up querying all transactions from a specific upload batch.
-- idx_transactions_date: Optimizes time-series queries and filtering by date ranges.
-- idx_transactions_category: Improves performance when aggregating emissions by category.
-- idx_insights_batch: Fast retrieval of insights associated with a specific upload batch.
CREATE INDEX idx_transactions_batch ON transactions(upload_batch_id);
CREATE INDEX idx_transactions_date ON transactions(transaction_date);
CREATE INDEX idx_transactions_category ON transactions(category);
CREATE INDEX idx_insights_batch ON insights_history(upload_batch_id);

-- Validation constraints
-- Rationale: Ensures critical data integrity for amount and date before calculating emissions.
ALTER TABLE transactions ADD CONSTRAINT chk_amount_not_null CHECK (amount IS NOT NULL);
ALTER TABLE transactions ADD CONSTRAINT chk_date_not_null CHECK (transaction_date IS NOT NULL);
