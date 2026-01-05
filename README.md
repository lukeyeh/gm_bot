# GM Bot 🌅

A Discord bot that tracks daily "GM" (Good Morning) streaks and maintains a monthly leaderboard.

## Features

- **Streak Tracking**: Automatically tracks consecutive days users say "GM"
- **Morning Validation**: Only accepts GM messages during morning hours (5 AM - 12 PM by default, configurable)
- **Customizable Allowlist**: Configure which phrases count as GM
- **Leaderboard**: Monthly leaderboard showing top GM warriors
- **Automatic Posts**: Posts leaderboard every Monday at 9 AM
- **Monthly Reset**: Streaks reset at the start of each month
- **Milestones**: Celebrates user achievements at special milestones (7 days, 10 days, 25 days, etc.)
- **Personal Stats**: Users can check their current and best streaks
- **Persistent Data**: All data saved to JSON file

## How It Works

1. Users say "GM" (or other allowed phrases) in the designated Discord channel **during morning hours**
2. Bot validates the time and tracks consecutive days
3. If a user says GM outside morning hours, they get a thumbs down reaction and error message
4. If a user misses a day, their streak resets
5. Leaderboard is automatically posted every Monday morning
6. All streaks reset monthly

## Setup

### Prerequisites

- Python 3.8 or higher
- A Discord bot token

### 1. Create a Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name
3. Go to the "Bot" section and click "Add Bot"
4. Under "Privileged Gateway Intents", enable:
   - MESSAGE CONTENT INTENT
   - SERVER MEMBERS INTENT
5. Click "Reset Token" and copy your bot token
6. Go to OAuth2 > URL Generator:
   - Select scopes: `bot` and `applications.commands`
   - Select permissions: `Send Messages`, `Read Messages/View Channels`, `Add Reactions`, `Embed Links`
   - Copy the generated URL and use it to invite the bot to your server

### 2. Install Dependencies

```bash
# Clone or download this repository
cd gm_bot

# Install required packages
pip install -r requirements.txt
```

### 3. Configure the Bot

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your configuration:
   ```
   DISCORD_TOKEN=your_bot_token_here
   GM_CHANNEL_ID=your_channel_id_here
   TIMEZONE=America/New_York
   MORNING_START_HOUR=5
   MORNING_END_HOUR=12
   ```

   **Configuration Options:**
   - `DISCORD_TOKEN`: Your Discord bot token (required)
   - `GM_CHANNEL_ID`: Channel ID where bot should operate (optional - leave empty for all channels)
   - `TIMEZONE`: Timezone for scheduling (e.g., `America/New_York`, `Europe/London`, `UTC`)
   - `MORNING_START_HOUR`: Start of morning hours in 24-hour format (default: 5 = 5 AM)
   - `MORNING_END_HOUR`: End of morning hours in 24-hour format (default: 12 = 12 PM/noon)
   - `DATA_DIR`: Directory for data storage (default: `.` for local, `/data` for Railway)

   **Finding Channel ID:**
   1. Enable Developer Mode in Discord (User Settings > Advanced > Developer Mode)
   2. Right-click on the channel and select "Copy ID"

### 4. Run the Bot

```bash
python bot.py
```

The bot should now be online and ready to track GM streaks!

## Commands

The bot uses Discord slash commands (type `/` to see all available commands):

- `/leaderboard` - Display the current leaderboard (optional: specify limit 1-25)
- `/streak` - Check your current streak and stats
- `/gmlist` - Show which phrases are accepted as GM
- `/gmadd <phrase>` - Add a phrase to the allowlist (admin only)
- `/gmremove <phrase>` - Remove a phrase from the allowlist (admin only)
- `/gmhelp` - Show help information

## Usage Examples

**Starting a streak:**
```
User: GM
Bot: 🌅 [reacts with sunrise emoji]
Bot: Good morning @User! Your streak has started! ☀️
```

**Continuing a streak:**
```
User: GM
Bot: 🌅 [reacts with sunrise emoji]
```

**New personal record:**
```
User: GM
Bot: 🌅 [reacts with sunrise emoji]
Bot: 🔥 New personal record! @User is on a 15 day streak! Keep it up! 🚀
```

**Viewing leaderboard:**
```
User: /leaderboard
Bot: [Displays formatted leaderboard with top 10 users]
```

**Saying GM outside morning hours:**
```
User: GM (at 3:00 PM)
Bot: 👎 [reacts with thumbs down]
Bot: ❌ @User, it's 03:00 PM - you can only say GM between 5:00 and 12:00! Try again in the morning! 🌙
```

## Scheduled Tasks

- **Monday Morning Post**: Leaderboard posted every Monday at 9:00 AM (configurable timezone)
- **Monthly Reset**: Streaks reset on the 1st of each month at midnight

## Data Storage

All data is stored in `gm_data.json` in the following format:

```json
{
  "users": {
    "user_id": {
      "username": "DisplayName",
      "current_streak": 5,
      "last_gm_date": "2026-01-05",
      "best_streak": 10
    }
  },
  "monthly_reset_date": "2026-01-01",
  "last_leaderboard_post": "2026-01-05T09:00:00"
}
```

## Customization

### Change Leaderboard Post Time

Edit `bot.py` line where the scheduler is configured:

```python
scheduler.add_job(
    post_weekly_leaderboard,
    CronTrigger(day_of_week='mon', hour=9, minute=0, timezone=tz),
    id='weekly_leaderboard'
)
```

Change `day_of_week`, `hour`, or `minute` as needed.

### Change Milestone Messages

Edit the milestone conditions in the `on_message` event handler in `bot.py`:

```python
elif streak % 7 == 0:  # Weekly milestone
    # Your custom message here
```

## Troubleshooting

**Bot commands don't appear:**
- Make sure you invited the bot with the `applications.commands` scope
- Wait a few minutes for commands to sync with Discord after the bot starts
- If the bot was already in your server before adding slash commands, you may need to re-invite it with the updated URL that includes `applications.commands`

**Bot doesn't respond to messages:**
- Make sure MESSAGE CONTENT INTENT is enabled in Discord Developer Portal
- Verify the bot has permission to read and send messages in the channel
- Check that the channel ID in `.env` is correct (if specified)

**Scheduled tasks not running:**
- Verify your timezone is set correctly in `.env`
- Check the bot logs for any errors
- Ensure the bot stays running (consider using a process manager)

**Data not persisting:**
- Check that the bot has write permissions in its directory
- Verify `gm_data.json` is being created and updated

## Deploy to Railway

Railway is the easiest way to deploy this bot to the cloud. The repository is already configured for Railway deployment.

### Quick Deploy

1. **Fork or clone this repository** to your GitHub account

2. **Go to [Railway](https://railway.app/)** and sign in with GitHub

3. **Click "New Project"** → "Deploy from GitHub repo"

4. **Select this repository** from the list

5. **Set up persistent storage (IMPORTANT)**:
   - In your Railway service, click on the "Settings" tab
   - Scroll to "Volumes" section
   - Click "Add Volume"
   - Set **Mount Path** to `/data`
   - Click "Add"
   - This ensures your streak data persists across deployments!

6. **Add environment variables** in Railway dashboard:
   - Click on your service
   - Go to "Variables" tab
   - Add the following variables:
     - `DISCORD_TOKEN`: Your Discord bot token
     - `GM_CHANNEL_ID`: Your channel ID (optional)
     - `TIMEZONE`: Your timezone (e.g., `America/New_York`)
     - `DATA_DIR`: `/data` (tells the bot to use the persistent volume)
     - `MORNING_START_HOUR`: `5` (optional, default is 5)
     - `MORNING_END_HOUR`: `12` (optional, default is 12)

7. **Deploy!** Railway will automatically:
   - Install dependencies from `requirements.txt`
   - Use the configuration from `railway.toml`
   - Mount the persistent volume
   - Keep the bot running 24/7
   - Preserve your data across deployments

### Railway Features

- **Automatic Deployments**: Pushes to your GitHub repo automatically deploy
- **Built-in Logs**: View bot logs in real-time
- **Persistent Storage**: Data persists across deployments
- **Always On**: Bot runs continuously without downtime
- **Free Tier**: $5 free credit per month (enough for this bot)

### Monitoring Your Bot on Railway

- View logs: Click on your service → "Deployments" → Select active deployment
- Check metrics: Monitor CPU and memory usage in the dashboard
- Restart bot: Click "Restart" in the service settings if needed

### Important Notes for Railway

- **CRITICAL**: You MUST set up a volume at `/data` for data persistence (see step 5 above)
- Without a volume, your streak data will be lost on each deployment
- The `gm_data.json` file is stored in the mounted volume and persists between deployments
- Make sure to set `DATA_DIR=/data` in your environment variables
- Logs are available in the Railway dashboard
- The bot automatically restarts if it crashes (configured in `railway.toml`)

## Running in Production (Self-Hosted)

For self-hosted production deployment, consider:

1. **Process Manager**: Use `systemd`, `pm2`, or `supervisor` to keep the bot running
2. **Log Management**: Redirect output to log files
3. **Backup**: Regularly backup `gm_data.json`
4. **Monitoring**: Set up alerts for bot downtime

### Example systemd Service

Create `/etc/systemd/system/gm-bot.service`:

```ini
[Unit]
Description=GM Bot Discord Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/gm_bot
ExecStart=/usr/bin/python3 /path/to/gm_bot/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable gm-bot
sudo systemctl start gm-bot
sudo systemctl status gm-bot
```

## Contributing

Feel free to submit issues, fork the repository, and create pull requests for any improvements.

## License

MIT License - feel free to use and modify as needed.

## Support

For issues or questions, please open an issue on the repository.

---

Made with ☕ for the GM community
