from __future__ import annotations

import json
import os
import re
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.database.connection import get_connection
from app.services.content_catalog import (
    get_lesson,
    list_class10_subjects,
    list_class9_subjects,
    list_questions,
)


@lru_cache(maxsize=1)
def ncert_questions() -> tuple[dict, ...]:
    """Load the extracted Class 10 NCERT question bank once per process."""
    path = Path(__file__).resolve().parents[2] / "data" / "curriculum" / "ncert_class10_syllabus.json"
    if not path.exists():
        return ()
    data = json.loads(path.read_text(encoding="utf-8"))
    questions = []
    for subject, grades in data.items():
        for chapter in grades.get("10", grades.get(10, [])):
            for item in chapter.get("questions", []):
                questions.append({
                    **item,
                    "subject": subject,
                    "chapter_name": chapter.get("chapter_name", ""),
                    "chapter_number": chapter.get("chapter_number"),
                })
    return tuple(questions)


@lru_cache(maxsize=1)
def feature_curriculum() -> tuple[dict, ...]:
    """Flatten the portable Features Class IX/X chapters for local retrieval."""
    items = []
    for class_level, subjects in (("Class IX", list_class9_subjects()), ("Class X", list_class10_subjects())):
        for subject in subjects:
            for chapter in subject.get("chapters", []):
                items.append({
                    "source_id": f"features:{class_level.lower().replace(' ', '-')}-{subject['slug']}-ch{chapter['number']}",
                    "content_version": "features-2026-27",
                    "subject": subject["name"],
                    "class_level": class_level,
                    "chapter_number": chapter["number"],
                    "chapter_name": chapter["title"],
                    "text": chapter["summary"],
                    "source_reference": subject.get("pdf_url", ""),
                })
    return tuple(items)


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
        mode = os.environ.get("LEARNCRAFT_AI_MODE", "OFFLINE").upper()
        if mode not in {"ONLINE", "AUTO"}:
            if self.local.available():
                return {"state": "offline", "provider": self.local.name}
            return {"state": "offline", "provider": "built-in", "reason": "Using LearnCraft's built-in offline assistant."}
        if self.cloud.available():
            return {"state": "online", "provider": self.cloud.name}
        if self.local.available():
            return {"state": "offline", "provider": self.local.name}
        return {"state": "offline", "provider": "built-in", "reason": "Using LearnCraft's built-in offline assistant."}

    def answer(self, question: str, context: AIContext, history: list[dict]) -> tuple[str, str]:
        retrieved = retrieve_context(context, question)
        system = build_system_prompt(context, retrieved)
        messages = [{"role": "system", "content": system}] + history[-8:] + [{"role": "user", "content": question}]
        mode = os.environ.get("LEARNCRAFT_AI_MODE", "OFFLINE").upper()
        providers = [self.local, self.cloud] if mode == "AUTO" else ([self.cloud] if mode == "ONLINE" else [self.local])
        errors = []
        for provider in providers:
            if not provider.available():
                continue
            try:
                return provider.generate(messages, context), provider.name
            except RuntimeError as exc:
                errors.append(str(exc))
                continue
        # Keep Ask AI useful in the default offline installation. A configured
        # provider is preferred, but the app must still answer common questions
        # when no model/API key has been installed.
        return offline_answer(question, context, retrieved), "offline"


def offline_answer(question: str, context: AIContext, chunks: list[dict]) -> str:
    """Provide a deterministic local answer when no external model is configured."""
    text = (question or "").strip().lower()
    normalized_question = _normalize_question(question)

    # Prefer the exact curriculum question and its stored explanation over a
    # generic fallback. This keeps answers specific when the user asks a known
    # question from the question bank.
    best_match = None
    best_score = 0.0
    for item in (*list_questions(), *ncert_questions()):
        prompt = _normalize_question(item.get("prompt", ""))
        if not prompt:
            prompt = _normalize_question(item.get("question", ""))
        if not prompt:
            continue
        score = _question_similarity(normalized_question, prompt)
        if score > best_score:
            best_match = item
            best_score = score
    if best_match is not None and best_score >= 0.55:
        return (
            f"Direct answer\n{best_match.get('answer', 'No answer recorded.')}\n\n"
            f"Why it matters\n{best_match.get('explanation') or 'Review the related chapter and connect this idea to an example.'}\n\n"
            f"Study context\nSubject: {best_match.get('subject', context.subject or 'Class 10')}\n"
            f"Chapter: {best_match.get('chapter_name', context.chapter or 'Relevant topic')}\n\n"
            "Next step\nTry explaining the answer in your own words and solve one similar question."
        )

    app_terms = (
        "app", "login", "log in", "sign in", "password", "otp", "forgot password",
        "sign out", "logout", "settings", "profile", "progress", "dashboard",
        "not saving", "app error", "app issue", "app problem", "not working",
    )

    if any(term in text for term in app_terms) or "app" in (context.mode or "").lower():
        if "password" in text or "otp" in text or "forgot" in text:
            return (
                "To reset your LearnCraft password: open the login page, choose "
                "Forgot password, enter your registered email, and submit the six-digit "
                "OTP sent to your inbox. Enter the OTP with your new password within "
                "10 minutes. If no email arrives, check spam and verify the email address."
            )
        if "login" in text or "log in" in text or "sign in" in text:
            return (
                "For a LearnCraft login issue, first verify your email and password. "
                "If the password is incorrect, use Forgot password to request a six-digit "
                "OTP. If the page still does not load, refresh the browser and try again "
                "with cookies enabled."
            )
        if "sign out" in text or "logout" in text:
            return (
                "Open your profile menu from the top-right avatar or the sidebar profile "
                "card, then select Sign out. This clears the current session and returns "
                "you to the login page."
            )
        if "progress" in text or "dashboard" in text or "lab" in text:
            return (
                "LearnCraft tracks progress per profile. Open My Learning or Progress to "
                "see saved lesson and lab completion. Start or resume the subject card; "
                "your percentage updates from the latest saved activity rather than a "
                "shared preset."
            )
        if "settings" in text or "profile" in text:
            return (
                "Open the profile avatar in the top-right corner or the sidebar profile "
                "card. The menu contains Profile, Settings, Help, and Sign out."
            )
        return (
            "I can help with LearnCraft app issues. Tell me the exact screen, the action "
            "you took, and the message you saw. For example: login, OTP/password reset, "
            "profile menu, progress tracking, settings, or a lab not saving."
        )

    # Use locally retrieved curriculum evidence when the user asks a subject question.
    question_chunk = next((chunk for chunk in chunks if chunk["source_id"] not in {"doc:README", "doc:OFFLINE_FIRST"}), None)
    if question_chunk:
        return (
            f"Concept\n{question_chunk['text']}\n\n"
            "How to use it\nIdentify the known values or key terms, connect them to this concept, and work through one example.\n\n"
            "Practice\nWrite one sentence explaining the idea, then share your working if you want a step-by-step check."
        )
    if context.subject or context.lesson_id:
        return (
            f"Focus\n{context.subject or 'This lesson'} · {context.chapter or 'Current topic'}\n\n"
            "Plan\nStart with the lesson concept, identify what the question is asking, and list the information you already know.\n\n"
            "Next step\nSend the exact question, answer choices, or your working for a guided solution."
        )
    return (
        "I am ready to help.\n\n"
        "Ask about a LearnCraft app issue or include the class, subject, chapter, and exact question.\n\n"
        "I will answer using the local curriculum and show the explanation and next practice step."
    )


def _normalize_question(value: str) -> str:
    return re.sub(r"[^a-z0-9\s]", " ", str(value or "").lower()).strip()


def _question_similarity(left: str, right: str) -> float:
    left_words = set(left.split())
    right_words = set(right.split())
    if not left_words or not right_words:
        return 0.0
    overlap = len(left_words & right_words) / len(right_words)
    if left == right:
        return 1.0
    return overlap


def retrieve_context(context: AIContext, question: str) -> list[dict]:
    chunks = []
    feature_chunks = []
    if context.lesson_id:
        lesson = get_lesson(context.lesson_id)
        if lesson:
            chunks.append({"source_id": lesson["lesson_id"], "chapter_id": lesson["chapter_id"],
                           "topic_id": lesson["topic_id"], "content_version": "2026-27",
                           "text": f"{lesson['title']}: {lesson['summary']} " +
                                   " ".join(block.get("text") or block.get("body", "") for block in lesson["blocks"])})
    for item in (*list_questions(), *ncert_questions()):
        prompt = item.get("prompt", item.get("question", ""))
        haystack = f"{prompt} {item.get('answer', '')} {item.get('explanation', '')}".lower()
        if any(term in haystack for term in question.lower().split() if len(term) > 3):
            source_id = item.get("question_id") or f"ncert:{item.get('subject', 'subject')}:{item.get('chapter_number', 0)}"
            chunks.append({"source_id": source_id, "chapter_id": item.get("chapter_id") or item.get("chapter_name"),
                           "topic_id": item.get("topic_id"), "content_version": "ncert-class10",
                           "text": f"Question: {prompt} Answer: {item.get('answer', '')} Explanation: {item.get('explanation', '')}"})

    query_terms = {term for term in _normalize_question(question).split() if len(term) > 3}
    for item in feature_curriculum():
        haystack = _normalize_question(f"{item['subject']} {item['chapter_name']} {item['text']}")
        if (context.subject and _normalize_question(context.subject) in haystack) or query_terms.intersection(haystack.split()):
            feature_chunks.append({
                "source_id": item["source_id"],
                "chapter_id": f"{item['subject']}-ch{item['chapter_number']}",
                "topic_id": None,
                "content_version": item["content_version"],
                "text": f"{item['class_level']} {item['subject']} · Chapter {item['chapter_number']}: {item['chapter_name']}. {item['text']}",
            })

    # Keep exact question-bank matches first for source accuracy. For broader
    # topic questions, put matching Features chapters ahead of generic matches.
    normalized_question = _normalize_question(question)
    exact_question = any(
        normalized_question == _normalize_question(item.get("prompt") or item.get("question", ""))
        for item in (*list_questions(), *ncert_questions())
    )
    chunks = chunks + feature_chunks if exact_question else feature_chunks + chunks

    # Detect app-related queries and add local documentation as context when relevant.
    app_keywords = {"app", "error", "issue", "login", "logout", "crash", "cannot", "unable", "bug", "not working", "help", "settings", "sign out", "signout"}
    qlower = (question or "").lower()
    mode_lower = (context.mode or "").lower()
    if any(k in qlower for k in app_keywords) or "app" in mode_lower or "help" in mode_lower:
        try:
            from pathlib import Path
            base = Path(__file__).resolve().parents[2]
            readme = base / "README.md"
            offline = base / "OFFLINE_FIRST.md"
            if readme.exists():
                text = readme.read_text(encoding="utf-8")
                chunks.insert(0, {"source_id": "doc:README", "chapter_id": None, "topic_id": None, "content_version": "docs", "text": text[:3000]})
            if offline.exists():
                text2 = offline.read_text(encoding="utf-8")
                chunks.insert(0, {"source_id": "doc:OFFLINE_FIRST", "chapter_id": None, "topic_id": None, "content_version": "docs", "text": text2[:2000]})
        except Exception:
            pass

    return chunks[:6]


def build_system_prompt(context: AIContext, chunks: list[dict]) -> str:
    evidence = "\n\n".join(f"[{chunk['source_id']}] {chunk['text']}" for chunk in chunks)
    # If any retrieved chunk originates from local app docs, switch to app troubleshooting persona.
    if any(str(chunk.get("source_id", "")).startswith("doc:") for chunk in chunks):
        return (
            "You are LearnCraft's App Assistant. Help the user troubleshoot, diagnose, and resolve issues with the LearnCraft application. "
            "Provide clear, safe, step-by-step instructions, recommend diagnostics to collect (logs, steps to reproduce, screenshots), and explain next steps. "
            "Do NOT fabricate internal logs or claim access to remote systems; if information is missing, ask the user for specific diagnostics. "
            f"Mode: {context.mode}. Subject: {context.subject}. Chapter: {context.chapter}. Topic: {context.topic}.\n"
            f"Retrieved application documentation and evidence:\n{evidence or 'No application documentation retrieved.'}"
        )

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
