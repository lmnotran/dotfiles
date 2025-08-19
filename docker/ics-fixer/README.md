
# Flask ICS Timezone Fixer

Fixes Outlook ICS feeds that contain Microsoft TZIDs like `"W. Europe Standard Time"` by mapping to IANA
(`Europe/Copenhagen`), injects a `VTIMEZONE` when missing, and **keeps VCALENDAR property ordering correct**
so Google Calendar will actually ingest events.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export SOURCE_URL='https://<your-outlook-ics-link>'
python app.py  # http://0.0.0.0:8000
```

Subscribe in Google Calendar → **Settings → Add calendar → From URL**:
- If `SOURCE_URL` is set: `http://<your-host>:8000/`
- Or pass a param: `http://<your-host>:8000/?url=https://<your-ics-link>`

## Docker

```bash
docker build -t ics-fixer .
docker run -e SOURCE_URL='https://<your-outlook-ics-link>' -p 8000:8000 --name ics-fixer ics-fixer
```


## One-off file rewrite

```bash
curl -s -X POST --data-binary @reachcalendar.ics http://localhost:8000/rewrite > fixed.ics
# or multipart:
curl -s -F file=@reachcalendar.ics http://localhost:8000/rewrite > fixed.ics
```

## Notes
- We only add the `Europe/Copenhagen` block if it doesn't already exist.
- We place the VTIMEZONE **after VCALENDAR header properties** and before the first component.
- Mapping table lives in `MS_TZ_TO_IANA`.


## Docker Compose

1) Copy `.env.example` → `.env` and set your Outlook ICS URL.
2) Build & run:
```bash
docker compose up -d --build
```
3) Subscribe in Google Calendar to: `http://<your-host>:8000/`

Logs & lifecycle:
```bash
docker compose logs -f
docker compose restart
docker compose down
```
