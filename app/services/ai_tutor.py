from __future__ import annotations

import json
import os
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.database.connection import get_connection
from app.services.content_catalog import get_lesson, list_questions


@dataclass
class AIContext:
    subject: str = ""
    chapter: str = ""
    topic: str = ""
    lesson_id: str = ""
    question: str = ""
    mode: str = "Explain"


class AIProvider:
    name = "unknown"

    def available(self) -> bool:
        raise NotImplementedError

    def generate(self, messages: list[dict], context: AIContext) -> str:
        raise NotImplementedError


class CloudProvider(AIProvider):
    name = "online"

    def __init__(self):
        self.url = os.environ.get("LEARNCRAFT_AI_CLOUD_URL", "").strip()
        self.api_key = os.environ.get("LEARNCRAFT_AI_CLOUD_KEY", "").strip()
        self.model = os.environ.get("LEARNCRAFT_AI_CLOUD_MODEL", "configured-model")

    def available(self) -> bool:
        return bool(self.url and self.api_key)

    def generate(self, messages: list[dict], context: AIContext) -> str:
        if not self.available():
            raise RuntimeError("Online AI is not configured.")
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": float(os.environ.get("LEARNCRAFT_AI_TEMPERATURE", "0.2")),
            "max_tokens": int(os.environ.get("LEARNCRAFT_AI_MAX_TOKENS", "500")),
        }
        request = Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        timeout = int(os.environ.get("LEARNCRAFT_AI_TIMEOUT", "20"))
        try:
            with urlopen(request, timeout=timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (OSError, URLError, TimeoutError) as exc:
            raise RuntimeError(f"Online AI request failed: {exc}") from exc
        choices = result.get("choices") or []
        if not choices or not choices[0].get("message", {}).get("content"):
            raise RuntimeError("Online AI returned no answer.")
        return str(choices[0]["message"]["content"]).strip()


class LocalModelManager:
    def __init__(self):
        self.command = os.environ.get("LEARNCRAFT_AI_LOCAL_COMMAND", "").strip()
        self.timeout = int(os.environ.get("LEARNCRAFT_AI_LOCAL_TIMEOUT", "30"))

    def status(self) -> dict:
        if not self.command:
            return {"state": "unavailable", "reason": "No local model command is configured."}
        return {"state": "available", "reason": "Configured local model command is ready."}

    def infer(self, messages: list[dict], context: AIContext) -> str:
        if not self.command:
            raise RuntimeError("No local AI model is configured.")
        try:
            completed = subprocess.run(
                self.command, input=json.dumps({"messages": messages}), text=True,
                capture_output=True, timeout=self.timeout, shell=True, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Local AI timed out. Try a shorter question.") from exc
        if completed.returncode != 0:
            raise RuntimeError("Local AI could not answer this question.")
        answer = completed.stdout.strip()
        if not answer:
            raise RuntimeError("Local AI returned no answer.")
        return answer


class LocalProvider(AIProvider):
    name = "offline"

    def __init__(self):
        self.manager = LocalModelManager()

    def available(self) -> bool:
        return self.manager.status()["state"] == "available"

    def generate(self, messages: list[dict], context: AIContext) -> str:
        return self.manager.infer(messages, context)


class AIService:
    def __init__(self):
        self.cloud = CloudProvider()
        self.local = LocalProvider()

    def status(self) -> dict:
        if self.cloud.available():
            return {"state": "online", "provider": self.cloud.name}
        if self.local.available():
            return {"state": "offline", "provider": self.local.name}
        return {"state": "unavailable", "provider": None, "reason": "Configure an online provider or local model command."}

    def answer(self, question: str, context: AIContext, history: list[dict]) -> tuple[str, str]:
        retrieved = retrieve_context(context, question)
        system = build_system_prompt(context, retrieved)
        messages = [{"role": "system", "content": system}] + history[-8:] + [{"role": "user", "content": question}]
        mode = os.environ.get("LEARNCRAFT_AI_MODE", "AUTO").upper()
        providers = [self.cloud, self.local] if mode == "AUTO" else ([self.cloud] if mode == "ONLINE" else [self.local])
        errors = []
        for provider in providers:
            if not provider.available():
                continue
            try:
                return provider.generate(messages, context), provider.name
            except RuntimeError as exc:
                errors.append(str(exc))
                continue
        limitation = "AI is unavailable right now. "
        if errors:
            limitation += errors[-1]
        else:
            limitation += "Configure an online provider or local model to continue."
        return limitation, "unavailable"


def retrieve_context(context: AIContext, question: str) -> list[dict]:
    chunks = []
    if context.lesson_id:
        lesson = get_lesson(context.lesson_id)
        if lesson:
            chunks.append({"source_id": lesson["lesson_id"], "chapter_id": lesson["chapter_id"],
                           "topic_id": lesson["topic_id"], "content_version": "2026-27",
                           "text": f"{lesson['title']}: {lesson['summary']} " +
                                   " ".join(block.get("text") or block.get("body", "") for block in lesson["blocks"])})
    for item in list_questions():
        haystack = f"{item['prompt']} {item['answer']} {item['explanation']}".lower()
        if any(term in haystack for term in question.lower().split() if len(term) > 3):
            chunks.append({"source_id": item["question_id"], "chapter_id": item["chapter_id"],
                           "topic_id": item.get("topic_id"), "content_version": "2026-27",
                           "text": f"Question: {item['prompt']} Answer: {item['answer']} Explanation: {item['explanation']}"})
    return chunks[:5]


def build_system_prompt(context: AIContext, chunks: list[dict]) -> str:
    evidence = "\n\n".join(f"[{chunk['source_id']}] {chunk['text']}" for chunk in chunks)
    return (
        "You are LearnCraft's CBSE Class X tutor. Explain simply, guide reasoning, and do not invent "
        "curriculum facts. If evidence is insufficient, say it cannot be verified from available curriculum content. "
        f"Mode: {context.mode}. Subject: {context.subject}. Chapter: {context.chapter}. Topic: {context.topic}.\n"
        f"Retrieved curriculum evidence:\n{evidence or 'No matching curriculum evidence was retrieved.'}"
    )


def create_conversation(user_id: int, context: dict | None = None) -> str:
    conversation_id = str(uuid.uuid4())
    connection = get_connection()
    connection.execute(
        "INSERT INTO ai_conversations (conversation_id, user_id, context_json) VALUES (?, ?, ?)",
        (conversation_id, int(user_id), json.dumps(context or {})),
    )
    connection.commit()
    connection.close()
    return conversation_id


def get_conversation(user_id: int, conversation_id: str) -> dict | None:
    connection = get_connection()
    row = connection.execute(
        "SELECT * FROM ai_conversations WHERE conversation_id = ? AND user_id = ?",
        (conversation_id, int(user_id)),
    ).fetchone()
    connection.close()
    return dict(row) if row else None


def conversation_messages(user_id: int, conversation_id: str) -> list[dict]:
    connection = get_connection()
    rows = connection.execute(
        "SELECT role, content, context_reference, provider, created_at FROM ai_messages WHERE conversation_id = ? AND user_id = ? ORDER BY created_at",
        (conversation_id, int(user_id)),
    ).fetchall()
    connection.close()
    return [dict(row) for row in rows]


def save_message(user_id: int, conversation_id: str, role: str, content: str, context_reference: dict | None = None, provider: str | None = None):
    if role not in {"user", "assistant", "system"}:
        raise ValueError("Invalid conversation role.")
    connection = get_connection()
    if not get_conversation(user_id, conversation_id):
        connection.close()
        raise PermissionError("Conversation not found.")
    connection.execute(
        "INSERT INTO ai_messages (message_id, conversation_id, user_id, role, content, context_reference, provider) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), conversation_id, int(user_id), role, content, json.dumps(context_reference or {}), provider),
    )
    connection.execute("UPDATE ai_conversations SET updated_at = CURRENT_TIMESTAMP WHERE conversation_id = ?", (conversation_id,))
    connection.commit()
    connection.close()


def ai_context_from_payload(payload: dict) -> AIContext:
    return AIContext(
        subject=str(payload.get("subject", ""))[:120],
        chapter=str(payload.get("chapter", ""))[:160],
        topic=str(payload.get("topic", ""))[:160],
        lesson_id=str(payload.get("lesson_id", ""))[:180],
        question=str(payload.get("current_question", ""))[:1000],
        mode=str(payload.get("mode", "Explain"))[:30],
    )


ai_service = AIService()
