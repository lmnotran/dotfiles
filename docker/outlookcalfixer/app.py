
from flask import Flask, request, Response
import os
import re
import requests

app = Flask(__name__)

# Europe/Copenhagen VTIMEZONE block (CET/CEST). RFC5545-compatible.
VTIMEZONE_EUROPE_COPENHAGEN = """BEGIN:VTIMEZONE
TZID:Europe/Copenhagen
X-LIC-LOCATION:Europe/Copenhagen
BEGIN:STANDARD
TZOFFSETFROM:+0200
TZOFFSETTO:+0100
TZNAME:CET
DTSTART:19701025T030000
RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU
END:STANDARD
BEGIN:DAYLIGHT
TZOFFSETFROM:+0100
TZOFFSETTO:+0200
TZNAME:CEST
DTSTART:19700329T020000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU
END:DAYLIGHT
END:VTIMEZONE
"""

MS_TZ_TO_IANA = {
    # Extend this map if you discover other Microsoft TZIDs.
    'W. Europe Standard Time': 'Europe/Copenhagen',
    'Romance Standard Time': 'Europe/Copenhagen',
    'GMT Standard Time': 'Europe/London',
}

def insert_vtimezone_after_header(ics: str, vtz: str) -> str:
    """
    Insert a VTIMEZONE block *after* VCALENDAR properties (VERSION/PRODID/etc.)
    and *before* the first component (e.g., VTIMEZONE/VEVENT). This keeps Google happy.
    """
    # Find 'BEGIN:VCALENDAR'
    m = re.search(r'BEGIN:VCALENDAR\r?\n', ics)
    if not m:
        # If the structure is malformed, just append vtz before END:VCALENDAR if present
        end = re.search(r'END:VCALENDAR', ics)
        if end:
            return ics.replace('END:VCALENDAR', vtz + '\r\nEND:VCALENDAR', 1)
        return ics + '\r\n' + vtz + '\r\n'

    start = m.end()
    # Identify the first component start after the header block
    comp = re.search(r'(?m)^BEGIN:(?!VCALENDAR)\w+', ics[start:])
    if not comp:
        # No components yet; put VTIMEZONE just before END:VCALENDAR
        end = re.search(r'END:VCALENDAR', ics[start:])
        if end:
            insert_at = start + end.start()
            return ics[:insert_at] + vtz + '\r\n' + ics[insert_at:]
        else:
            return ics + '\r\n' + vtz + '\r\n'

    comp_start = start + comp.start()
    header = ics[:comp_start]
    components = ics[comp_start:]
    return header + vtz + '\r\n' + components

def rewrite_ics(ics_text: str) -> str:
    """
    Rewrites a Microsoft/Exchange ICS to fix missing/unknown TZIDs by mapping them
    to IANA tzids (e.g., W. Europe Standard Time -> Europe/Copenhagen) and injects
    a VTIMEZONE block for Europe/Copenhagen if it's not present.
    Ensures VCALENDAR property ordering: properties first, then components.
    """
    # Normalize to LF for manipulation
    ics = ics_text.replace('\\r\\n', '\\n').replace('\\r', '\\n')

    # Replace TZIDs in attributes (TZID="W. Europe Standard Time" or TZID=W. Europe Standard Time)
    for ms_tz, iana in MS_TZ_TO_IANA.items():
        esc = re.escape(ms_tz)
        pattern = re.compile(rf'TZID=(?:"|)?{esc}(?:"|)?')
        ics = pattern.sub(f'TZID={iana}', ics)

    # If any RECURRENCE-ID params include the Microsoft TZID inside quotes, they are handled by the same pattern.

    # Ensure a Europe/Copenhagen VTIMEZONE exists
    has_cph = re.search(r'BEGIN:VTIMEZONE[\\s\\S]*?TZID:Europe/Copenhagen[\\s\\S]*?END:VTIMEZONE', ics) is not None
    if not has_cph:
        # Convert back to CRLF temporarily to make downstream insertions use CRLF consistently
        ics = ics.replace('\\n', '\\r\\n')
        ics = insert_vtimezone_after_header(ics, VTIMEZONE_EUROPE_COPENHAGEN)
        # Normalize back to LF for any further regex work
        ics = ics.replace('\\r\\n', '\\n')

    # Normalize calendar-level timezone hint (optional)
    # If present, rewrite to a consistent IANA TZ for better hints in some clients.
    if re.search(r'(?m)^X-WR-TIMEZONE:.*', ics):
        ics = re.sub(r'(?m)^X-WR-TIMEZONE:.*', 'X-WR-TIMEZONE:Europe/Copenhagen', ics)
    else:
        # Insert X-WR-TIMEZONE in the header area for clarity
        m = re.search(r'BEGIN:VCALENDAR\\n', ics)
        if m:
            start = m.end()
            ics = ics[:start] + 'X-WR-TIMEZONE:Europe/Copenhagen\\n' + ics[start:]

    # Finally, return with CRLFs per RFC 5545
    return ics.replace('\\n', '\\r\\n')


@app.route('/')
def proxy():
    """
    GET /?url=<source_ics_url>
      - Proxies the given ICS URL, rewrites TZIDs, injects VTIMEZONE if needed,
        fixes VCALENDAR ordering, and returns corrected ICS.
    If the environment variable SOURCE_URL is set, it's used when the query param is absent.
    """
    source_url = request.args.get('url') or os.environ.get('SOURCE_URL')
    if not source_url:
        return Response(
            'Missing source ICS URL. Provide ?url=https://... or set SOURCE_URL env var.',
            status=400,
            content_type='text/plain; charset=utf-8',
        )
    try:
        r = requests.get(source_url, timeout=20)
    except requests.RequestException as e:
        return Response(f'Upstream fetch error: {e}', status=502, content_type='text/plain; charset=utf-8')

    if r.status_code != 200:
        return Response(f'Upstream error: HTTP {r.status_code}', status=502, content_type='text/plain; charset=utf-8')

    fixed = rewrite_ics(r.text)
    return Response(fixed, content_type='text/calendar; charset=utf-8')


@app.route('/rewrite', methods=['POST'])
def rewrite_endpoint():
    """
    POST /rewrite
      - Accepts either a raw ICS body (text/calendar) or a multipart form with a file field named 'file'.
      - Returns the corrected ICS.
    """
    if request.files.get('file'):
        ics_text = request.files['file'].read().decode('utf-8', errors='replace')
    else:
        ics_text = request.get_data(as_text=True) or ''

    if not ics_text.strip():
        return Response('No ICS content received.', status=400, content_type='text/plain; charset=utf-8')

    fixed = rewrite_ics(ics_text)
    return Response(fixed, content_type='text/calendar; charset=utf-8')


@app.route('/healthz')
def health():
    return {'ok': True}


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '8000'))
    app.run(host='0.0.0.0', port=port)
