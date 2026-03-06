CREATE TABLE users(
    id BIGSERIAL PRIMARY KEY,
    email TEXT NOT NULL,
    password TEXT NOT NULL,
    username TEXT NOT NULL,
    role TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE email_verifications (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    code VARCHAR(10) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_verification_timestamp ON email_verifications (created_at);
CREATE OR REPLACE FUNCTION clean_expired_verifications()
RETURNS TRIGGER AS $$
BEGIN
    DELETE FROM email_verifications 
    WHERE created_at < NOW() - INTERVAL '15 minutes';
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trigger_clean_verifications
AFTER INSERT ON email_verifications
FOR EACH STATEMENT 
EXECUTE FUNCTION clean_expired_verifications();

