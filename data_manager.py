"""
Data manager for GM Bot streak tracking
"""
import json
import os
import pytz
from datetime import datetime, date
from typing import Dict, List, Tuple

# Badge definitions: (threshold, emoji, name)
# Ordered by threshold ascending - users earn all badges up to their best streak
STREAK_BADGES = [
    (3,   "🌱", "Sprout"),
    (7,   "🔥", "Week Warrior"),
    (14,  "⭐", "Fortnight Star"),
    (21,  "🌟", "Triple Week"),
    (30,  "💎", "Monthly Legend"),
    (50,  "👑", "Half Century"),
    (75,  "🏅", "Diamond Dedication"),
    (100, "🏆", "Centurion"),
    (150, "🐉", "Dragon"),
    (200, "🌈", "Mythical"),
    (365, "☀️", "Year-Round Sun"),
]


class DataManager:
    def __init__(self, data_file: str = "gm_data.json", timezone: str = None):
        self.data_file = data_file
        # Use provided timezone or get from environment variable, default to UTC
        self.timezone_str = timezone or os.getenv('TIMEZONE', 'UTC')
        self.timezone = pytz.timezone(self.timezone_str)
        self.data = self._load_data()
        self._ensure_allowlist()

    def _load_data(self) -> dict:
        """Load data from JSON file or create new data structure"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print(f"Warning: Could not decode {self.data_file}, creating new data")

        # Initialize new data structure
        return {
            "users": {},  # user_id -> {current_streak, last_gm_date, best_streak}
            "last_leaderboard_post": None,
            "gm_allowlist": [  # List of {phrase, time_range} objects
                {"phrase": "gm", "time_range": "anytime"},
                {"phrase": "good morning", "time_range": "anytime"},
                {"phrase": "gm!", "time_range": "anytime"},
                {"phrase": "morning", "time_range": "anytime"}
            ]
        }

    def _save_data(self):
        """Save data to JSON file"""
        with open(self.data_file, 'w') as f:
            json.dump(self.data, f, indent=2)

    def _get_current_date(self) -> date:
        """Get current date in the configured timezone"""
        return datetime.now(self.timezone).date()

    def record_gm(self, user_id: str, username: str) -> Tuple[int, bool, bool]:
        """
        Record a GM for a user and update their streak

        Returns:
            Tuple of (current_streak, is_new_record, already_counted_today)
        """
        today = self._get_current_date().isoformat()
        user_id = str(user_id)

        # Initialize user if they don't exist
        if user_id not in self.data["users"]:
            self.data["users"][user_id] = {
                "username": username,
                "current_streak": 0,
                "last_gm_date": None,
                "best_streak": 0,
                "previous_streak": 0
            }

        user_data = self.data["users"][user_id]
        last_gm = user_data["last_gm_date"]

        # Check if user already said GM today
        if last_gm == today:
            return user_data["current_streak"], False, True

        # Update username in case it changed
        user_data["username"] = username

        # Calculate new streak
        if last_gm is None:
            # First time saying GM
            user_data["current_streak"] = 1
        else:
            last_date = date.fromisoformat(last_gm)
            today_date = self._get_current_date()
            days_diff = (today_date - last_date).days

            if days_diff == 1:
                # Consecutive day
                user_data["current_streak"] += 1
            else:
                # Streak broken, save it as previous_streak before resetting
                user_data["previous_streak"] = user_data["current_streak"]
                user_data["current_streak"] = 1

        user_data["last_gm_date"] = today

        # Update best_streak if this is a new personal best
        if user_data["current_streak"] > user_data["best_streak"]:
            user_data["best_streak"] = user_data["current_streak"]

        # Only announce new record the moment they beat their previous streak
        # (not every day after that)
        previous = user_data.get("previous_streak", 0)
        is_new_record = user_data["current_streak"] == previous + 1 and previous > 0

        self._save_data()
        return user_data["current_streak"], is_new_record, False

    def get_user_streak(self, user_id: str) -> int:
        """Get current streak for a user"""
        user_id = str(user_id)
        if user_id not in self.data["users"]:
            return 0
        return self.data["users"][user_id]["current_streak"]

    def reset_user_streak(self, user_id: str) -> int:
        """
        Reset a specific user's streak to 0 (penalty for rule violation)

        Returns:
            The streak that was lost (0 if user didn't exist)
        """
        user_id = str(user_id)
        if user_id not in self.data["users"]:
            return 0

        lost_streak = self.data["users"][user_id]["current_streak"]
        # Save the lost streak as previous_streak before resetting
        self.data["users"][user_id]["previous_streak"] = lost_streak
        self.data["users"][user_id]["current_streak"] = 0
        self.data["users"][user_id]["last_gm_date"] = None
        self._save_data()
        return lost_streak

    def get_leaderboard(self, limit: int = 10) -> List[Tuple[str, int, int, str]]:
        """
        Get top users by current streak

        Returns:
            List of tuples (username, current_streak, best_streak, user_id)
        """
        users = []
        for user_id, user_data in self.data["users"].items():
            users.append((
                user_data["username"],
                user_data["current_streak"],
                user_data["best_streak"],
                user_id
            ))

        # Sort by current streak (descending), then by best streak
        users.sort(key=lambda x: (x[1], x[2]), reverse=True)
        return users[:limit]

    def reset_all(self) -> int:
        """
        Reset ALL data - clears all users and their streaks completely.
        This is a destructive operation and should only be used by admins.

        Returns:
            Number of users that were cleared
        """
        user_count = len(self.data["users"])
        self.data["users"] = {}
        self.data["last_leaderboard_post"] = None
        self._save_data()
        return user_count

    def mark_leaderboard_posted(self):
        """Mark that leaderboard was posted"""
        self.data["last_leaderboard_post"] = datetime.now().isoformat()
        self._save_data()

    def get_total_users(self) -> int:
        """Get total number of users"""
        return len(self.data["users"])

    def _ensure_allowlist(self):
        """Ensure allowlist exists and migrate from old format if needed"""
        if "gm_allowlist" not in self.data:
            # Create new allowlist with default phrases
            self.data["gm_allowlist"] = [
                {"phrase": "gm", "time_range": "anytime"},
                {"phrase": "good morning", "time_range": "anytime"},
                {"phrase": "gm!", "time_range": "anytime"},
                {"phrase": "morning", "time_range": "anytime"}
            ]
            self._save_data()
        elif self.data["gm_allowlist"] and isinstance(self.data["gm_allowlist"][0], str):
            # Migrate old format (list of strings) to new format (list of objects)
            old_list = self.data["gm_allowlist"]
            self.data["gm_allowlist"] = [
                {"phrase": phrase, "time_range": "anytime"} for phrase in old_list
            ]
            self._save_data()
            print("Migrated GM allowlist to new time-range format")

    def get_gm_allowlist(self) -> List[Dict]:
        """Get the current GM allowlist with time ranges"""
        return self.data.get("gm_allowlist", [{"phrase": "gm", "time_range": "anytime"}])

    def add_to_allowlist(self, phrase: str, time_range: str = "anytime") -> Tuple[bool, str]:
        """
        Add a phrase to the GM allowlist with time range

        Args:
            phrase: The phrase to add (case-sensitive)
            time_range: Time range in format "HH-HH" (e.g., "5-12") or "anytime"

        Returns:
            Tuple of (success: bool, error_message: str)
        """
        phrase = phrase.strip()
        if not phrase:
            return False, "Phrase cannot be empty"

        # Validate time range
        if time_range.lower() != "anytime":
            if not self._validate_time_range(time_range):
                return False, "Invalid time range format. Use 'HH-HH' (e.g., '5-12') or 'anytime'"

        # Check if phrase already exists
        for item in self.data["gm_allowlist"]:
            if item["phrase"] == phrase:
                return False, f"Phrase '{phrase}' already exists"

        # Add new phrase
        self.data["gm_allowlist"].append({
            "phrase": phrase,
            "time_range": time_range.lower()
        })
        self._save_data()
        return True, ""

    def _validate_time_range(self, time_range: str) -> bool:
        """Validate time range format (HH-HH)"""
        try:
            if '-' not in time_range:
                return False
            parts = time_range.split('-')
            if len(parts) != 2:
                return False
            start, end = int(parts[0]), int(parts[1])
            return 0 <= start <= 23 and 0 <= end <= 23
        except (ValueError, IndexError):
            return False

    def remove_from_allowlist(self, phrase: str) -> bool:
        """
        Remove a phrase from the GM allowlist (case-sensitive)

        Returns:
            True if removed, False if not found
        """
        phrase = phrase.strip()

        for item in self.data["gm_allowlist"]:
            if item["phrase"] == phrase:
                self.data["gm_allowlist"].remove(item)
                self._save_data()
                return True
        return False

    def is_gm_message(self, message: str, current_hour: int = None) -> Tuple[bool, str, str]:
        """
        Check if a message matches any phrase in the allowlist and time range (case-sensitive)

        Args:
            message: The message to check
            current_hour: Current hour (0-23) for time range validation

        Returns:
            Tuple of (is_valid, matched_phrase, time_range)
            - is_valid: True if both phrase matches AND time is valid
            - matched_phrase: The phrase that was matched (or empty string)
            - time_range: The time range of the matched phrase (or empty string)
        """
        message = message.strip()

        for item in self.data["gm_allowlist"]:
            phrase = item["phrase"]
            time_range = item.get("time_range", "anytime")

            # Check if message matches the phrase (case-sensitive)
            phrase_matches = (
                message == phrase or
                message.startswith(phrase + " ") or
                message.endswith(" " + phrase) or
                message == phrase + "!" or
                message.startswith(phrase + "! ")
            )

            if not phrase_matches:
                continue

            # Phrase matched - now check time range
            if current_hour is not None and time_range != "anytime":
                if not self._is_within_time_range(current_hour, time_range):
                    # Phrase matched but time is invalid
                    return False, phrase, time_range

            # Both phrase and time are valid
            return True, phrase, time_range

        # No phrase matched
        return False, "", ""

    def _is_within_time_range(self, current_hour: int, time_range: str) -> bool:
        """Check if current hour is within the specified time range"""
        try:
            start, end = map(int, time_range.split('-'))
            if start <= end:
                # Normal range (e.g., 5-12)
                return start <= current_hour < end
            else:
                # Crosses midnight (e.g., 22-2)
                return current_hour >= start or current_hour < end
        except (ValueError, AttributeError):
            return True  # If invalid range, allow it

    def get_user_badges(self, user_id: str) -> List[Tuple[int, str, str]]:
        """
        Get all badges earned by a user based on their best streak.

        Returns:
            List of (threshold, emoji, name) tuples for earned badges
        """
        user_id = str(user_id)
        if user_id not in self.data["users"]:
            return []

        best_streak = self.data["users"][user_id].get("best_streak", 0)
        return [(t, e, n) for t, e, n in STREAK_BADGES if best_streak >= t]

    def get_newly_earned_badge(self, user_id: str, streak: int) -> Tuple[str, str] | None:
        """
        Check if the user just earned a new badge at exactly this streak count.

        Returns:
            (emoji, name) if a badge was just earned, None otherwise
        """
        for threshold, emoji, name in STREAK_BADGES:
            if streak == threshold:
                return (emoji, name)
        return None
