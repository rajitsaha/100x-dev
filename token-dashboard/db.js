// Database module for 100xprism Token Dashboard
// Supports both SQLite and PostgreSQL for flexibility

const Database = require('better-sqlite3');
const fs = require('fs');
const path = require('path');

class TokenDB {
  constructor(dbType, dbPath = '') {
    this.dbType = dbType || 'sqlite';
    
    if (this.dbType === 'sqlite') {
      this.db = new Database(dbPath || ':memory:');
      this.db.exec(`
        CREATE TABLE IF NOT EXISTS stats (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          tool TEXT,
          total_transcripts INTEGER DEFAULT 0,
          total_tokens INTEGER DEFAULT 0,
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
          FOREIGN KEY (snapshot_hash) REFERENCES snapshots(id)
        );
        
        CREATE TABLE IF NOT EXISTS snapshots (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
          data BLOB
        );
      `);
    } else if (this.dbType === 'postgres') {
      // PostgreSQL requires connection parameters
      this.pool = require('pg').Pool({
        host: process.env.PG_HOST || 'localhost',
        port: process.env.PG_PORT || 5432,
        database: process.env.PG_DATABASE || '100xprism',
        user: process.env.PG_USER || 'postgres',
        password: process.env.PG_PASSWORD
      });
    }
  }

  // Initialize database with schema
  init() {
    if (this.dbType === 'sqlite') {
      const schemaPath = path.join(__dirname, '../init.sql');
      if (fs.existsSync(schemaPath)) {
        this.db.exec(fs.readFileSync(schemaPath, 'utf8'));
      }
    }
    console.log(`Database initialized as ${this.dbType}`);
  }

  // Get dashboard stats
  async getStats() {
    const toolCounts = new Map([['claude', 0], ['codex', 0], ['cursor', 0], ['pi', 0]]);
    const totalTokens = new Map([['claude', 0], ['codex', 0], ['cursor', 0], ['pi', 0]]);
    
    if (this.dbType === 'sqlite') {
      const rows = this.db.prepare('SELECT tool, COUNT(*) as count, SUM(token_count) as tokens FROM transcripts GROUP BY tool').all();
      
      for (const row of rows) {
        if (toolCounts.has(row.tool)) {
          toolCounts.set(row.tool, row.count);
          totalTokens.set(row.tool, row.tokens);
        }
      }
    } else {
      const result = await this.pool.query(`
        SELECT tool, COUNT(*) as count, SUM(token_count) as tokens
        FROM transcripts
        GROUP BY tool
      `);
      for (const row of result.rows) {
        if (toolCounts.has(row.tool)) {
          toolCounts.set(row.tool, row.count);
          totalTokens.set(row.tool, row.tokens);
        }
      }
    }

    return {
      timestamp: new Date().toISOString(),
      toolCounts: Object.fromEntries(toolCounts),
      totalTokens: Object.fromEntries(totalTokens),
      totalSessions: toolCounts.reduce((sum, c) => sum + c, 0)
    };
  }

  // Get transcripts for a tool (paginated)
  async getTranscripts(tool, page = 1, limit = 50) {
    if (this.dbType === 'sqlite') {
      const offset = (page - 1) * limit;
      const rows = this.db.prepare(
        'SELECT * FROM transcripts WHERE tool = ? ORDER BY created_at DESC LIMIT ? OFFSET ?'
      ).all(tool, limit, offset);
      return rows;
    } else {
      const result = await this.pool.query(
        'SELECT * FROM transcripts WHERE tool = ? ORDER BY created_at DESC LIMIT ? OFFSET ?',
        [tool, limit, (page - 1) * limit]
      );
      return result.rows;
    }
  }

  // Search transcripts
  async searchTranscripts(query = '', limit = 50) {
    if (this.dbType === 'sqlite') {
      return this.db.prepare(
        'SELECT * FROM transcripts WHERE content LIKE ? OR session_id LIKE ? ORDER BY created_at DESC LIMIT ?'
      ).all(`%${query}%`, `%${query}%`, limit);
    } else {
      const result = await this.pool.query(
        'SELECT * FROM transcripts WHERE content ILIKE ? OR session_id ILIKE ? LIMIT ?',
        [`%${query}%`, `%${query}%`, limit]
      );
      return result.rows;
    }
  }

  // Insert transcript
  async insertTranscript(transcript) {
    if (this.dbType === 'sqlite') {
      const snapshotHash = transcript.snapshot_hash || cryptoHash(transcript.content);
      this.db.prepare(`
        INSERT OR IGNORE INTO transcripts (hash, created_at, tool, session_id, title, token_count, user_tokens, model_tokens, tool_tokens, content, snapshot_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      `).run(
        transcript.hash, 
        new Date().toISOString(),
        transcript.tool, transcript.session_id, transcript.title,
        transcript.token_count, transcript.user_tokens, transcript.model_tokens, 
        transcript.tool_tokens, transcript.content, snapshotHash
      );
    } else {
      await this.pool.query(`
        INSERT INTO transcripts (hash, created_at, tool, session_id, title, token_count, user_tokens, model_tokens, tool_tokens, content, snapshot_hash)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
      `, [
        transcript.hash, 
        new Date().toISOString(),
        transcript.tool, transcript.session_id, transcript.title,
        transcript.token_count, transcript.user_tokens, transcript.model_tokens, 
        transcript.tool_tokens, transcript.content || '[]', transcript.snapshot_hash
      ]);
    }
  }

  // Update transcript
  async updateTranscript(hash, updates) {
    const { new_count, new_title, ...rest } = updates;
    
    const updatesSql = [];
    const updatesParams = [];
    
    if (new_count !== undefined) {
      updatesSql.push('token_count = ?');
      updatesParams.push(new_count);
    }
    
    if (new_title !== undefined) {
      updatesSql.push('title = ?');
      updatesParams.push(new_title);
    }
    
    if (updatesSql.length > 0) {
      const snapshotHash = cryptoHash(updates);
      
      if (this.dbType === 'sqlite') {
        this.db.prepare(`
          UPDATE transcripts 
          SET token_count = ?, title = ?, snapshot_hash = ? 
          WHERE hash = ?
        `).run(
          updatesParams[0], updatesParams[1], snapshotHash, hash
        );
      } else {
        await this.pool.query(
          'UPDATE transcripts SET token_count = ?, title = ?, snapshot_hash = ? WHERE hash = ?',
          [updatesParams[0], updatesParams[1], snapshotHash, hash]
        );
      }
    }
  }

  // Snapshot: save current state to disk
  async snapshot(filename = 'snapshot') {
    if (this.dbType === 'sqlite') {
      const stats = await this.getStats();
      const db = this.db;
      
      // Extract all transcripts
      const transcripts = db.prepare('SELECT hash, tool, session_id, title, token_count FROM transcripts').all();
      
      return {
        timestamp: new Date().toISOString(),
        tools: Object.fromEntries(stats.toolCounts),
        total: stats.totalSessions,
        stats: {
          claude: { count: stats.toolCounts.claude, tokens: stats.totalTokens.claude || 0 },
          codex: { count: stats.toolCounts.codex, tokens: stats.totalTokens.codex || 0 },
          cursor: { count: stats.toolCounts.cursor, tokens: stats.totalTokens.cursor || 0 },
          pi: { count: stats.toolCounts.pi, tokens: stats.totalTokens.pi || 0 }
        },
        exports: {
          transcripts: transcripts,
          schema: 'sqlite'
        }
      };
    }
    return null;
  }

  // Restore from snapshot
  async restoreSnapshot(snapshot) {
    if (this.dbType === 'sqlite' && snapshot.exports && snapshot.exports.transcripts) {
      // Clear and repopulate
      this.db.exec('DELETE FROM transcripts');
      this.db.exec('DELETE FROM stats');
      
      for (const t of snapshot.exports.transcripts) {
        this.db.prepare(`
          INSERT INTO transcripts (hash, created_at, tool, session_id, title, token_count, user_tokens, model_tokens, tool_tokens, content)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        `).run(
          t.hash, new Date(t.timestamp).toISOString(),
          t.tool, t.session_id, t.title,
          t.token_count, t.user_tokens, t.model_tokens, t.tool_tokens, JSON.stringify(t.content)
        );
      }
    }
  }
}

// Simple hash function for snapshots
function cryptoHash(content) {
  let hash = 0;
  for (let i = 0; i < content.length; i++) {
    const char = content.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash;
  }
  return Math.abs(hash).toString(36);
}

module.exports = TokenDB;
