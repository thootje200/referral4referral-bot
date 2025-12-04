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
        pass  # nothing to load, DB handles queue


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
        self.db.queue_add(user_id, referral_link)

        return True, "Your referral link has been added! You are in the queue."

    def get_queue_position(self, user_id: int) -> Optional[int]:
        queue = self.db.queue_get_all()
        queue_ids = [uid for uid, _ in queue]
        try:
            return queue_ids.index(user_id) + 1
        except ValueError:
            return None


    def get_next_user_to_assign(self) -> Optional[int]:
        queue = self.db.queue_get_all()

        for user_id, link in queue:
            user = self.db.get_user(user_id)
            if user and user.status == UserStatus.WAITING.value:
                return user_id

        return None

    def get_referral_target(self, user_id: int) -> Optional[int]:
        queue = self.db.queue_get_all()
        queue_ids = [uid for uid, _ in queue]
    
        if user_id not in queue_ids:
            return None

        pos = queue_ids.index(user_id)

        if pos + 1 < len(queue_ids):
            return queue_ids[pos + 1]

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

        # Haal volledige queue op uit de database
        queue = self.db.queue_get_all()
        queue_ids = [uid for uid, _ in queue]

        # User moet in de queue staan
        if user_id not in queue_ids:
            return False, None, None

        current_pos = queue_ids.index(user_id)

        # Zoek de volgende veilige referral target
        target_id = None
        for next_pos in range(current_pos + 1, len(queue_ids)):
            candidate_id = queue_ids[next_pos]
            # Skip mensen die eerder met elkaar matchten
            if not self.db.has_interacted_before(user_id, candidate_id):
                target_id = candidate_id
                break

        if not target_id:
            return False, None, None

        target_user = self.db.get_user(target_id)
        if not target_user:
            return False, None, None

        # Update user status to ASSIGNED
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

        # Move user to the back of the queue (DB-based)
        self.db.queue_remove(user_id)
        self.db.queue_add(user_id, user.referral_link)


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
        
        queue = [uid for uid, _ in self.db.queue_get_all()]
        for i, user_id in enumerate(queue[:limit], 1):

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
        queue = self.db.queue_get_all()
        if not queue:
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
        queue_ids = [uid for uid, _ in self.db.queue_get_all()]
        if user_id not in queue_ids:
            return False, "User not in queue."

        self.db.queue_remove(user_id)
        self.db.remove_user(user_id)


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
        queue_ids = [uid for uid, _ in self.db.queue_get_all()]
        
        total = len(queue_ids)
        waiting = sum(
            1 for uid in queue_ids
            if self.db.get_user(uid) and self.db.get_user(uid).status == UserStatus.WAITING.value
        )
        assigned = sum(
            1 for uid in queue_ids
            if self.db.get_user(uid) and self.db.get_user(uid).status == UserStatus.ASSIGNED.value
        )

        return (
            f"📈 Queue Status\n"
            f"Total users: {total}\n"
            f"Waiting: {waiting}\n"
            f"Assigned: {assigned}"
        )
