// Token Dashboard Web Server
// A Node.js web app for tracking 100xprism token usage with SQLite backend

const express = require('express');
const { Pool } = require('pg');  // or use better-sqlite3 for local
const path = require('path');
const fs = require('fs');
const crypto = require('crypto');

const app = express();

// Database connection (use SQLite for simplicity, or pg for Postgres)
const db = require('./db');

// Middleware
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// API Routes

// Dashboard stats
app.get('/api/stats', async (req, res) => {
  try {
    const stats = await db.getStats();
    res.json(stats);
  } catch (err) {
    console.error('Error getting stats:', err);
    res.status(500).json({ error: err.message });
  }
});

// Get transcript by hash
app.get('/api/transcripts/:hash', async (req, res) => {
  try {
    const { hash } = req.params;
    const transcript = await db.getTranscript(hash);
    res.json(transcript);
  } catch (err) {
    res.status(404).json({ error: err.message });
  }
});

// Parse transcript (on-demand)
app.post('/api/transcripts', async (req, res) => {
  try {
    const { tool, session_id, content } = req.body;
    const hash = crypto.createHash('md5').update(`${tool}-${session_id}-${content}`).digest('hex').substr(0, 16);
    
    const transcript = {
      hash,
      tool,
      session_id,
      title: content.match(/\[\[(.*?)\]\[\/\]\([^\)]+\)\]\[\/\]\(/)?.[1] || 'Unknown Session',
      tool_name: tool,
      content: content,
      token_count: 0,  // Will be calculated by the backend
      user_tokens: 0,
      model_tokens: 0,
      tool_tokens: 0,
      parsed_at: new Date().toISOString()
    };
    
    await db.insertTranscript(transcript);
    res.json(transcript);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Search transcripts
app.get('/api/transcripts/search', async (req, res) => {
  try {
    const { tool, query, limit = 50 } = req.query;
    const results = await db.searchTranscripts({ tool, query, limit });
    res.json(results);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Snapshot current state
app.post('/api/snapshot', async (req, res) => {
  try {
    const snapshot = await db.snapshot();
    await db.saveSnapshot(snapshot);
    res.json({ success: true, snapshot });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Restore from snapshot
app.post('/api/restore-snapshot', async (req, res) => {
  try {
    const { snapshot } = req.body;
    await db.restoreSnapshot(snapshot);
    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// List sessions by tool
app.get('/api/transcripts/:tool', async (req, res) => {
  try {
    const { tool } = req.params;
    const transcripts = await db.getTranscriptsByTool(tool);
    res.json(transcripts);
  } catch (err) {
    res.status(404).json({ error: err.message });
  }
});

const PORT = process.env.PORT || 8787;
app.listen(PORT, () => {
  console.log(`Token Dashboard running on http://0.0.0.0:${PORT}`);
});
