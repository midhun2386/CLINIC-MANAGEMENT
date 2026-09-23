"""
AI-powered chatbot using Anthropic Claude with tool-calling.

Replaces the old rule-based parser with an LLM that can answer open-ended
questions against patients + treatment entries via defined tool functions.
Falls back gracefully if no API key is configured.
"""

import json
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, g, current_app

from .models import db, Patient, TreatmentEntry
from .auth import token_required, _log

chatbot_bp = Blueprint('chatbot', __name__, url_prefix='/api/chatbot')


# ---------------------------------------------------------------------------
# Tool functions — the LLM calls these to query the database
# ---------------------------------------------------------------------------

def tool_search_patients(name=None, gender=None, phone=None):
    """Search patients by name, gender, and/or phone."""
    query = Patient.query

    if name:
        query = query.filter(Patient.name.ilike(f'%{name}%'))
    if gender:
        query = query.filter(Patient.gender.ilike(f'%{gender}%'))
    if phone:
        query = query.filter(Patient.phone.ilike(f'%{phone}%'))

    patients = query.order_by(Patient.name.asc()).limit(20).all()
    return [
        {
            'id': p.id,
            'name': p.name,
            'dob': p.dob.isoformat() if p.dob else None,
            'gender': p.gender,
            'phone': p.phone,
            'email': p.email,
            'address': p.address,
        }
        for p in patients
    ]


def tool_search_treatments(patient_name=None, treatment_name=None,
                            date_from=None, date_to=None, payment_method=None):
    """Search treatment entries with optional filters."""
    query = TreatmentEntry.query

    if patient_name:
        # Join with Patient to filter by name
        query = query.join(Patient).filter(Patient.name.ilike(f'%{patient_name}%'))

    if treatment_name:
        query = query.filter(TreatmentEntry.treatment_name.ilike(f'%{treatment_name}%'))

    if date_from:
        try:
            d = datetime.strptime(date_from, '%Y-%m-%d').date()
            query = query.filter(TreatmentEntry.date_of_treatment >= d)
        except ValueError:
            pass

    if date_to:
        try:
            d = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(TreatmentEntry.date_of_treatment <= d)
        except ValueError:
            pass

    if payment_method:
        query = query.filter(TreatmentEntry.payment_method.ilike(f'%{payment_method}%'))

    entries = query.order_by(TreatmentEntry.date_of_treatment.desc()).limit(30).all()

    # Enrich with patient names
    pid_set = {e.patient_id for e in entries}
    p_map = {}
    if pid_set:
        p_map = {p.id: p.name for p in Patient.query.filter(Patient.id.in_(pid_set)).all()}

    return [
        {
            'id': e.id,
            'patient_name': p_map.get(e.patient_id, 'Unknown'),
            'date_of_treatment': e.date_of_treatment.isoformat() if e.date_of_treatment else None,
            'consultation_number': e.consultation_number,
            'treatment_name': e.treatment_name,
            'medicine': e.medicine,
            'remark': e.remark,
            'next_consultation': e.next_consultation.isoformat() if e.next_consultation else None,
            'payment': e.payment,
            'payment_method': e.payment_method,
        }
        for e in entries
    ]


def tool_get_upcoming_consultations(date_from=None, date_to=None):
    """Get treatment entries with upcoming (future) next_consultation dates."""
    today = datetime.utcnow().date()

    query = TreatmentEntry.query.filter(TreatmentEntry.next_consultation.isnot(None))

    if date_from:
        try:
            d = datetime.strptime(date_from, '%Y-%m-%d').date()
            query = query.filter(TreatmentEntry.next_consultation >= d)
        except ValueError:
            query = query.filter(TreatmentEntry.next_consultation >= today)
    else:
        query = query.filter(TreatmentEntry.next_consultation >= today)

    if date_to:
        try:
            d = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(TreatmentEntry.next_consultation <= d)
        except ValueError:
            pass

    entries = query.order_by(TreatmentEntry.next_consultation.asc()).limit(30).all()

    pid_set = {e.patient_id for e in entries}
    p_map = {}
    if pid_set:
        p_map = {p.id: p.name for p in Patient.query.filter(Patient.id.in_(pid_set)).all()}

    return [
        {
            'patient_name': p_map.get(e.patient_id, 'Unknown'),
            'patient_id': e.patient_id,
            'next_consultation': e.next_consultation.isoformat(),
            'treatment_name': e.treatment_name,
            'last_visit': e.date_of_treatment.isoformat() if e.date_of_treatment else None,
        }
        for e in entries
    ]


def tool_get_payment_totals(date_from=None, date_to=None, group_by=None):
    """Get payment totals, optionally grouped by payment_method."""
    query = TreatmentEntry.query.filter(TreatmentEntry.payment.isnot(None))

    if date_from:
        try:
            d = datetime.strptime(date_from, '%Y-%m-%d').date()
            query = query.filter(TreatmentEntry.date_of_treatment >= d)
        except ValueError:
            pass

    if date_to:
        try:
            d = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(TreatmentEntry.date_of_treatment <= d)
        except ValueError:
            pass

    entries = query.all()

    if group_by == 'payment_method':
        groups = {}
        for e in entries:
            method = e.payment_method or 'Unknown'
            if method not in groups:
                groups[method] = {'total': 0, 'count': 0}
            groups[method]['total'] += e.payment or 0
            groups[method]['count'] += 1
        total = sum(g['total'] for g in groups.values())
        return {
            'grand_total': total,
            'by_method': groups,
            'entry_count': len(entries),
        }

    total = sum(e.payment or 0 for e in entries)
    return {
        'grand_total': total,
        'entry_count': len(entries),
    }


# ---------------------------------------------------------------------------
# Tool definitions for Claude
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "name": "search_patients",
        "description": "Search for patients by name, gender, and/or phone number. Returns patient demographics.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Patient name to search (partial match)"},
                "gender": {"type": "string", "description": "Gender filter (Male/Female/Other)"},
                "phone": {"type": "string", "description": "Phone number to search (partial match)"},
            },
            "required": [],
        },
    },
    {
        "name": "search_treatments",
        "description": "Search treatment entries by patient name, treatment name, date range, or payment method. Returns treatment details including medicine, payment, and next consultation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "patient_name": {"type": "string", "description": "Patient name to filter by"},
                "treatment_name": {"type": "string", "description": "Treatment/problem name to search"},
                "date_from": {"type": "string", "description": "Start date filter (YYYY-MM-DD)"},
                "date_to": {"type": "string", "description": "End date filter (YYYY-MM-DD)"},
                "payment_method": {"type": "string", "description": "Payment method filter (Cash/Card/UPI/Insurance)"},
            },
            "required": [],
        },
    },
    {
        "name": "get_upcoming_consultations",
        "description": "Get patients with scheduled upcoming follow-up consultations, optionally filtered by date range.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date_from": {"type": "string", "description": "Start date (YYYY-MM-DD), defaults to today"},
                "date_to": {"type": "string", "description": "End date (YYYY-MM-DD)"},
            },
            "required": [],
        },
    },
    {
        "name": "get_payment_totals",
        "description": "Calculate total payment collections, optionally filtered by date range and grouped by payment method.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date_from": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                "date_to": {"type": "string", "description": "End date (YYYY-MM-DD)"},
                "group_by": {"type": "string", "description": "Group results by 'payment_method' to see breakdowns"},
            },
            "required": [],
        },
    },
]

TOOL_FUNCTIONS = {
    "search_patients": tool_search_patients,
    "search_treatments": tool_search_treatments,
    "get_upcoming_consultations": tool_get_upcoming_consultations,
    "get_payment_totals": tool_get_payment_totals,
}

SYSTEM_PROMPT = """You are a helpful clinic EMR assistant. You have access to the clinic's patient and treatment data through the provided tools. 

When answering questions:
- Use the tools to look up real data before answering
- Be concise and clear in your responses
- Format numbers nicely (e.g., currency amounts)
- If no results are found, say so clearly
- Never make up patient data — only report what the tools return
- When listing patients or treatments, include relevant details like dates and names
- For payment queries, always mention the total and time period

Today's date is {today}."""


def _call_claude(user_message: str) -> str:
    """Send message to Claude with tool definitions, process tool calls, return answer."""
    try:
        import anthropic
    except ImportError:
        return "The AI chatbot requires the 'anthropic' package. Please install it with: pip install anthropic"

    api_key = current_app.config.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        return _fallback_response(user_message)

    client = anthropic.Anthropic(api_key=api_key)
    today = datetime.utcnow().strftime('%Y-%m-%d')

    messages = [{"role": "user", "content": user_message}]

    # Initial call with tools
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=SYSTEM_PROMPT.format(today=today),
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )
    except Exception as e:
        return f"Sorry, I couldn't process your question. Error: {str(e)}"

    # Process tool calls in a loop
    max_iterations = 5
    iteration = 0
    while response.stop_reason == "tool_use" and iteration < max_iterations:
        iteration += 1

        # Extract tool use blocks
        tool_results = []
        assistant_content = response.content

        for block in assistant_content:
            if block.type == "tool_use":
                tool_name = block.name
                tool_input = block.input
                tool_id = block.id

                # Execute the tool
                func = TOOL_FUNCTIONS.get(tool_name)
                if func:
                    try:
                        result = func(**tool_input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": json.dumps(result, default=str),
                        })
                    except Exception as e:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": json.dumps({"error": str(e)}),
                            "is_error": True,
                        })
                else:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": json.dumps({"error": f"Unknown tool: {tool_name}"}),
                        "is_error": True,
                    })

        # Continue conversation with tool results
        messages.append({"role": "assistant", "content": assistant_content})
        messages.append({"role": "user", "content": tool_results})

        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                system=SYSTEM_PROMPT.format(today=today),
                tools=TOOL_DEFINITIONS,
                messages=messages,
            )
        except Exception as e:
            return f"Sorry, I encountered an error while processing: {str(e)}"

    # Extract final text response
    text_parts = []
    for block in response.content:
        if hasattr(block, 'text'):
            text_parts.append(block.text)

    return '\n'.join(text_parts) if text_parts else "I processed your request but couldn't generate a text response."


def _call_gemini(user_message: str, api_key: str) -> str:
    """Send message to Google Gemini using google-genai with tool functions."""
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return "The Google GenAI library is not installed. Please run: pip install google-genai"

    # Define tools with type annotations so Gemini recognizes them properly
    def search_patients(name: str = None, gender: str = None, phone: str = None) -> list:
        """Search patients in clinic database by name, gender, or phone."""
        return tool_search_patients(name=name, gender=gender, phone=phone)

    def search_treatments(patient_name: str = None, treatment_name: str = None,
                          date_from: str = None, date_to: str = None, payment_method: str = None) -> list:
        """Search treatment entries with optional filters."""
        return tool_search_treatments(patient_name=patient_name, treatment_name=treatment_name,
                                      date_from=date_from, date_to=date_to, payment_method=payment_method)

    def get_upcoming_consultations(date_from: str = None, date_to: str = None) -> list:
        """Get treatment entries with scheduled upcoming next_consultation dates."""
        return tool_get_upcoming_consultations(date_from=date_from, date_to=date_to)

    def get_payment_totals(date_from: str = None, date_to: str = None, group_by: str = None) -> dict:
        """Get payment totals, optionally grouped by payment_method."""
        return tool_get_payment_totals(date_from=date_from, date_to=date_to, group_by=group_by)

    today = datetime.utcnow().strftime('%Y-%m-%d')
    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        tools=[search_patients, search_treatments, get_upcoming_consultations, get_payment_totals],
        system_instruction=SYSTEM_PROMPT.format(today=today),
        temperature=0.2,
    )

    candidate_models = ['gemini-3.6-flash', 'gemini-3.5-flash', 'gemini-3.5-flash-lite']
    last_err = None

    for model_name in candidate_models:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=user_message,
                config=config,
            )
            if response and response.text:
                return response.text
        except Exception as e:
            last_err = e
            err_str = str(e)
            if 'RESOURCE_EXHAUSTED' in err_str or '429' in err_str:
                continue
            if 'UNAVAILABLE' in err_str or '503' in err_str:
                continue
            continue

    if last_err:
        err_msg = str(last_err)
        if 'RESOURCE_EXHAUSTED' in err_msg or '429' in err_msg:
            return "Gemini API free tier rate limit reached (5 requests/minute). Please wait a few seconds and try again."
        return f"Unable to reach Gemini: {err_msg[:200]}"

    return _fallback_response(user_message)


def _call_llm(user_message: str) -> str:
    """Route to Gemini or Claude depending on configured API keys."""
    gemini_key = current_app.config.get('GEMINI_API_KEY', '')
    anthropic_key = current_app.config.get('ANTHROPIC_API_KEY', '')

    # Detect if anthropic_key was mistakenly set with a Gemini key (starts with AQ.)
    if anthropic_key and anthropic_key.startswith('AQ.') and not gemini_key:
        gemini_key = anthropic_key
        anthropic_key = ''

    if gemini_key:
        return _call_gemini(user_message, gemini_key)
    elif anthropic_key:
        return _call_claude(user_message)
    else:
        return _fallback_response(user_message)


def _fallback_response(user_message: str) -> str:
    """Simple keyword-based fallback when no API key is configured."""
    text_lower = user_message.lower().strip()

    if any(w in text_lower for w in ['help', 'what can you do', 'commands']):
        return (
            "🤖 I'm the EMR Assistant! I can help you find patient information.\n\n"
            "Try asking things like:\n"
            "• \"Find patient John Smith\"\n"
            "• \"Who has a follow-up next week?\"\n"
            "• \"How much did we collect this month?\"\n"
            "• \"Show me treatments for diabetes\"\n\n"
            "💡 **Note:** For full AI-powered Q&A, configure your Gemini or Anthropic API key in .env."
        )

    # Basic patient search fallback
    patients = Patient.query.filter(Patient.name.ilike(f'%{user_message}%')).limit(10).all()
    if patients:
        lines = [f"Found {len(patients)} patient(s) matching \"{user_message}\":\n"]
        for p in patients:
            lines.append(f"• **{p.name}** — DOB: {p.dob.isoformat() if p.dob else 'N/A'}, Phone: {p.phone or 'N/A'}")
            entries = TreatmentEntry.query.filter_by(patient_id=p.id).order_by(TreatmentEntry.date_of_treatment.desc()).limit(3).all()
            for e in entries:
                lines.append(f"  └ {e.date_of_treatment.isoformat() if e.date_of_treatment else '?'}: {e.treatment_name or 'No treatment name'}")
        lines.append("\n💡 Configure your Gemini API key in .env for full AI-powered Q&A.")
        return '\n'.join(lines)

    return (
        f"No results found for \"{user_message}\".\n\n"
        "Try searching by patient name, or ask about treatments, payments, or upcoming consultations.\n"
        "💡 Configure your Gemini API key in .env for full AI-powered Q&A."
    )


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@chatbot_bp.route('', methods=['POST'])
@token_required
def chat():
    body = request.get_json(silent=True) or {}
    user_message = body.get('message', '').strip()

    if not user_message:
        return jsonify({'error': 'Message is required'}), 400

    # Use LLM (Gemini or Claude) if API key is available, otherwise fallback
    answer = _call_llm(user_message)

    _log(g.current_user.id, 'CHATBOT_QUERY',
         f'q="{user_message[:100]}"', request.remote_addr)

    return jsonify({
        'message': answer,
        'patients': [],
        'records': [],
    })
