"""Public-facing endpoints for customers to respond to consent requests."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from cms_shared.models.consent import ConsentRecord, ConsentResponseRequest

from consent_api.dependencies import get_consent_service
from consent_api.services.consent_service import ConsentService

logger = structlog.get_logger()

router = APIRouter()


@router.post("/consents/respond/{response_token}", response_model=ConsentRecord)
async def respond_to_consent(
    response_token: str,
    response_body: ConsentResponseRequest,
    request: Request,
    service: ConsentService = Depends(get_consent_service),
) -> ConsentRecord:
    """Process a customer's consent grant or denial.

    The ``ip_address`` and ``user_agent`` are captured automatically from the
    incoming request when not explicitly provided in the body.
    """
    if not response_body.ip_address:
        response_body.ip_address = request.client.host if request.client else None
    if not response_body.user_agent:
        response_body.user_agent = request.headers.get("user-agent")

    return await service.respond_to_consent(response_token, response_body)


_CONSENT_PAGE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Consent Request</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5; color: #333;
            display: flex; justify-content: center; align-items: center;
            min-height: 100vh; padding: 1rem;
        }}
        .card {{
            background: #fff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            max-width: 480px; width: 100%; padding: 2rem;
        }}
        h1 {{ font-size: 1.4rem; margin-bottom: 1rem; }}
        .consent-text {{
            background: #f9f9f9; border: 1px solid #e0e0e0; border-radius: 4px;
            padding: 1rem; margin-bottom: 1.5rem; line-height: 1.6;
        }}
        .actions {{ display: flex; gap: 1rem; }}
        button {{
            flex: 1; padding: 0.75rem 1rem; border: none; border-radius: 4px;
            font-size: 1rem; cursor: pointer; font-weight: 600;
        }}
        .grant {{ background: #22c55e; color: #fff; }}
        .grant:hover {{ background: #16a34a; }}
        .deny {{ background: #ef4444; color: #fff; }}
        .deny:hover {{ background: #dc2626; }}
        .result {{ text-align: center; padding: 2rem 0; }}
        .result.success {{ color: #16a34a; }}
        .result.denied {{ color: #dc2626; }}
        .result.error {{ color: #d97706; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>Consent Request</h1>
        <div class="consent-text">{consent_text}</div>
        <div class="actions" id="actions">
            <button class="grant" onclick="respond(true)">Grant Consent</button>
            <button class="deny" onclick="respond(false)">Deny Consent</button>
        </div>
        <div id="result" style="display:none;"></div>
    </div>
    <script>
        async function respond(granted) {{
            const actions = document.getElementById('actions');
            const result = document.getElementById('result');
            actions.style.display = 'none';
            try {{
                const res = await fetch(window.location.pathname, {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ granted: granted }})
                }});
                if (res.ok) {{
                    const cls = granted ? 'success' : 'denied';
                    const msg = granted ? 'Thank you! Your consent has been recorded.'
                                        : 'Your response has been recorded. Consent denied.';
                    result.className = 'result ' + cls;
                    result.innerHTML = '<h2>' + msg + '</h2>';
                }} else {{
                    const err = await res.json();
                    result.className = 'result error';
                    result.innerHTML = '<h2>Error</h2><p>' +
                        (err.detail || err.error?.message || 'Something went wrong') + '</p>';
                }}
            }} catch (e) {{
                result.className = 'result error';
                result.innerHTML = '<h2>Error</h2><p>Unable to submit your response. Please try again.</p>';
            }}
            result.style.display = 'block';
        }}
    </script>
</body>
</html>
"""


@router.get("/consents/respond/{response_token}", response_class=HTMLResponse)
async def consent_response_page(
    response_token: str,
    service: ConsentService = Depends(get_consent_service),
) -> HTMLResponse:
    """Render a simple HTML page for the customer to grant or deny consent."""
    try:
        consent = await service._repo.get_consent_by_token(response_token)
        consent_text = consent.consent_text
    except Exception:
        consent_text = (
            "We were unable to load the consent details. "
            "The link may have expired or is invalid."
        )

    html = _CONSENT_PAGE_HTML.format(consent_text=consent_text)
    return HTMLResponse(content=html)
