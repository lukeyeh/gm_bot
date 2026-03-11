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

from data_manager import DataManager, STREAK_BADGES


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
data_manager = DataManager(data_file=os.path.join(DATA_DIR, 'gm_data.json'), timezone=TIMEZONE)


def format_leaderboard(limit: int = 10) -> discord.Embed:
    """Format leaderboard as a Discord embed"""
    leaderboard = data_manager.get_leaderboard(limit)

    embed = discord.Embed(
        title="🌅 GM Streak Leaderboard",
        description="Top GM warriors!",
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
        # Create leaderboard text with proper tie handling
        medals = ["🥇", "🥈", "🥉"]
        leaderboard_text = []

        current_rank = 1
        previous_streak = None

        for idx, (username, current_streak, best_streak) in enumerate(leaderboard):
            # If this person has a different streak than previous, increment rank
            if previous_streak is not None and current_streak != previous_streak:
                # New rank - increment by 1 for dense ranking
                current_rank += 1

            # Determine medal or rank number
            if current_rank <= 3:
                medal = medals[current_rank - 1]
            else:
                medal = f"**{current_rank}.**"

            streak_text = f"{medal} **{username}**\n"
            streak_text += f"   Current: {current_streak} day{'s' if current_streak != 1 else ''}"

            if best_streak > current_streak:
                streak_text += f" | Best: {best_streak}"

            leaderboard_text.append(streak_text)
            previous_streak = current_streak

        embed.add_field(
            name="Current Standings",
            value="\n\n".join(leaderboard_text),
            inline=False
        )

    total_users = data_manager.get_total_users()
    embed.set_footer(text=f"Total GM warriors: {total_users}")

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


@bot.event
async def on_message(message):
    """Listen for GM messages"""
    # Ignore messages from this bot itself to prevent loops
    if message.author.id == bot.user.id:
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

    is_valid, matched_phrase, time_range = data_manager.is_gm_message(message.content, current_hour)

    if matched_phrase:  # Phrase was matched
        if not is_valid:
            # Phrase matched but outside time range
            await message.add_reaction("⏰")
            if '-' in time_range:
                start, end = time_range.split('-')
                await message.channel.send(
                    f"⏰ {message.author.mention}, `{matched_phrase}` can only be said between "
                    f"**{start}:00 - {end}:00**! Current time: {current_time.strftime('%H:%M')} ({TIMEZONE})"
                )
            await bot.process_commands(message)
            return

        # Valid GM message - record it
        user_id = str(message.author.id)
        username = message.author.display_name

        streak, is_new_record, already_counted = data_manager.record_gm(user_id, username)

        # React to the message
        await message.add_reaction("🌅")

        # Check if user just earned a new badge
        new_badge = data_manager.get_newly_earned_badge(user_id, streak)

        # Send appropriate message based on situation
        if already_counted:
            # User already said GM today
            await message.channel.send(
                f"☀️ {message.author.mention}, you already said GM today! "
                f"Your current streak is **{streak} day{'s' if streak != 1 else ''}**. "
                f"Come back tomorrow to keep it going!"
            )
        elif new_badge:
            emoji, badge_name = new_badge
            await message.channel.send(
                f"{emoji} **NEW BADGE UNLOCKED!** {message.author.mention} earned the "
                f"**{badge_name}** badge with a **{streak} day streak!** {emoji}"
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
    else:
        # No phrase matched
        # If we're in a restricted GM channel, warn the user and reset their streak
        if GM_CHANNEL_ID:
            await message.add_reaction("👎")

            # Reset the user's streak as penalty
            user_id = str(message.author.id)
            lost_streak = data_manager.reset_user_streak(user_id)

            if lost_streak > 0:
                await message.channel.send(
                    f"👎 {message.author.mention}, you can only say allowlisted GM phrases in this channel!\n"
                    f"**Your {lost_streak} day streak has been reset to 0.** 💔\n"
                    f"Use `/gmlist` to see valid phrases."
                )
            else:
                await message.channel.send(
                    f"👎 {message.author.mention}, you can only say allowlisted GM phrases in this channel!\n"
                    f"Use `/gmlist` to see valid phrases."
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

        msg = f"🔥 {interaction.user.mention}, your current streak is **{streak} day{'s' if streak != 1 else ''}**!"

        if best > streak:
            msg += f"\nYour best: **{best} days**"

        # Show earned badges
        earned = data_manager.get_user_badges(user_id)
        if earned:
            badge_display = " ".join(emoji for _, emoji, _ in earned)
            msg += f"\nBadges: {badge_display}"

        await interaction.response.send_message(msg)


@bot.tree.command(name='badges', description='View your GM streak badges or see all available badges')
async def badges_command(interaction: discord.Interaction):
    """Show badges earned and available"""
    user_id = str(interaction.user.id)
    earned = data_manager.get_user_badges(user_id)
    earned_thresholds = {t for t, _, _ in earned}

    user_data = data_manager.data["users"].get(user_id, {})
    best_streak = user_data.get("best_streak", 0)

    embed = discord.Embed(
        title="🏅 GM Streak Badges",
        description=f"Your best streak: **{best_streak} day{'s' if best_streak != 1 else ''}**",
        color=discord.Color.purple()
    )

    badge_lines = []
    for threshold, emoji, name in STREAK_BADGES:
        if threshold in earned_thresholds:
            badge_lines.append(f"{emoji} **{name}** — {threshold} days ✅")
        else:
            badge_lines.append(f"🔒 ~~{name}~~ — {threshold} days")

    embed.add_field(
        name="Badges",
        value="\n".join(badge_lines),
        inline=False
    )

    earned_count = len(earned)
    total_count = len(STREAK_BADGES)
    embed.set_footer(text=f"Earned: {earned_count}/{total_count} badges")

    await interaction.response.send_message(embed=embed)


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
            "Miss a day and your streak resets to 0."
        ),
        inline=False
    )

    embed.add_field(
        name="Commands",
        value=(
            "`/leaderboard` - Show the top GM warriors\n"
            "`/streak` - Check your current streak\n"
            "`/badges` - View your streak badges\n"
            "`/gmlist` - Show what phrases count as GM\n"
            "`/gmadd <phrase>` - Add a phrase to allowlist (admin only)\n"
            "`/gmremove <phrase>` - Remove a phrase from allowlist (admin only)\n"
            "`/resetall` - Reset all data and streaks (admin only)\n"
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

    embed.set_footer(text="Phrases are case-sensitive | Time ranges in 24-hour format")
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
                f"✅ Added `{phrase}` to the GM allowlist! (Valid anytime)"
            )
        else:
            await interaction.response.send_message(
                f"✅ Added `{phrase}` to the GM allowlist! (Valid {time_range}:00)"
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
        await interaction.response.send_message(f"✅ Removed `{phrase}` from the GM allowlist!")
    else:
        await interaction.response.send_message(f"❌ `{phrase}` is not in the allowlist.")


@bot.tree.command(name='resetall', description='Reset ALL user data and streaks (admin only)')
@app_commands.default_permissions(administrator=True)
async def resetall_command(interaction: discord.Interaction):
    """Reset all user data and streaks - DESTRUCTIVE OPERATION (admin only)"""
    # Defer the response since we want to add a confirmation step
    await interaction.response.defer(ephemeral=True)

    # Get user count before reset
    user_count = data_manager.get_total_users()

    if user_count == 0:
        await interaction.followup.send("ℹ️ No data to reset - the database is already empty.")
        return

    # Reset all data
    cleared = data_manager.reset_all()

    await interaction.followup.send(
        f"⚠️ **ALL DATA HAS BEEN RESET!**\n\n"
        f"• Cleared {cleared} user(s)\n"
        f"• All streaks deleted\n"
        f"• Leaderboard cleared\n\n"
        f"Users can start fresh by saying GM!"
    )


async def post_weekly_leaderboard():
    """Post the leaderboard to all configured channels"""
    print(f"Posting weekly leaderboard at {datetime.now()}")

    embed = format_leaderboard(10)

    # Add a special header for the weekly post
    embed.description = "🎯 **Weekly Leaderboard Update!** 🎯\n\nTop GM warriors!"

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

    scheduler.start()
    print(f"Scheduler started with timezone: {TIMEZONE}")
    print(f"Weekly leaderboard will post every Monday at 9:00 AM {TIMEZONE}")


if __name__ == '__main__':
    if not TOKEN:
        print("Error: DISCORD_TOKEN not found in environment variables!")
        print("Please create a .env file with your bot token.")
        exit(1)

    bot.run(TOKEN)
