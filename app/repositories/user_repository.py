from __future__ import annotations

from app.database.connection import create_user, get_user_by_email, get_user_by_id, get_users, update_user_profile, user_payload


class UserRepository:
    def create(self, name, email, password_hash, role="STUDENT", avatar=None):
        return create_user(name=name, email=email, password_hash=password_hash, role=role, avatar=avatar)

    def get_by_email(self, email):
        return get_user_by_email(email)

    def get_by_id(self, user_id):
        return get_user_by_id(user_id)

    def list(self):
        return get_users()

    def update_profile(self, user_id, **kwargs):
        return update_user_profile(user_id, **kwargs)

    def payload(self, user):
        return user_payload(user)
