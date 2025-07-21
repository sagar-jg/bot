-- Database initialization script for WhatsApp Bot
-- This script will be run when PostgreSQL container starts

-- Create database if not exists
SELECT 'CREATE DATABASE bot_db'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'bot_db')\gexec

-- Connect to the bot_db database
\c bot_db;

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create enum types
DO $$ BEGIN
    CREATE TYPE message_sender AS ENUM ('user', 'assistant');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE feedback_type_enum AS ENUM ('thumbs_up', 'thumbs_down', 'rating', 'text');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create conversation_history table
CREATE TABLE IF NOT EXISTS conversation_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    message_id VARCHAR(255) UNIQUE NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    sender message_sender NOT NULL,
    message_text TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    search_results JSONB DEFAULT NULL,
    tools_used TEXT[] DEFAULT '{}',
    response_time_ms INTEGER DEFAULT NULL,
    search_confidence FLOAT DEFAULT NULL,
    search_results_count INTEGER DEFAULT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create feedback table
CREATE TABLE IF NOT EXISTS feedback (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    message_id VARCHAR(255) NOT NULL REFERENCES conversation_history(message_id) ON DELETE CASCADE,
    user_id VARCHAR(255) NOT NULL,
    feedback_type feedback_type_enum NOT NULL,
    human_feedback BOOLEAN DEFAULT NULL,
    human_feedback_score INTEGER CHECK (human_feedback_score >= 1 AND human_feedback_score <= 5),
    human_feedback_text TEXT DEFAULT NULL,
    question_text TEXT DEFAULT NULL,
    answer_text TEXT DEFAULT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_conversation_user_id ON conversation_history(user_id);
CREATE INDEX IF NOT EXISTS idx_conversation_timestamp ON conversation_history(timestamp);
CREATE INDEX IF NOT EXISTS idx_conversation_message_id ON conversation_history(message_id);
CREATE INDEX IF NOT EXISTS idx_conversation_sender ON conversation_history(sender);
CREATE INDEX IF NOT EXISTS idx_feedback_message_id ON feedback(message_id);
CREATE INDEX IF NOT EXISTS idx_feedback_user_id ON feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_feedback_created_at ON feedback(created_at);
CREATE INDEX IF NOT EXISTS idx_feedback_type ON feedback(feedback_type);

-- Create GIN index for metadata JSONB column for better JSON queries
CREATE INDEX IF NOT EXISTS idx_conversation_metadata_gin ON conversation_history USING GIN (metadata);
CREATE INDEX IF NOT EXISTS idx_conversation_search_results_gin ON conversation_history USING GIN (search_results);

-- Create text search index for message content
CREATE INDEX IF NOT EXISTS idx_conversation_message_text_gin ON conversation_history USING GIN (to_tsvector('english', message_text));

-- Create composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_conversation_user_timestamp ON conversation_history(user_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_message_created ON feedback(message_id, created_at DESC);

-- Create trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers
DROP TRIGGER IF EXISTS update_conversation_history_updated_at ON conversation_history;
CREATE TRIGGER update_conversation_history_updated_at
    BEFORE UPDATE ON conversation_history
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_feedback_updated_at ON feedback;
CREATE TRIGGER update_feedback_updated_at
    BEFORE UPDATE ON feedback
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Insert some sample data for testing (optional)
-- INSERT INTO conversation_history (message_id, user_id, sender, message_text, metadata)
-- VALUES 
--     ('test_msg_1', 'test_user_1', 'user', 'Hello, this is a test message', '{"test": true}'),
--     ('test_msg_2', 'test_user_1', 'assistant', 'Hello! How can I help you today?', '{"response_time": 150}');

-- Create a view for analytics
CREATE OR REPLACE VIEW conversation_analytics AS
SELECT 
    DATE(timestamp) as date,
    user_id,
    COUNT(*) as message_count,
    COUNT(CASE WHEN sender = 'user' THEN 1 END) as user_messages,
    COUNT(CASE WHEN sender = 'assistant' THEN 1 END) as assistant_messages,
    AVG(CASE WHEN sender = 'assistant' AND response_time_ms IS NOT NULL THEN response_time_ms END) as avg_response_time,
    AVG(CASE WHEN sender = 'assistant' AND search_confidence IS NOT NULL THEN search_confidence END) as avg_search_confidence
FROM conversation_history
GROUP BY DATE(timestamp), user_id
ORDER BY date DESC, user_id;

-- Create a view for feedback analytics
CREATE OR REPLACE VIEW feedback_analytics AS
SELECT 
    DATE(created_at) as date,
    feedback_type,
    COUNT(*) as count,
    AVG(CASE WHEN human_feedback_score IS NOT NULL THEN human_feedback_score END) as avg_rating,
    COUNT(CASE WHEN human_feedback = true THEN 1 END) as positive_feedback,
    COUNT(CASE WHEN human_feedback = false THEN 1 END) as negative_feedback
FROM feedback
GROUP BY DATE(created_at), feedback_type
ORDER BY date DESC, feedback_type;

-- Grant permissions (adjust as needed for your setup)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_app_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO your_app_user;

PRINT 'Database initialization completed successfully!';
