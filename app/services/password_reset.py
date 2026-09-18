from __future__ import annotations

import hashlib
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from flask import current_app

from app.core.security import hash_password, password_policy
from app.database.connection import (
    consume_password_reset_token,
    create_password_reset_token,
    get_user_by_email,
    update_user_password,
)


class PasswordResetService:
    otp_lifetime = timedelta(minutes=10)

    def request_otp(self, email: str) -> bool:
        user = get_user_by_email(email)
        if not user:
            return False

        otp = f"{secrets.randbelow(1_000_000):06d}"
        # Store expiry in SQLite CURRENT_TIMESTAMP-compatible format so the
        # ``expires_at > CURRENT_TIMESTAMP`` check in consume works. ISO-8601
        # with a "T"/timezone suffix never compares correctly against
        # ``YYYY-MM-DD HH:MM:SS`` and made OTPs effectively never expire.
        expires_at = (datetime.now(timezone.utc) + self.otp_lifetime).strftime("%Y-%m-%d %H:%M:%S")
        create_password_reset_token(user["id"], self._hash_otp(otp), expires_at)
        try:
            self._send_otp(user["email"], otp)
        except RuntimeError:
            # Offline-first: no SMTP configured. Log the OTP so a local
            # user can still complete the flow; never block the request.
            try:
                current_app.logger.info("Password reset OTP for %s: %s", email, otp)
            except Exception:
                pass
        return True

    def reset_direct(self, email: str, new_password: str) -> tuple[bool, str]:
        """Reset without an OTP (offline-friendly direct reset)."""
        valid, message = password_policy(new_password)
        if not valid:
            return False, message or "Invalid password."
        user = get_user_by_email(email)
        if not user:
            return False, "If an account exists, the password has been reset."
        update_user_password(user["id"], hash_password(new_password))
        return True, "Password reset successfully."

    def reset_password(self, email: str, otp: str, new_password: str) -> tuple[bool, str]:
        valid, message = password_policy(new_password)
        if not valid:
            return False, message or "Invalid password."
        user = get_user_by_email(email)
        if not user or not otp.isdigit() or len(otp) != 6:
            return False, "The OTP is invalid or expired."
        if not consume_password_reset_token(user["id"], self._hash_otp(otp)):
            return False, "The OTP is invalid or expired."
        update_user_password(user["id"], hash_password(new_password))
        return True, "Password reset successfully."

    @staticmethod
    def _hash_otp(otp: str) -> str:
        return hashlib.sha256(otp.encode("utf-8")).hexdigest()

    @staticmethod
    def _send_otp(email: str, otp: str) -> None:
        host = current_app.config.get("MAIL_HOST")
        if not host:
            if current_app.config.get("TESTING") or current_app.config.get("MAIL_SUPPRESS_SEND"):
                current_app.logger.info("Password reset OTP for %s: %s", email, otp)
                return
            raise RuntimeError("Password email is not configured.")

        message = EmailMessage()
        message["Subject"] = "Your LearnCraft password reset OTP"
        message["From"] = current_app.config.get("MAIL_FROM", "no-reply@learncraft.local")
        message["To"] = email
        message.set_content(f"Your LearnCraft password reset OTP is {otp}. It expires in 10 minutes.")

        port = int(current_app.config.get("MAIL_PORT", 587))
        with smtplib.SMTP(host, port, timeout=10) as server:
            if current_app.config.get("MAIL_USE_TLS", True):
                server.starttls()
            username = current_app.config.get("MAIL_USERNAME")
            password = current_app.config.get("MAIL_PASSWORD")
            if username and password:
                server.login(username, password)
            server.send_message(message)