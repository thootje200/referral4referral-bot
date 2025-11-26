"""
Queue manager module for Referral4Referral Telegram Bot
Handles FIFO queue logic, referral assignment, and verification
"""

from typing import Optional, List, Tuple
from database import Database, User, UserStatus


class QueueManager:
    """
    Manages the referral queue system
    Handles assignment, verification, and persistence
    """

    def __init__(self, db: Database):
        """
        Initialize queue manager with database connection
        
        Args:
            db: Database instance
        """
        self.db = db
        self._load_queue_from_db()

    def _load_queue_from_db(self):
        """Load queue state from database or reconstruct from user statuses"""
        saved_queue = self.db.get_queue_state()
        
        if saved_queue:
            # Verify saved queue is still valid
            self.queue = [uid for uid in saved_queue if self.db.user_exists(uid)]
        else:
            # Reconstruct queue from database
            waiting_users = self.db.get_users_by_status(UserStatus.WAITING.value)
            self.queue = [user.user_id for user in waiting_users]

    def _save_queue_to_db(self):
        """Persist queue state to database"""
        self.db.save_queue_state(self.queue)

    def add_user_to_queue(self, user_id: int, referral_link: str) -> Tuple[bool, str]:
        """
        Add a new user to the queue
        
        Args:
            user_id: Telegram user ID
            referral_link: User's referral link
            
        Returns:
            Tuple[bool, str]: (success, message)
        """
        # Check if user already exists
        if self.db.user_exists(user_id):
            return False, "You are already in the queue."

        # Check if link already exists
        if self.db.link_exists(referral_link):
            return False, "This referral link is already registered."

        # Add user to database
        if not self.db.add_user(user_id, referral_link):
            return False, "Failed to add user. Please try again."

        # Add to queue
        self.queue.append(user_id)
        self._save_queue_to_db()

        return True, "Your referral link has been added! You are in the queue."

    def get_queue_position(self, user_id: int) -> Optional[int]:
        """
        Get a user's position in the queue (1-indexed)
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Position in queue (1-indexed), or None if not in queue
        """
        try:
            return self.queue.index(user_id) + 1
        except ValueError:
            return None

    def get_next_user_to_assign(self) -> Optional[int]:
        """
        Get the next user who should receive a referral
        (First user in WAITING status)
        
        Returns:
            User ID of next user, or None if queue is empty
        """
        for user_id in self.queue:
            user = self.db.get_user(user_id)
            if user and user.status == UserStatus.WAITING.value:
                return user_id
        return None

    def get_referral_target(self, user_id: int) -> Optional[int]:
        """
        Get the user ID of the next person who will provide a referral to the given user
        (Next user in ASSIGNED status, or first user if none assigned)
        
        Args:
            user_id: User requesting their target
            
        Returns:
            User ID to refer, or None if not found
        """
        # Find this user's position
        position = self.get_queue_position(user_id)
        if position is None:
            return None

        # Get the next user's ID
        if position < len(self.queue):
            return self.queue[position]  # position + 1 in 1-indexed, but index needs 0-indexed

        return None

    def assign_referral(self, user_id: int) -> Tuple[bool, Optional[str], Optional[int]]:
        """
        Assign a referral to a user (move to ASSIGNED status)
        """
        user = self.db.get_user(user_id)
        if not user:
            return False, None, None

        if user.status != UserStatus.WAITING.value:
            return False, None, None

        # Find the target user (next in queue after this user)
        target_id = self.get_referral_target(user_id)

        if not target_id:
            return False, None, None

        current_pos = self.queue.index(user_id)
        next_pos = current_pos + 1

        while next_pos < len(self.queue):
            candidate_id = self.queue[next_pos]
            if not self.db.has_interacted_before(user_id, candidate_id):
                target_id = candidate_id
                break
            next_pos += 1
        else:
            # Geen veilige kandidaat gevonden
            return False, None, None


        target_user = self.db.get_user(target_id)
        if not target_user:
            return False, None, None

        # Update user to ASSIGNED status with target link
        self.db.update_user_status(
            user_id,
            UserStatus.ASSIGNED.value,
            assigned_to=target_id
        )

        return True, target_user.referral_link, target_id



    def mark_referral_completed(self, user_id: int) -> Tuple[bool, str]:
        """
        Mark a user's referral as completed and move to DONE status
        Then requeue them by moving them to the back
        
        Args:
            user_id: User who completed the referral
            
        Returns:
            Tuple[bool, str]: (success, message)
        """
        user = self.db.get_user(user_id)
        if not user:
            return False, "User not found."

        if user.status != UserStatus.ASSIGNED.value:
            return False, "You don't have a pending referral to complete."

        # Get the target user they referred
        target_id = user.assigned_to

       # Mark referral as completed
        self.db.increment_completed_referrals(user_id)

        # Save referral pair to history (prevents future rematches)
        if target_id:
            self.db.add_referral_history(user_id, target_id)


        # Move user back to WAITING status
        self.db.update_user_status(user_id, UserStatus.WAITING.value, assigned_to=None)

        # Move them to the back of the queue
        if user_id in self.queue:
            self.queue.remove(user_id)
            self.queue.append(user_id)
            self._save_queue_to_db()

        return True, "Referral completed! You've been added back to the queue."

    def get_queue_list(self, limit: Optional[int] = None) -> List[str]:
        """
        Get formatted queue list for display
        
        Args:
            limit: Max number of users to show
            
        Returns:
            List of formatted queue entries
        """
        queue_list = []
        
        for i, user_id in enumerate(self.queue[:limit], 1):
            user = self.db.get_user(user_id)
            if user:
                status_emoji = {
                    UserStatus.WAITING.value: "⏳",
                    UserStatus.ASSIGNED.value: "📤",
                    UserStatus.DONE.value: "✅",
                }.get(user.status, "❓")

                queue_list.append(
                    f"{i}. User {user_id} {status_emoji} ({user.status})\n"
                    f"   Referrals completed: {user.completed_referrals}"
                )

        return queue_list

    def get_full_queue_list(self) -> str:
        """Get full queue as formatted string"""
        if not self.queue:
            return "Queue is empty."

        queue_list = self.get_queue_list()
        return "\n".join(queue_list)

    def remove_user_from_queue(self, user_id: int) -> Tuple[bool, str]:
        """
        Remove a user from the queue entirely
        
        Args:
            user_id: User to remove
            
        Returns:
            Tuple[bool, str]: (success, message)
        """
        if user_id not in self.queue:
            return False, "User not in queue."

        self.queue.remove(user_id)
        self.db.remove_user(user_id)
        self._save_queue_to_db()

        return True, f"User {user_id} has been removed from the queue."

    def get_user_info(self, user_id: int) -> Optional[str]:
        """
        Get formatted user information
        
        Args:
            user_id: User ID
            
        Returns:
            Formatted user info string, or None if not found
        """
        user = self.db.get_user(user_id)
        if not user:
            return None

        position = self.get_queue_position(user_id)
        status_text = {
            UserStatus.WAITING.value: "Waiting for assignment",
            UserStatus.ASSIGNED.value: f"Assigned (refer user {user.assigned_to})",
            UserStatus.DONE.value: "Completed",
        }.get(user.status, "Unknown")

        return (
            f"📊 User Info for {user_id}\n"
            f"Status: {status_text}\n"
            f"Queue position: {position or 'Not in queue'}\n"
            f"Referrals completed: {user.completed_referrals}\n"
            f"Joined: {user.created_at}"
        )

    def get_next_assignment(self) -> Tuple[Optional[int], Optional[str]]:
        """
        Process next user in queue for assignment
        Returns the user ID and their target referral link
        
        Returns:
            Tuple[int, str]: (user_id, referral_link) or (None, None)
        """
        next_user = self.get_next_user_to_assign()
        if not next_user:
            return None, None

        success, referral_link, target_id = self.assign_referral(next_user)
        if success:
            self._save_queue_to_db()
            return next_user, referral_link
        
        return None, None

    def get_queue_status(self) -> str:
        """Get readable queue status"""
        total = len(self.queue)
        waiting = sum(1 for uid in self.queue if self.db.get_user(uid) and self.db.get_user(uid).status == UserStatus.WAITING.value)
        assigned = sum(1 for uid in self.queue if self.db.get_user(uid) and self.db.get_user(uid).status == UserStatus.ASSIGNED.value)

        return (
            f"📈 Queue Status\n"
            f"Total users: {total}\n"
            f"Waiting: {waiting}\n"
            f"Assigned: {assigned}"
        )
