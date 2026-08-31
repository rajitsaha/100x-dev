# 100xprism Token Dashboard

A lightweight web dashboard for tracking token usage across AI tools (Claude Code, Codex, Cursor, Pi) with incremental updates and snapshot capabilities.

## Features

- ✅ **Lightweight** - Runs on a single Node.js process
- ✅ **Persistent** - SQLite database stores all transcripts
- ✅ **Incremental** - Add transcripts as they're generated, no full scans needed
- ✅ **Snapshot** - Save/restore dashboard state anytime
- ✅ **REST API** - Endpoints for stats, transcripts, search, CRUD operations
- ✅ **Web UI** - Simple dashboard to browse and filter transcripts

## Tech Stack

- **Backend**: Node.js + Express
- **Database**: SQLite (better-sqlite3) or PostgreSQL
- **Frontend**: Vanilla HTML/JS (served via static files)

## Installation

```bash
# Clone and install
cd token-dashboard
npm install

# Initialize database
npm run init-db

# Start server
npm start
```

## Usage

### Start the server
```bash
npm start
```

### Add transcripts to database
```bash
node add-transcript.js
# Or programmatically:
# POST /api/transcripts { tool, session_id, title, tokens... }
```

### API Endpoints

| Method | Endpoint | Description |
|--------|---------|-------------|
| GET | `/api/stats` | Get aggregated stats for all tools |
| GET | `/api/transcripts/:tool` | Get transcripts for a specific tool (paginated) |
| GET | `/api/transcripts/search` | Search transcripts by query |
| POST | `/api/transcripts` | Add a new transcript |
| POST | `/api/transcripts/:hash/update` | Update an existing transcript |
| POST | `/api/snapshot` | Save current state to disk |
| POST | `/api/restore-snapshot` | Restore from a snapshot file |

## Project Structure

```
token-dashboard/
├── package.json
├── init.sql          # Database schema
├── db.js             # Database module (SQLite/PostgreSQL)
├── server.js         # Express server
└── public/
    ├── index.html    # Dashboard UI
    └── app.js        # Dashboard frontend logic
```

## Environment Variables

```bash
# SQLite is default, set these for PostgreSQL
PG_HOST=localhost
PG_PORT=5432
PG_DATABASE=100xprism
PG_USER=postgres
PG_PASSWORD=your_password

# Server port
PORT=8787
```

## How It Works

### Incremental Mode
1. **Transcript is generated** (e.g., from Hermes session)
2. **Call API**: `POST /api/transcripts` with transcript data
3. **Database saves** the transcript (hashed by content)
4. **API automatically updates stats**

### Snapshot Mode
1. **Periodically** (e.g., every hour): `POST /api/snapshot`
2. **DB dumps** current transcripts to file
3. **Restore anytime**: `POST /api/restore-snapshot` with snapshot

## Why This Is Better Than Current Approach

| Current (node 100xprism dashboard) | This Solution |
|----------------------------------|---------------|
| Scans ALL transcripts at startup | Adds transcripts incrementally |
| Blocks while scanning | Non-blocking, real-time |
| Loses data if crashes | SQLite persists across restarts |
| Hard to scale to 1000s of files | Efficient queries, pagination |
| No restore capability | Snapshot/restore feature |

## Next Steps: Integration with Hermes

Add this dashboard as a 100xprism skill that hooks into Hermes:

```bash
# After every session completes:
# 1. Parse transcripts from session
# 2. POST to /api/transcripts
# 3. Auto-updates dashboard
```

### Hook into Hermes's `session_reset`

Add a small daemon that runs:

```bash
# /Users/rajit.saha/work/100xprism/token-dashboard/daemon.js
const { watch } = require('chokidar');
const db = require('./db');
const http = require('http');

const server = http.createServer((req, res) => {
  // Listen for session completion hooks
});

// Watch Hermes session directory
const watcher = watch('/Users/rajit.saha/.hermes/sessions/', {
  persistent: true,
  awaitWriteFinish: { stabiliseThreshold: 500 }
});

watcher.on('add', (file) => {
  // If new .jsonl or .json session detected:
  // - Parse transcripts
  // - POST to /api/transcripts
  // - Update stats
});

server.listen(8787, () => {
  console.log('Token Dashboard ready, waiting for sessions...');
});
```

## Roadmap

- [ ] Add WebSocket for real-time updates
- [ ] Export to CSV/JSON
- [ ] Visual charts (token trends over time)
- [ ] Cost calculator (based on provider pricing)
- [ ] Auto-snapshot on every N minutes
