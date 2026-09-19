from __future__ import annotations

import json
import os
import re
import subprocess
import time
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
    load_packages,
    list_class10_subjects,
    list_class9_subjects,
    list_questions,
)


def strip_thinking(text: str) -> str:
    """Remove reasoning-model think blocks (e.g. qwen3 ``<think>…</think>``).

    Some local models emit their chain of thought before the final answer.
    The browser should only ever see the answer itself.
    """
    if not text:
        return text
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Unterminated block: drop everything from <think> to the end.
    cleaned = re.sub(r"<think>.*$", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    return cleaned.strip()


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
    """Flatten available Class IX/X chapters for local retrieval.

    The optional sibling ``Features`` project contains richer curriculum
    metadata, but LearnCraft must remain useful when this repository is used
    on its own. In that case, the bundled curriculum packages are the source
    of truth.
    """
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
    if items:
        return tuple(items)

    for package in load_packages():
        for chapter in package.get("chapters", []):
            items.append({
                "source_id": f"bundled:{package['slug']}-ch{chapter['chapter_number']}",
                "content_version": "features-2026-27",
                "subject": package["name"],
                "class_level": package.get("class_level", "Class X"),
                "chapter_number": chapter["chapter_number"],
                "chapter_name": chapter["title"],
                "text": chapter["summary"],
                "source_reference": chapter.get("source_reference", package.get("source_reference", "")),
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
    """Cloud chat-completion provider driven by whichever API key is present.

    Supported keys (checked in order) — all use OpenAI-compatible endpoints:

    - ``LEARNCRAFT_AI_CLOUD_URL`` + ``LEARNCRAFT_AI_CLOUD_KEY`` (custom)
    - ``OPENAI_API_KEY``        -> api.openai.com
    - ``GROQ_API_KEY``          -> api.groq.com
    - ``GEMINI_API_KEY``        -> generativelanguage.googleapis.com (OpenAI-compat)
    - ``OPENROUTER_API_KEY``    -> openrouter.ai
    """

    # key env var -> (default endpoint, default model)
    PRESETS = {
        "OPENAI_API_KEY": ("https://api.openai.com/v1/chat/completions", "gpt-4o-mini"),
        "GROQ_API_KEY": ("https://api.groq.com/openai/v1/chat/completions", "llama-3.3-70b-versatile"),
        "GEMINI_API_KEY": ("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", "gemini-2.0-flash"),
        "GOOGLE_API_KEY": ("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", "gemini-2.0-flash"),
        "OPENROUTER_API_KEY": ("https://openrouter.ai/api/v1/chat/completions", "openrouter/auto"),
    }

    name = "online"

    def __init__(self):
        self.url = ""
        self.api_key = ""
        self.model = ""
        self.label = ""
        # Custom endpoint override wins, otherwise pick the first preset key.
        custom_url = os.environ.get("LEARNCRAFT_AI_CLOUD_URL", "").strip()
        custom_key = os.environ.get("LEARNCRAFT_AI_CLOUD_KEY", "").strip()
        if custom_url and custom_key:
            self.url = custom_url
            self.api_key = custom_key
            self.model = os.environ.get("LEARNCRAFT_AI_CLOUD_MODEL", "").strip() or "configured-model"
            self.label = "custom"
            return
        for env_key, (endpoint, model) in self.PRESETS.items():
            value = os.environ.get(env_key, "").strip()
            if value:
                self.url = endpoint
                self.api_key = value
                self.model = os.environ.get("LEARNCRAFT_AI_CLOUD_MODEL", "").strip() or model
                self.label = env_key.removesuffix("_API_KEY").lower()
                return

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


_last_connectivity_check = 0.0
_internet_available: bool | None = None


def internet_available(max_age_seconds: int = 60) -> bool:
    """Cheap cached connectivity probe used by AUTO mode.

    A TCP connect to the cloud provider (or a public DNS fallback) answers
    'is there internet' far more reliably than ``navigator.onLine`` style
    guesses, and caching keeps it from stalling every request.
    """
    global _last_connectivity_check, _internet_available
    import time

    now = time.monotonic()
    if _internet_available is not None and (now - _last_connectivity_check) < max_age_seconds:
        return _internet_available

    import socket

    hosts: list[tuple[str, int]] = []
    cloud = CloudProvider()
    if cloud.available():
        from urllib.parse import urlparse

        parsed = urlparse(cloud.url)
        if parsed.hostname:
            hosts.append((parsed.hostname, parsed.port or 443))
    hosts.append(("8.8.8.8", 53))

    reachable = False
    for host, port in hosts:
        try:
            with socket.create_connection((host, port), timeout=2):
                reachable = True
                break
        except OSError:
            continue
    _internet_available = reachable
    _last_connectivity_check = now
    return reachable


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


class OllamaProvider(AIProvider):
    """Local LLM server (Ollama by default, LM Studio/llama.cpp compatible).

    Auto-detected at request time: when a local model server is running the
    tutor can answer ANY question fully offline, with no API key. Set
    ``LEARNCRAFT_AI_LOCAL_URL`` to point at an OpenAI-compatible server
    (e.g. http://localhost:1234/v1 for LM Studio); otherwise the Ollama
    native API on localhost:11434 is probed.
    """

    name = "local-llm"

    def __init__(self):
        self.base_url = os.environ.get("LEARNCRAFT_AI_LOCAL_URL", "").strip().rstrip("/")
        self.preferred_model = os.environ.get("LEARNCRAFT_AI_LOCAL_MODEL", "").strip()
        self.timeout = int(os.environ.get("LEARNCRAFT_AI_LOCAL_TIMEOUT", "120"))
        self._detected_model: str | None = None
        self._last_good: str = ""
        # model -> monotonic time it last failed; retried after a cooldown.
        self._failed_models: dict[str, float] = {}
        self._model_retry_ttl = int(os.environ.get("LEARNCRAFT_AI_LOCAL_MODEL_RETRY_TTL", "600"))
        self._detect_failed_at: float = 0.0
        self._detect_ttl = int(os.environ.get("LEARNCRAFT_AI_LOCAL_DETECT_TTL", "15"))

    @staticmethod
    def _usable(name: str) -> bool:
        lowered = (name or "").lower()
        return not any(tag in lowered for tag in ("embed", "bge", "nomic", "minilm", "guard", "rerank"))

    def _candidates(self) -> list[str]:
        """Ordered list of locally installed chat models worth trying.

        The preferred/last-working model comes first; the remaining installed
        models follow so a request can survive one model failing to load
        (for example a 30B model that does not fit in memory).
        """
        try:
            if self.base_url:
                return [self.preferred_model or "local"]
            with urlopen("http://localhost:11434/api/tags", timeout=2) as response:
                models = json.loads(response.read().decode("utf-8")).get("models") or []
            names = [m.get("name", "") for m in models if self._usable(m.get("name", ""))]
        except (OSError, URLError, TimeoutError, ValueError):
            return []
        if not names:
            return []
        # Skip models that recently failed to load (e.g. OOM) until their
        # retry cooldown expires.
        now = time.monotonic()
        self._failed_models = {m: t for m, t in self._failed_models.items()
                               if now - t < self._model_retry_ttl}
        healthy = [n for n in names if n not in self._failed_models]
        if not healthy:
            healthy = names  # everything failed recently; retry anyway
        names = healthy
        if self._last_good and self._last_good in names:
            head = [self._last_good]
        elif self.preferred_model:
            stem = self.preferred_model.split(":")[0]
            head = [n for n in names if n.split(":")[0] == stem]
        else:
            head = [names[0]]
        ordered = head + [n for n in names if n not in head]
        # Push very large models (typically >9 GB) to the back: they are the
        # ones most likely to OOM and stall the request while Ollama loads them.
        sizes = {m.get("name", ""): float(m.get("size") or 0) for m in models}
        big = [n for n in ordered if sizes.get(n, 0) > 9_000_000_000]
        return [n for n in ordered if n not in big] + big if big else ordered

    def _detect(self) -> str:
        if self._last_good:
            return self._last_good
        # Re-probe failed detections after a short cooldown so a model server
        # started after the Flask process boots is still picked up.
        if time.monotonic() - self._detect_failed_at < self._detect_ttl:
            return ""
        candidates = self._candidates()
        model = candidates[0] if candidates else ""
        if not model:
            self._detect_failed_at = time.monotonic()
        self._detected_model = model
        return model

    def available(self) -> bool:
        return bool(self._detect())

    def generate(self, messages: list[dict], context: AIContext) -> str:
        candidates = self._candidates()
        if not candidates:
            self._detect_failed_at = time.monotonic()
            raise RuntimeError("No local LLM server is reachable.")
        last_error = ""
        for model in candidates:
            answer = self._generate_with_model(model, messages)
            if answer is not None:
                self._last_good = model
                self._detected_model = model
                return answer
            last_error = f"model '{model}' failed to load or returned nothing"
            # OOM / load failure: remember so later requests skip it quickly.
            self._failed_models[model] = time.monotonic()
            self._last_good = ""
        self._detect_failed_at = time.monotonic()
        raise RuntimeError(f"Local LLM request failed: {last_error}")

    def _generate_with_model(self, model: str, messages: list[dict]) -> str | None:
        """Run one inference; returns None (not raises) so callers can fall back."""
        if self.base_url:
            payload = {"model": model, "messages": messages,
                       "temperature": float(os.environ.get("LEARNCRAFT_AI_TEMPERATURE", "0.2"))}
            url = self.base_url if self.base_url.endswith("/chat/completions") else f"{self.base_url}/chat/completions"
        else:
            payload = {"model": model, "messages": messages, "stream": False,
                       "options": {"num_ctx": int(os.environ.get("LEARNCRAFT_AI_LOCAL_NUM_CTX", "4096"))}}
            url = "http://localhost:11434/api/chat"
        request = Request(
            url, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (OSError, URLError, TimeoutError, ValueError) as exc:
            print(f"[ai_tutor] local model '{model}' error: {exc}", flush=True)
            return None
        if self.base_url:
            answer = ((result.get("choices") or [{}])[0].get("message") or {}).get("content", "")
        else:
            answer = (result.get("message") or {}).get("content", "")
        answer = strip_thinking((answer or "").strip())
        return answer or None


class AIService:
    def __init__(self):
        self.cloud = CloudProvider()
        self.local_llm = OllamaProvider()
        self.local = LocalProvider()

    def _mode(self) -> str:
        return os.environ.get("LEARNCRAFT_AI_MODE", "AUTO").upper()

    def _local_state(self) -> dict | None:
        for provider in (self.local_llm, self.local):
            if provider.available():
                info = {"provider": provider.name}
                model = getattr(provider, "_detected_model", "") or ""
                if model and provider is self.local_llm:
                    info["model"] = model
                return info
        return None

    def status(self) -> dict:
        mode = self._mode()
        if mode == "ONLINE":
            if self.cloud.available():
                return {"state": "online", "provider": self.cloud.name, "model": self.cloud.model}
            local_state = self._local_state()
            if local_state:
                return {"state": "offline", **local_state,
                        "reason": "No cloud API key configured for ONLINE mode — using local model."}
            return {"state": "offline", "provider": "built-in",
                    "reason": "No cloud API key configured for ONLINE mode."}
        if mode not in {"ONLINE", "AUTO"}:
            # OFFLINE mode: honour the explicit offline preference.
            local_state = self._local_state()
            if local_state:
                return {"state": "offline", **local_state}
            return {"state": "offline", "provider": "built-in",
                    "reason": "Using LearnCraft's built-in offline assistant."}

        # AUTO: cloud when internet + key exist, local LLM next, built-in last.
        if self.cloud.available() and internet_available():
            return {"state": "online", "provider": self.cloud.name, "model": self.cloud.model}
        local_state = self._local_state()
        if local_state:
            return {"state": "offline", **local_state}
        if self.cloud.available():
            return {"state": "offline", "provider": "built-in",
                    "reason": "Cloud AI key found but no internet connection — using built-in tutor."}
        return {"state": "offline", "provider": "built-in",
                "reason": "Using LearnCraft's built-in offline assistant."}

    def answer(self, question: str, context: AIContext, history: list[dict]) -> tuple[str, str]:
        retrieved = retrieve_context(context, question)
        system = build_system_prompt(context, retrieved)
        messages = [{"role": "system", "content": system}] + history[-8:] + [{"role": "user", "content": question}]
        mode = self._mode()
        if mode == "ONLINE":
            providers = [self.cloud, self.local_llm, self.local]
        elif mode == "AUTO":
            # Cloud first when the internet is reachable, then the local LLM
            # (Ollama / LM Studio), then a custom local command; the loop still
            # falls back automatically if any provider call fails.
            providers = ([self.cloud] if self.cloud.available() and internet_available() else []) \
                + [self.local_llm, self.local]
        else:
            providers = [self.local_llm, self.local]
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
        "app", "login", "log in", "sign in", "password", "forgot password",
        "sign out", "logout", "settings", "profile", "progress", "dashboard",
        "not saving", "app error", "app issue", "app problem", "not working",
    )

    if any(term in text for term in app_terms) or "app" in (context.mode or "").lower():
        if "password" in text or "forgot" in text:
            return (
                "To reset your LearnCraft password: open the login page, choose "
                "Forgot password, enter your registered email, and select Send "
                "reset code. A 6-digit one-time code valid for 10 minutes is "
                "generated for your account — in offline deployments it is "
                "written to the server log or provided by your teacher/admin. "
                "Enter the code with your new password and submit. Knowing only "
                "the email address is never enough to reset an account."
            )
        if "login" in text or "log in" in text or "sign in" in text:
            return (
                "For a LearnCraft login issue, first verify your email and password. "
                "If the password is incorrect, use Forgot password: request the "
                "6-digit code, then set a new password with that code. If the page "
                "still does not load, refresh the browser and try again with "
                "cookies enabled."
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
            "you took, and the message you saw. For example: login, password reset, "
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
        "You are LearnCraft's AI tutor — a friendly, knowledgeable assistant for students. "
        "Your specialty is CBSE Class IX/X school work, but you answer ANY question the user asks: "
        "general knowledge, science, coding, language, hobbies, current topics, or homework help. "
        "Never refuse a question just because it is outside the curriculum; answer it directly and completely. "
        "Use the retrieved curriculum evidence when it is relevant to the question; otherwise rely on your "
        "own knowledge and ignore it. Explain step by step, adapt the answer to the question type "
        "(definition, why/how, numerical, comparison, opinion), and keep it clear for a student. "
        "If you are genuinely unsure about a specific fact, say so briefly and still give your best answer. "
        f"Mode: {context.mode}. Subject: {context.subject}. Chapter: {context.chapter}. Topic: {context.topic}.\n"
        f"Retrieved curriculum evidence (may be empty — use only if relevant):\n{evidence or 'None.'}"
    )


def create_conversation(user_id: int, context: dict | None = None) -> str:
    from app.database.connection import _transaction

    conversation_id = str(uuid.uuid4())

    def work(connection):
        connection.execute(
            "INSERT INTO ai_conversations (conversation_id, user_id, context_json) VALUES (?, ?, ?)",
            (conversation_id, int(user_id), json.dumps(context or {})),
        )
    _transaction(work)
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
    from app.database.connection import _transaction

    if not get_conversation(user_id, conversation_id):
        raise PermissionError("Conversation not found.")

    def work(connection):
        # Re-check ownership inside the write transaction so a conversation
        # deleted/raced between the read above and this write cannot be written to.
        owner = connection.execute(
            "SELECT 1 FROM ai_conversations WHERE conversation_id = ? AND user_id = ?",
            (conversation_id, int(user_id)),
        ).fetchone()
        if not owner:
            raise PermissionError("Conversation not found.")
        connection.execute(
            "INSERT INTO ai_messages (message_id, conversation_id, user_id, role, content, context_reference, provider) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), conversation_id, int(user_id), role, content, json.dumps(context_reference or {}), provider),
        )
        connection.execute("UPDATE ai_conversations SET updated_at = CURRENT_TIMESTAMP WHERE conversation_id = ?", (conversation_id,))
    _transaction(work)


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
