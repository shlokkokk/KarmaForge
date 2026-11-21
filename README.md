# KarmaForge

KarmaForge is an autonomous organic Reddit engagement engine engineered to build authentic comment karma across aged Reddit accounts without triggering spam heuristics, bot detectors, or community downvotes.

---

## Architecture Overview

```
                                +-------------------+
                                |   Rising Feeds    |
                                |  (35+ Subreddits) |
                                +---------+---------+
                                          |
                                          v
+------------------+           +-------------------+
| Multi-Account DB | <-------> |    Wave Hunter    |
| (WAL SQLite)     |           | (Velocity Scoring)|
+------------------+           +---------+---------+
                                          |
                                          v
+------------------+           +-------------------+
| Downvote Shield  |           |   Persona Engine  |
| (-2 Auto-Nuke)   |           | (Calibrated Model)|
+--------+---------+           +---------+---------+
         |                                |
         |                                v
         |                     +-------------------+
         |                     |    AI Gateway     |
         |                     | (Gemini -> Groq)  |
         |                     +---------+---------+
         |                                |
         +----------------+---------------+
                          |
                          v
               +----------------------+
               | Discord Control Room |
               | (17 Categorized Chs) |
               +----------------------+
```

### Core Features
- **Wave-Riding Hunter**: Continuously scans rising and top-hour feeds across 35+ high-volume subreddits for high-velocity early posts (<25 comments, 15-55m old).
- **Multi-Account Concurrency**: Rotates across aged Reddit accounts with daily limits (max 6/day) and anti-collision checks via WAL-mode SQLite (`karmaforge.db`).
- **AI Gateway & Cascade**: Keypool rotation with automatic rate-limit cooldowns across Gemini Flash models, backed up by instant Groq LPU failover.
- **Empirical Persona Calibration**: Prompts derived from deep linguistic analysis of 350+ top Reddit comments. Enforces natural lowercase starts, zero emojis, trailing period drops, and dry observational humor.
- **Downvote Shield**: Inspects comments posted in the last 36 hours. Issues warnings at -1 score and auto-deletes at -2 score to freeze karma bleed.
- **Discord Mission Control**: 17 dedicated channels organized across 5 categories with real-time alerts, slash commands, and persistent interactive buttons (`[Delete Comment Now]`, Control Panel).
- **Circadian Rest**: Automatically sleeps during local night hours (00:30 - 08:30) to mirror realistic human sleep schedules.

---

## Quickstart

### 1. Installation
Clone the repository and install requirements:
```bash
git clone https://github.com/shlokkokk/KarmaForge.git
cd KarmaForge
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configuration
Copy the template and configure your credentials:
```bash
cp .env.example .env
```

Edit `.env` with your API keys, Reddit session cookies, and Discord bot credentials.

### 3. Verify Accounts & Status
```bash
python main.py --status
```

### 4. Run Autonomous Engine + Discord Bot
```bash
python main.py --run
```

---

## Cloud Deployment

### Docker Compose (Recommended)
KarmaForge includes a lightweight Docker container with built-in `curl` TLS fingerprint handling.
```bash
docker compose up -d --build
```
The database persists on the host under `./data/karmaforge.db`.

---

## Security
- Credentials and session cookies are strictly managed through `.env`.
- Real session tokens and database files are gitignored by default.
