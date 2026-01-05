"""
Data manager for GM Bot streak tracking
"""
import json
import os
from datetime import datetime, date
from typing import Dict, List, Tuple


class DataManager:
    def __init__(self, data_file: str = "gm_data.json"):
        self.data_file = data_file
        self.data = self._load_data()

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
            "monthly_reset_date": date.today().replace(day=1).isoformat(),
            "last_leaderboard_post": None
        }

    def _save_data(self):
        """Save data to JSON file"""
        with open(self.data_file, 'w') as f:
            json.dump(self.data, f, indent=2)

    def record_gm(self, user_id: str, username: str) -> Tuple[int, bool]:
        """
        Record a GM for a user and update their streak

        Returns:
            Tuple of (current_streak, is_new_record)
        """
        today = date.today().isoformat()
        user_id = str(user_id)

        # Initialize user if they don't exist
        if user_id not in self.data["users"]:
            self.data["users"][user_id] = {
                "username": username,
                "current_streak": 0,
                "last_gm_date": None,
                "best_streak": 0
            }

        user_data = self.data["users"][user_id]
        last_gm = user_data["last_gm_date"]

        # Check if user already said GM today
        if last_gm == today:
            return user_data["current_streak"], False

        # Update username in case it changed
        user_data["username"] = username

        # Calculate new streak
        if last_gm is None:
            # First time saying GM
            user_data["current_streak"] = 1
        else:
            last_date = date.fromisoformat(last_gm)
            today_date = date.today()
            days_diff = (today_date - last_date).days

            if days_diff == 1:
                # Consecutive day
                user_data["current_streak"] += 1
            else:
                # Streak broken, start over
                user_data["current_streak"] = 1

        user_data["last_gm_date"] = today

        # Check if this is a new personal best
        is_new_record = user_data["current_streak"] > user_data["best_streak"]
        if is_new_record:
            user_data["best_streak"] = user_data["current_streak"]

        self._save_data()
        return user_data["current_streak"], is_new_record

    def get_user_streak(self, user_id: str) -> int:
        """Get current streak for a user"""
        user_id = str(user_id)
        if user_id not in self.data["users"]:
            return 0
        return self.data["users"][user_id]["current_streak"]

    def get_leaderboard(self, limit: int = 10) -> List[Tuple[str, int, int]]:
        """
        Get top users by current streak

        Returns:
            List of tuples (username, current_streak, best_streak)
        """
        users = []
        for user_id, user_data in self.data["users"].items():
            users.append((
                user_data["username"],
                user_data["current_streak"],
                user_data["best_streak"]
            ))

        # Sort by current streak (descending), then by best streak
        users.sort(key=lambda x: (x[1], x[2]), reverse=True)
        return users[:limit]

    def reset_monthly_streaks(self):
        """Reset all streaks for the new month"""
        for user_data in self.data["users"].values():
            user_data["current_streak"] = 0
            user_data["last_gm_date"] = None
            user_data["best_streak"] = 0

        self.data["monthly_reset_date"] = date.today().replace(day=1).isoformat()
        self._save_data()

    def should_reset_monthly(self) -> bool:
        """Check if we should reset for a new month"""
        last_reset = date.fromisoformat(self.data["monthly_reset_date"])
        today = date.today()

        # Check if we're in a new month
        return (today.year > last_reset.year or
                (today.year == last_reset.year and today.month > last_reset.month))

    def mark_leaderboard_posted(self):
        """Mark that leaderboard was posted"""
        self.data["last_leaderboard_post"] = datetime.now().isoformat()
        self._save_data()

    def get_total_users(self) -> int:
        """Get total number of users"""
        return len(self.data["users"])
