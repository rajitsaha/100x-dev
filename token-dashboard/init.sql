-- 100xprism Token Dashboard Database Schema

CREATE TABLE IF NOT EXISTS stats (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  tool TEXT,
  total_transcripts INTEGER DEFAULT 0,
  total_tokens INTEGER DEFAULT 0,
  user_tokens INTEGER DEFAULT 0,
  model_tokens INTEGER DEFAULT 0,
  tool_tokens INTEGER DEFAULT 0,
  last_snapshot TEXT
);

CREATE TABLE IF NOT EXISTS transcripts (
  hash TEXT PRIMARY KEY,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  tool TEXT,
  session_id TEXT,
  title TEXT,
  token_count INTEGER DEFAULT 0,
  user_tokens INTEGER DEFAULT 0,
  model_tokens INTEGER DEFAULT 0,
  tool_tokens INTEGER DEFAULT 0,
  content TEXT,
  snapshot_hash TEXT,
  INDEX idx_tool_created (tool, created_at)
);

CREATE INDEX IF NOT EXISTS idx_hash ON transcripts (hash);
CREATE INDEX IF NOT EXISTS idx_session ON transcripts (session_id);

-- Views for quick aggregation
CREATE VIEW IF NOT EXISTS tool_stats AS
SELECT 
  tool,
  COUNT(*) as session_count,
  SUM(token_count) as total_tokens,
  SUM(user_tokens) as user_tokens,
  SUM(model_tokens) as model_tokens,
  SUM(tool_tokens) as tool_tokens
FROM transcripts
GROUP BY tool;
