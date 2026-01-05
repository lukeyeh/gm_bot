"""
GM Bot - Track daily GM streaks on Discord
"""
import os
import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, time
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from data_manager import DataManager


# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GM_CHANNEL_ID = os.getenv('GM_CHANNEL_ID')
TIMEZONE = os.getenv('TIMEZONE', 'UTC')
DATA_DIR = os.getenv('DATA_DIR', '.')  # Data directory for persistent storage

# Initialize bot
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)
data_manager = DataManager(data_file=os.path.join(DATA_DIR, 'gm_data.json'))


def format_leaderboard(limit: int = 10) -> discord.Embed:
    """Format leaderboard as a Discord embed"""
    leaderboard = data_manager.get_leaderboard(limit)

    embed = discord.Embed(
        title="🌅 GM Streak Leaderboard",
        description="Top GM warriors this month!",
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )

    if not leaderboard:
        embed.add_field(
            name="No data yet!",
            value="Be the first to say GM and start your streak!",
            inline=False
        )
    else:
        # Create leaderboard text
        medals = ["🥇", "🥈", "🥉"]
        leaderboard_text = []

        for idx, (username, current_streak, best_streak) in enumerate(leaderboard):
            medal = medals[idx] if idx < 3 else f"**{idx + 1}.**"
            streak_text = f"{medal} **{username}**\n"
            streak_text += f"   Current: {current_streak} day{'s' if current_streak != 1 else ''}"

            if best_streak > current_streak:
                streak_text += f" | Best: {best_streak}"

            leaderboard_text.append(streak_text)

        embed.add_field(
            name="Current Standings",
            value="\n\n".join(leaderboard_text),
            inline=False
        )

    total_users = data_manager.get_total_users()
    embed.set_footer(text=f"Total GM warriors: {total_users} | Resets monthly")

    return embed


@bot.event
async def on_ready():
    """Called when bot is ready"""
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guild(s)')

    # Sync slash commands with Discord
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} command(s)')
    except Exception as e:
        print(f'Failed to sync commands: {e}')

    # Start scheduled tasks
    start_scheduler()

    # Check if monthly reset is needed
    if data_manager.should_reset_monthly():
        print("New month detected! Resetting streaks...")
        data_manager.reset_monthly_streaks()


@bot.event
async def on_message(message):
    """Listen for GM messages"""
    # Ignore messages from the bot itself
    if message.author.bot:
        return

    # Check if we should only listen in a specific channel
    if GM_CHANNEL_ID and str(message.channel.id) != GM_CHANNEL_ID:
        # Still process commands in other channels
        await bot.process_commands(message)
        return

    # Check if message matches GM allowlist (with time validation)
    tz = pytz.timezone(TIMEZONE)
    current_time = datetime.now(tz)
    current_hour = current_time.hour

    if data_manager.is_gm_message(message.content, current_hour):
        # Record the GM
        user_id = str(message.author.id)
        username = message.author.display_name

        streak, is_new_record, already_counted = data_manager.record_gm(user_id, username)

        # React to the message
        await message.add_reaction("🌅")

        # Send appropriate message based on situation
        if already_counted:
            # User already said GM today
            await message.channel.send(
                f"☀️ {message.author.mention}, you already said GM today! "
                f"Your current streak is **{streak} day{'s' if streak != 1 else ''}**. "
                f"Come back tomorrow to keep it going!"
            )
        elif is_new_record and streak > 1:
            await message.channel.send(
                f"🔥 **New personal record!** {message.author.mention} is on a "
                f"**{streak} day streak!** Keep it up! 🚀"
            )
        elif streak == 1:
            await message.channel.send(
                f"Good morning {message.author.mention}! Your streak has started! ☀️"
            )
        elif streak % 7 == 0:  # Weekly milestone
            await message.channel.send(
                f"🎉 **{streak} days!** {message.author.mention} has been saying GM for "
                f"{streak // 7} week{'s' if streak // 7 != 1 else ''}! Amazing dedication! 💪"
            )
        elif streak in [10, 25, 50, 100]:  # Special milestones
            await message.channel.send(
                f"🏆 **MILESTONE!** {message.author.mention} has reached a "
                f"**{streak} day streak!** Legendary! 🌟"
            )

    # Process commands
    await bot.process_commands(message)


@bot.tree.command(name='leaderboard', description='Show the GM leaderboard')
@app_commands.describe(limit='Number of users to show (1-25, default: 10)')
async def leaderboard_command(interaction: discord.Interaction, limit: int = 10):
    """Show the GM leaderboard"""
    if limit < 1:
        limit = 10
    if limit > 25:
        limit = 25

    embed = format_leaderboard(limit)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name='streak', description='Check your current GM streak')
async def streak_command(interaction: discord.Interaction):
    """Check your current streak"""
    user_id = str(interaction.user.id)
    streak = data_manager.get_user_streak(user_id)

    if streak == 0:
        await interaction.response.send_message(
            f"{interaction.user.mention}, you don't have an active streak yet! "
            f"Say GM to start one! 🌅"
        )
    else:
        user_data = data_manager.data["users"].get(user_id, {})
        best = user_data.get("best_streak", 0)

        message = f"🔥 {interaction.user.mention}, your current streak is **{streak} day{'s' if streak != 1 else ''}**!"

        if best > streak:
            message += f"\nYour best this month: **{best} days**"

        await interaction.response.send_message(message)


@bot.tree.command(name='gmhelp', description='Show bot help and information')
async def help_command(interaction: discord.Interaction):
    """Show bot help"""
    embed = discord.Embed(
        title="GM Bot Help",
        description="Track your daily GM streaks!",
        color=discord.Color.blue()
    )

    embed.add_field(
        name="How it works",
        value=(
            "Say **GM** in the chat each day to maintain your streak!\n"
            "Miss a day and your streak resets to 0.\n"
            "Streaks reset at the start of each month."
        ),
        inline=False
    )

    embed.add_field(
        name="Commands",
        value=(
            "`/leaderboard` - Show the top GM warriors\n"
            "`/streak` - Check your current streak\n"
            "`/gmlist` - Show what phrases count as GM\n"
            "`/gmadd <phrase>` - Add a phrase to allowlist (admin only)\n"
            "`/gmremove <phrase>` - Remove a phrase from allowlist (admin only)\n"
            "`/gmhelp` - Show this help message"
        ),
        inline=False
    )

    embed.add_field(
        name="Leaderboard",
        value="The leaderboard is posted automatically every Monday morning!",
        inline=False
    )

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name='gmlist', description='Show what phrases count as GM')
async def gmlist_command(interaction: discord.Interaction):
    """Show the current GM allowlist"""
    allowlist = data_manager.get_gm_allowlist()

    embed = discord.Embed(
        title="✅ GM Allowlist",
        description="These phrases count as GM messages:",
        color=discord.Color.green()
    )

    if allowlist:
        # Sort by phrase
        sorted_list = sorted(allowlist, key=lambda x: x["phrase"])

        phrases = []
        for item in sorted_list:
            phrase = item["phrase"]
            time_range = item.get("time_range", "anytime")

            if time_range == "anytime":
                phrases.append(f"• `{phrase}` - ⏰ Anytime")
            else:
                phrases.append(f"• `{phrase}` - ⏰ {time_range}:00")

        embed.add_field(
            name="Accepted Phrases",
            value="\n".join(phrases),
            inline=False
        )
    else:
        embed.add_field(
            name="No phrases yet!",
            value="Use `/gmadd <phrase> <time_range>` to add one.",
            inline=False
        )

    embed.set_footer(text="All phrases are case-insensitive | Time ranges in 24-hour format")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name='gmadd', description='Add a phrase to the GM allowlist with time range (admin only)')
@app_commands.describe(
    phrase='The phrase to add to the allowlist',
    time_range='Time range (e.g., "5-12" for 5 AM-12 PM, or "anytime" for 24/7)'
)
@app_commands.default_permissions(administrator=True)
async def gmadd_command(interaction: discord.Interaction, phrase: str, time_range: str = "anytime"):
    """Add a phrase to the GM allowlist with optional time range (admin only)"""
    if not phrase or not phrase.strip():
        await interaction.response.send_message("❌ Please provide a valid phrase to add.")
        return

    success, error_msg = data_manager.add_to_allowlist(phrase, time_range)

    if success:
        if time_range.lower() == "anytime":
            await interaction.response.send_message(
                f"✅ Added `{phrase.lower()}` to the GM allowlist! (Valid anytime)"
            )
        else:
            await interaction.response.send_message(
                f"✅ Added `{phrase.lower()}` to the GM allowlist! (Valid {time_range}:00)"
            )
    else:
        await interaction.response.send_message(f"❌ {error_msg}")


@bot.tree.command(name='gmremove', description='Remove a phrase from the GM allowlist (admin only)')
@app_commands.describe(phrase='The phrase to remove from the allowlist')
@app_commands.default_permissions(administrator=True)
async def gmremove_command(interaction: discord.Interaction, phrase: str):
    """Remove a phrase from the GM allowlist (admin only)"""
    if not phrase or not phrase.strip():
        await interaction.response.send_message("❌ Please provide a valid phrase to remove.")
        return

    success = data_manager.remove_from_allowlist(phrase)

    if success:
        await interaction.response.send_message(f"✅ Removed `{phrase.lower()}` from the GM allowlist!")
    else:
        await interaction.response.send_message(f"❌ `{phrase.lower()}` is not in the allowlist.")


async def post_weekly_leaderboard():
    """Post the leaderboard to all configured channels"""
    print(f"Posting weekly leaderboard at {datetime.now()}")

    embed = format_leaderboard(10)

    # Add a special header for the weekly post
    embed.description = "🎯 **Weekly Leaderboard Update!** 🎯\n\nTop GM warriors this month!"

    # If a specific channel is configured, post there
    if GM_CHANNEL_ID:
        try:
            channel = bot.get_channel(int(GM_CHANNEL_ID))
            if channel:
                await channel.send(embed=embed)
                data_manager.mark_leaderboard_posted()
                print("Leaderboard posted successfully!")
            else:
                print(f"Warning: Could not find channel {GM_CHANNEL_ID}")
        except Exception as e:
            print(f"Error posting leaderboard: {e}")
    else:
        # Post to all guilds the bot is in
        for guild in bot.guilds:
            # Try to find a suitable channel (general, gm, etc.)
            target_channel = None

            for channel in guild.text_channels:
                if channel.name.lower() in ['general', 'gm', 'chat', 'main']:
                    target_channel = channel
                    break

            # If no suitable channel found, use the first text channel
            if not target_channel and guild.text_channels:
                target_channel = guild.text_channels[0]

            if target_channel:
                try:
                    await target_channel.send(embed=embed)
                    print(f"Posted leaderboard to {guild.name}")
                except discord.Forbidden:
                    print(f"No permission to post in {guild.name}")
                except Exception as e:
                    print(f"Error posting to {guild.name}: {e}")

        data_manager.mark_leaderboard_posted()


def check_monthly_reset():
    """Check and perform monthly reset if needed"""
    if data_manager.should_reset_monthly():
        print(f"Performing monthly reset at {datetime.now()}")
        data_manager.reset_monthly_streaks()


def start_scheduler():
    """Start the scheduled tasks"""
    scheduler = AsyncIOScheduler()
    tz = pytz.timezone(TIMEZONE)

    # Schedule weekly leaderboard for Monday at 9:00 AM
    scheduler.add_job(
        post_weekly_leaderboard,
        CronTrigger(day_of_week='mon', hour=9, minute=0, timezone=tz),
        id='weekly_leaderboard'
    )

    # Check for monthly reset daily at midnight
    scheduler.add_job(
        check_monthly_reset,
        CronTrigger(hour=0, minute=1, timezone=tz),
        id='monthly_reset_check'
    )

    scheduler.start()
    print(f"Scheduler started with timezone: {TIMEZONE}")
    print(f"Weekly leaderboard will post every Monday at 9:00 AM {TIMEZONE}")
    print(f"Monthly reset check runs daily at 12:01 AM {TIMEZONE}")


if __name__ == '__main__':
    if not TOKEN:
        print("Error: DISCORD_TOKEN not found in environment variables!")
        print("Please create a .env file with your bot token.")
        exit(1)

    bot.run(TOKEN)
