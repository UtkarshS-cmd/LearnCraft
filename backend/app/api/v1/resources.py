"""External learning resource catalog API (offline metadata, link-out launches)."""

from __future__ import annotations

from flask import Blueprint, jsonify, redirect, request, session

from app.services.external_providers import list_providers
from app.services.external_resources import (
    create_resource,
    delete_resource,
    ensure_external_resource_seed,
    get_resource,
    list_resources,
    log_activity,
    obsidian_uri,
    remove_bookmark,
    resources_for_context,
    set_bookmark,
    update_resource,
    user_activity,
    user_bookmarks,
)

bp = Blueprint("resources_v1", __name__, url_prefix="/api/v1/resources")


def _user_id():
    return session.get("user_id")


def _teacher():
    from app.main import current_user
    user = current_user()
    if user and user.get("role") in {"TEACHER", "ADMIN"}:
        return user
    return None


def _require_auth():
    if not _user_id():
        return jsonify({"success": False, "message": "Authentication required.", "code": "AUTH_REQUIRED"}), 401
    return None


@bp.get("/providers")
def providers():
    err = _require_auth()
    if err:
        return err
    return jsonify({"items": list_providers()})


@bp.get("")
def catalog():
    err = _require_auth()
    if err:
        return err
    args = request.args
    verified = args.get("verified")
    items = list_resources({
        "provider": args.get("provider") or "",
        "subject": args.get("subject") or "",
        "class_level": args.get("class_level") or "",
        "chapter": args.get("chapter") or "",
        "resource_type": args.get("resource_type") or "",
        "difficulty": args.get("difficulty") or "",
        "language": args.get("language") or "",
        "concept_id": args.get("concept_id") or "",
        "q": args.get("q") or "",
        **({"verified": verified in ("1", "true", "yes")} if verified is not None else {}),
    })
    return jsonify({"items": items, "count": len(items), "offline": True})



@bp.get("/context")
def context():
    err = _require_auth()
    if err:
        return err
    args = request.args
    return jsonify({"items": resources_for_context(
        args.get("subject") or "", args.get("chapter") or "", args.get("topic") or "",
        args.get("concept_id") or "", args.get("limit", type=int) or 12)})


@bp.get("/<resource_id>")
def detail(resource_id: str):
    err = _require_auth()
    if err:
        return err
    item = get_resource(resource_id)
    if not item or not item.get("enabled"):
        return jsonify({"success": False, "message": "Resource not found."}), 404
    vault = (request.args.get("vault") or "").strip()
    note = request.args.get("note") or ""
    if item["provider"] == "obsidian":
        # Deep links require a user-configured vault; otherwise be honest and offer the site.
        item = {**item, "obsidian_uri": obsidian_uri(vault, note or item.get("topic") or item.get("title")) if vault else "",
                "deep_link_supported": bool(vault)}
    return jsonify(item)


@bp.get("/<resource_id>/open")
def open_resource(resource_id: str):
    err = _require_auth()
    if err:
        return err
    item = get_resource(resource_id)
    if not item or not item.get("enabled"):
        return jsonify({"success": False, "message": "Resource not found."}), 404
    log_activity(_user_id(), resource_id, "opened", request.args.get("concept_id") or "")
    if item["provider"] == "obsidian":
        vault = (request.args.get("vault") or "").strip()
        target = obsidian_uri(vault, request.args.get("note") or "") if vault else (item["url"] or "https://obsidian.md/")
        if request.args.get("format") == "json":
            return jsonify({"url": target, "provider": "obsidian", "deep_link": bool(vault)})
        return redirect(target)
    if request.args.get("format") == "json":
        return jsonify({"url": item["url"], "provider": item["provider"]})
    return redirect(item["url"])


@bp.post("/<resource_id>/complete")
def complete(resource_id: str):
    err = _require_auth()
    if err:
        return err
    if not get_resource(resource_id):
        return jsonify({"success": False, "message": "Resource not found."}), 404
    return jsonify({"success": True, "event": log_activity(
        _user_id(), resource_id, "completed", (request.get_json(silent=True) or {}).get("concept_id") or "")})


@bp.get("/bookmarks/mine")
def my_bookmarks():
    err = _require_auth()
    if err:
        return err
    return jsonify({"items": user_bookmarks(_user_id())})


@bp.post("/<resource_id>/bookmark")
def bookmark(resource_id: str):
    err = _require_auth()
    if err:
        return err
    payload = request.get_json(silent=True) or {}
    try:
        return jsonify({"success": True, "item": set_bookmark(
            _user_id(), resource_id, payload.get("status", "IN_PROGRESS"), bool(payload.get("pinned")))})
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400 if "not found" in str(exc).lower() else 400


@bp.delete("/<resource_id>/bookmark")
def unbookmark(resource_id: str):
    err = _require_auth()
    if err:
        return err
    return jsonify({"success": True, "removed": remove_bookmark(_user_id(), resource_id)})


@bp.get("/activity/mine")
def my_activity():
    err = _require_auth()
    if err:
        return err
    return jsonify({"items": user_activity(_user_id(), request.args.get("limit", type=int) or 50)})


@bp.post("")
def teacher_create():
    teacher = _teacher()
    if not teacher:
        return jsonify({"success": False, "message": "Teacher access required.", "code": "FORBIDDEN"}), 403
    try:
        item = create_resource(request.get_json(silent=True) or {}, created_by=int(teacher["id"]))
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc), "code": "VALIDATION_ERROR"}), 400
    log_activity(int(teacher["id"]), item["id"], "created")
    ensure_external_resource_seed()
    return jsonify({"success": True, "item": item}), 201


@bp.put("/<resource_id>")
def teacher_update(resource_id: str):
    if not _teacher():
        return jsonify({"success": False, "message": "Teacher access required.", "code": "FORBIDDEN"}), 403
    try:
        item = update_resource(resource_id, request.get_json(silent=True) or {})
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc), "code": "VALIDATION_ERROR"}), 400
    if not item:
        return jsonify({"success": False, "message": "Resource not found."}), 404
    return jsonify({"success": True, "item": item})


@bp.delete("/<resource_id>")
def teacher_delete(resource_id: str):
    if not _teacher():
        return jsonify({"success": False, "message": "Teacher access required.", "code": "FORBIDDEN"}), 403
    if not delete_resource(resource_id):
        return jsonify({"success": False, "message": "Resource not found."}), 404
    return jsonify({"success": True})


@bp.post("/<resource_id>/verify")
def teacher_verify(resource_id: str):
    if not _teacher():
        return jsonify({"success": False, "message": "Teacher access required.", "code": "FORBIDDEN"}), 403
    item = update_resource(resource_id, {"verified": True, "enabled": True})
    if not item:
        return jsonify({"success": False, "message": "Resource not found."}), 404
    return jsonify({"success": True, "item": item})


@bp.get("/adapters/status")
def adapters_status():
    err = _require_auth()
    if err:
        return err
    from app.services.provider_adapters import NotionAdapter
    return jsonify({"items": [
        {"provider": "notion", **NotionAdapter().status()},
        {"provider": "obsidian", "level": 1, "configured": True,
         "message": "Local-first obsidian:// URIs; configure vault in Settings"},
        {"provider": "anki", "level": 1, "configured": True,
         "message": "Link-out + TSV export hook (no account needed)"},
        {"provider": "github", "level": 1, "configured": True,
         "message": "Link-out + project URL validation"},
    ]})


@bp.post("/anki/export")
def anki_export():
    err = _require_auth()
    if err:
        return err
    from app.services.provider_adapters import flashcards_to_tsv
    from flask import Response
    payload = request.get_json(silent=True) or {}
    tsv = flashcards_to_tsv(payload.get("cards") or [])
    log_activity(_user_id(), payload.get("resource_id") or "anki-export", "created")
    return Response(tsv, mimetype="text/tab-separated-values",
                    headers={"Content-Disposition": "attachment; filename=learncraft-flashcards.tsv"})


@bp.post("/github/validate")
def github_validate():
    """Validate + parse a GitHub repository link (seam for future project linking)."""
    err = _require_auth()
    if err:
        return err
    from app.services.provider_adapters import parse_github_repo
    payload = request.get_json(silent=True) or {}
    try:
        repo = parse_github_repo(str(payload.get("url", "")))
    except ValueError as exc:
        return jsonify({"success": False, "valid": False, "message": str(exc)}), 400
    return jsonify({"success": True, "valid": True, **repo})


@bp.get("/search")
def search():
    err = _require_auth()
    if err:
        return err
    args = request.args
    items = list_resources({
        "q": args.get("q") or "", "provider": args.get("provider") or "",
        "subject": args.get("subject") or "", "class_level": args.get("class_level") or "",
        "chapter": args.get("chapter") or "", "resource_type": args.get("resource_type") or "",
        "language": args.get("language") or "",
    })
    return jsonify({"items": items, "count": len(items), "query": args.get("q") or ""})
