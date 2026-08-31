// 100xprism Token Dashboard - Web Server with SQLite

require('dotenv').config();
const express = require('express');
const { createClient } = require('postgres');  // or better-sqlite3 if preferred
const cors = require('cors');

const app = express();
app.use(cors());
app.use(express.json());
app.use(express.static('public'));

// Database
const pool = require('./db');

// --- Stats Endpoint ---
app.get('/api/stats', async (req, res) => {
  try {
    const result = await pool.query('SELECT * FROM stats');
    res.json(result.rows);
  } catch (e) { res.status(500).json({ error: e.message }); }
});

// --- Get Transcripts for Tool ---
app.get('/api/transcripts/:tool', async (req, res) => {
  try {
    const tool = req.params.tool;
    const page = parseInt(req.query.page) || 1;
    const limit = parseInt(req.query.limit) || 50;
    
    const result = await pool.query(`
      SELECT * FROM transcripts 
      WHERE tool = $1 
      ORDER BY created_at DESC 
      LIMIT $2 OFFSET $3
    `, [tool, limit, (page - 1) * limit]);
    
    res.json(result.rows);
  } catch (e) { res.status(404).json({ error: e.message }); }
});

// --- Search Transcripts ---
app.post('/api/transcripts/search', async (req, res) => {
  try {
    const { tool, query } = req.body;
    const result = await pool.query(`
      SELECT * FROM transcripts 
      WHERE (tool = $1 OR tool IS NULL) 
      AND (session_id ILIKE $2 OR content ILIKE $2)
      LIMIT $3
    `, [tool, `%${query}%`, 50]);
    res.json(result.rows);
  } catch (e) { res.status(500).json({ error: e.message }); }
});

// --- Save Snapshot ---
app.post('/api/snapshot', async (req, res) => {
  try {
    const snapshot = await pool.query('SELECT * FROM transcripts').then(r => ({
      timestamp: new Date().toISOString(),
      tools: {
        claude: r.rows.filter(t => t.tool === 'claude').length,
        codex: r.rows.filter(t => t.tool === 'codex').length,
        cursor: r.rows.filter(t => t.tool === 'cursor').length,
        pi: r.rows.filter(t => t.tool === 'pi').length
      },
      total_rows: r.rows.length
    }));
    // Save to disk...
    res.json({ success: true, snapshot });
  } catch (e) { res.status(500).json({ error: e.message }); }
});

// --- Increment: Add Transcript ---
app.post('/api/transcripts', async (req, res) => {
  try {
    const { tool, session_id, title, token_count, user_tokens, model_tokens, tool_tokens, content } = req.body;
    await pool.query(`
      INSERT INTO transcripts (tool, session_id, title, token_count, user_tokens, model_tokens, tool_tokens, content)
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
    `, [tool, session_id, title, token_count, user_tokens, model_tokens, tool_tokens, JSON.stringify(content)]);
    res.json({ id: 1, success: true });
  } catch (e) { res.status(500).json({ error: e.message }); }
});

// --- Update Token Count for Hash ---
app.post('/api/transcripts/:hash/update', async (req, res) => {
  try {
    const { hash, new_count } = req.body;
    await pool.query('UPDATE transcripts SET token_count = $1 WHERE hash = $2', [new_count, hash]);
    res.json({ success: true });
  } catch (e) { res.status(404).json({ error: 'Not found' }); }
});

const PORT = process.env.PORT || 8787;
app.listen(PORT, () => console.log(`Token Dashboard running on http://0.0.0.0:${PORT}`));
