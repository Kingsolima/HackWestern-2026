"""RFQ flow (ARCHITECTURE §3 #10–11). Owner 2.

Gemini drafts the RFQ (numbers passed in, never computed). TinyBrowser + Playwright fills one
supplier's quote form and STOPS before submit. Submission requires Auth0 manager approval.
One honest identity, no fake personas.
"""


async def draft_rfq(design_id: str) -> str:
    raise NotImplementedError
