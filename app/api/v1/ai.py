from __future__ import annotations

from flask import Blueprint, jsonify, request, session

from app.services.ai_tutor import (
    ai_context_from_payload,
    ai_service,
    conversation_messages,
    create_conversation,
    get_conversation,
    retrieve_context,
    save_message,
)

bp = Blueprint("ai_v1", __name__, url_prefix="/api/v1/ai")


def _user_id():
    return session.get("user_id")


@bp.get("/status")
def status():
    return jsonify(ai_service.status())


@bp.post("/chat")
def chat():
    user_id = _user_id()
    if not user_id:
        return jsonify({"success": False, "message": "Authentication required.", "code": "AUTH_REQUIRED"}), 401
    payload = request.get_json(silent=True) or {}
    question = str(payload.get("message", "")).strip()
    if not question:
        return jsonify({"success": False, "message": "Ask a question to continue.", "code": "MESSAGE_REQUIRED"}), 400
    if len(question) > 4000:
        return jsonify({"success": False, "message": "Please keep your question under 4000 characters.", "code": "MESSAGE_TOO_LONG"}), 400
    conversation_id = str(payload.get("conversation_id", "")).strip() or create_conversation(user_id, payload)
    if not get_conversation(user_id, conversation_id):
        return jsonify({"success": False, "message": "Conversation not found.", "code": "CONVERSATION_NOT_FOUND"}), 404
    context = ai_context_from_payload(payload)
    history = conversation_messages(user_id, conversation_id)
    save_message(user_id, conversation_id, "user", question, payload, "student")
    answer, provider = ai_service.answer(question, context, history)
    save_message(user_id, conversation_id, "assistant", answer, {"lesson_id": context.lesson_id}, provider)
    return jsonify({
        "success": True, "conversation_id": conversation_id, "answer": answer, "provider": provider,
        "status": ai_service.status(), "sources": [{"source_id": chunk["source_id"], "chapter_id": chunk["chapter_id"],
        "topic_id": chunk["topic_id"], "content_version": chunk["content_version"]} for chunk in
        retrieve_context(context, question)],
    })


@bp.get("/conversations/<conversation_id>")
def conversation(conversation_id):
    user_id = _user_id()
    if not user_id:
        return jsonify({"success": False, "message": "Authentication required."}), 401
    if not get_conversation(user_id, conversation_id):
        return jsonify({"success": False, "message": "Conversation not found."}), 404
    return jsonify({"conversation_id": conversation_id, "messages": conversation_messages(user_id, conversation_id)})
