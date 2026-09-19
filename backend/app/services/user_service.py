from __future__ import annotations

from app.repositories.user_repository import UserRepository


class UserService:
    def __init__(self, repository: UserRepository | None = None):
        self.repository = repository or UserRepository()

    def get_user(self, user_id):
        return self.repository.get_by_id(user_id)

    def get_users(self):
        return self.repository.list()

    def update_profile(self, user_id, **kwargs):
        return self.repository.update_profile(user_id, **kwargs)
