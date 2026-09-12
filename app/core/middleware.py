from __future__ import annotations

from flask import g, request

from app.main import current_user


def attach_request_context():
    g.current_user = current_user()


def register_middlewares(app):
    @app.before_request
    def before_request():
        attach_request_context()

    @app.after_request
    def after_request(response):
        response.headers["X-LearnCraft-App"] = "learncraft"
        return response
