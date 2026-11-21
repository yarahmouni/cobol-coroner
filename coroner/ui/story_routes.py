"""Routes of the guided story: the step pages and the HTML fragments of its three actions.

The fragment routes (gate check, Run it yourself, job polling) call the route functions of
coroner/ui/app.py and render their answer as HTML. They validate nothing, limit nothing, cache
nothing and replay nothing themselves, so every limit of the API routes applies unchanged.

Fragment answers always use status 200: htmx does not swap a 4xx or 5xx response into the page,
and the visitor must see the message in the live region. The real status is shown in the text.
"""
import importlib
import json
from typing import Optional

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from coroner.ui import story

router = APIRouter()

VARY = {"Vary": "HX-Request, HX-History-Restore-Request"}

RUN_NOT_ACCEPTED_MESSAGE = (
    "The audit was not started. Check that the seed and the number of batches are whole numbers "
    "within the limits of the form."
)


def _ui():
    """The route functions and settings of coroner/ui/app.py, looked up at call time."""
    return importlib.import_module("coroner.ui.app")


def _is_fragment_request(request: Request) -> bool:
    """htmx asks for a fragment; when it restores history it needs the full page."""
    return (
        request.headers.get("HX-Request") == "true"
        and request.headers.get("HX-History-Restore-Request") != "true"
    )


def _render_step(request: Request, step: int, view: Optional[str]):
    ui = _ui()
    fragment = _is_fragment_request(request)
    context = story.build_step(ui.get_base_dir(), step, view)
    context["is_fragment"] = fragment
    return ui.templates.TemplateResponse(
        request=request,
        name="story_fragment.html" if fragment else "story.html",
        context=context,
        headers=VARY,
    )


@router.get("/story", response_class=HTMLResponse)
async def story_start(request: Request, view: Optional[str] = None):
    """The story at step 1."""
    return _render_step(request, 1, view)


@router.get("/story/step/{step}", response_class=HTMLResponse)
async def story_step(request: Request, step: str, view: Optional[str] = None):
    """One step: the full page, or only the step when htmx asks. A step outside 1 to 8 goes to step 1."""
    number = story.parse_step(step)
    if number is None:
        return RedirectResponse(story.step_url(1, view), status_code=302, headers=VARY)
    return _render_step(request, number, view)


def _json_of(response) -> dict:
    """The JSON body of a JSONResponse returned by a route function."""
    body = json.loads(response.body)
    return body if isinstance(body, dict) else {}


def _render(request: Request, name: str, **context):
    return _ui().templates.TemplateResponse(request=request, name=name, context=context)


def _alert(request: Request, message: str, **context):
    return _render(request, "story_alert.html", message=message, **context)


@router.post("/story/gate-check", response_class=HTMLResponse)
async def story_gate_check(request: Request, run_id: str = Form(""), view: Optional[str] = Form(None)):
    """Fragment for the gate check: the answer of POST /api/gate-check as a badge or an alert."""
    ui = _ui()
    view = story.normalize_view(view)
    retry = {"retry_action": "gate", "run_id": run_id, "view": view}
    try:
        response = await ui.gate_check(request, run_id=run_id)
    except HTTPException as e:
        return _alert(request, str(e.detail))
    body = _json_of(response)
    status_code = response.status_code
    if status_code == 200:
        message = body.get("message")
        if body.get("status") == "allowed":
            kind = "alive"
        elif message == ui.GATE_MESSAGE_INVALID:
            kind = "invalid"
        else:
            kind = "zombie"
        return _render(
            request, "story_gate_result.html",
            kind=kind, heading=message, exit_code=body.get("exit_code"),
        )
    message = body.get("message") or body.get("detail") or f"The gate check failed (status {status_code})"
    if status_code in (429, 500, 503):
        return _alert(request, str(message), retry_after=response.headers.get("Retry-After"), **retry)
    return _alert(request, str(message))


@router.post("/story/run", response_class=HTMLResponse)
async def story_run(
    request: Request,
    port: str = Form(""),
    seed: str = Form(""),
    cases: str = Form(""),
    view: Optional[str] = Form(None),
):
    """Fragment for Run it yourself: starts an audit of the story trap through POST /api/run."""
    ui = _ui()
    view = story.normalize_view(view)
    response = await ui.run_audit(request, sample=story.STORY_TRAP_ID, port=port, seed=seed, cases=cases)
    body = _json_of(response)
    status_code = response.status_code
    if status_code == 202:
        return _render(request, "story_job.html", job_id=body.get("job_id"), job_status="queued", view=view)
    if status_code == 200 and body.get("run_id"):
        try:
            result = story.audit_result(ui.get_base_dir(), body["run_id"])
        except story.StoryDataError as e:
            return _alert(request, str(e))
        return _render(request, "story_run_result.html", result=result, cached=True)
    retry = {"retry_action": "run", "port": port, "seed": seed, "cases": cases, "view": view}
    if status_code == 422:
        # The API detail is the raw validation report of the model; the visitor gets a plain sentence.
        return _alert(request, RUN_NOT_ACCEPTED_MESSAGE)
    message = body.get("detail") or f"The audit was not started (status {status_code})"
    if status_code == 429:
        return _alert(request, str(message), retry_after=response.headers.get("Retry-After"), **retry)
    return _alert(request, str(message))


@router.get("/story/job/{job_id}", response_class=HTMLResponse)
async def story_job(request: Request, job_id: str, view: Optional[str] = None):
    """Fragment polled every 2 seconds: the job status of GET /api/job/<id>/status as HTML."""
    ui = _ui()
    view = story.normalize_view(view)
    response = await ui.job_status(job_id)
    body = _json_of(response)
    if response.status_code != 200:
        return _alert(request, str(body.get("detail") or f"The job status failed (status {response.status_code})"))
    status = body.get("status")
    if status in ("queued", "running"):
        return _render(request, "story_job.html", job_id=job_id, job_status=status, view=view)
    if status == "error":
        return _alert(request, f"The audit stopped: {body.get('reason') or 'no reason recorded'}")
    if status == "done" and body.get("run_id"):
        try:
            result = story.audit_result(ui.get_base_dir(), body["run_id"])
        except story.StoryDataError as e:
            return _alert(request, str(e))
        return _render(request, "story_run_result.html", result=result, cached=False)
    return _alert(request, f"The job has an unknown status: {status}")
