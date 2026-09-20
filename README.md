# Are We Flying?

A small **local-only, deterministic** Python 3.12+ SMS weather checker for KRYY. No AI, database, scheduler, or hosting deployment.

## What it does

Text your Twilio number `ARE WE FLYING?`. The app retrieves one current AWC METAR, validates required fields and freshness, checks your personal minimums, and replies with TwiML. PASS means only that the **reported conditions meet these configured rules**. FAIL lists unmet rules; UNKNOWN overrides either outcome if required data is uncertain. The app never sends a separate outbound API message.

## Architecture

```text
My Phone
↓
Twilio SMS
↓
ngrok
↓
Local Flask App (signature validation and phone authorization)
↓
Aviation Weather Center API
↓
Weather Parser
↓
Personal Minimum Evaluator
↓
Runway/Crosswind Calculator
↓
Twilio Reply (TwiML returned to original webhook)
↓
My Phone
```

`aviation_weather.py` retrieves; `weather_parser.py` normalizes; `runway.py` calculates components; `evaluator.py` decides; `sms.py` formats; `routes.py` secures and handles webhooks. Local demos use the same parser, evaluator, and formatter as SMS. No demo routes exist.

## Personal minimums

| Criterion | Requirement |
|---|---|
| Visibility | ≥ 5 statute miles |
| Ceiling | ≥ 4,000 feet AGL, or no reported ceiling restriction |
| Wind/gust | ≤ 25 knots |
| Crosswind | ≤ 10 knots using the greater of sustained wind and gust |
| AWC flight category | VFR |
| Observation age | ≤ 90 minutes |

Only BKN, OVC and VV (including AWC's OVX representation) define ceilings. FEW/SCT do not. Missing cloud data is different from no ceiling. Missing vertical visibility is UNKNOWN. Numeric, fractional, and lower-bound visibility such as `10+` are supported conservatively; less-than or unrecognized values return UNKNOWN. Raw and JSON wind/ceiling disagreement returns UNKNOWN. Missing category does not get inferred into VFR.

For both runway directions, crosswind = speed × |sin(angle)| and headwind = speed × cos(angle), with angles converted to radians. The greatest headwind selects the runway; reciprocal directions have the same crosswind magnitude. Comparisons use unrounded values (only a 1e-9 kt tolerance at the crosswind boundary); display rounds to one decimal. A displayed 10.0 can thus fail when the underlying value is just above 10.

VRB and directional variability ranges use full worst wind speed as conservative crosswind. Best runway is undetermined for variable winds. Calm defaults to the first configured runway, 09. A runway suggestion considers wind components only, not closures, traffic, ATC, or runway condition.

### Runway references and magnetic variation — setup required

The supplied **09 = 094° magnetic / 27 = 274° magnetic** values are retained in `app/config.py`. Current official FAA magnetic headings were **not verified** during implementation. Verify these and magnetic variation periodically using the current [FAA airport diagram/terminal procedures](https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/dtpp/) and [FAA Chart Supplement](https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/dafd/). Record the source/cycle you use below or in your local configuration notes.

The local configuration uses `MAGNETIC_VARIATION_DEG=-4`, matching the published KRYY airport-record value (04W, epoch 2005).

METAR wind uses **true north**. Configure `MAGNETIC_VARIATION_DEG` from verified airport data, east positive / west negative. The calculation is `runway_true = runway_magnetic + variation`. Blank variation intentionally gives UNKNOWN for non-calm directional winds. Do not enter zero just to enable PASS. Synthetic demos use zero explicitly, solely for demonstration. Reference: [NWS/WMO measurement guidance](https://www.weather.gov/media/epz/mesonet/CWOP-WMO8.pdf).

## SMS commands

| Text | Response |
|---|---|
| ARE WE FLYING?, FLY, FLY?, CAN I FLY?, WEATHER | Full check |
| METAR | Raw report, UTC timestamp and age; no minimums decision |
| LIMITS | Configured personal minimums |
| HELP | Command help |

Case, punctuation, and repeated whitespace are normalized. Unsupported commands show help suggestions without fetching weather. Unauthorized senders receive empty TwiML, with no weather request or SMS reply.

## Installation

Clone your GitHub repository:

```bash
git clone YOUR_REPOSITORY_URL are-we-flying
cd are-we-flying
```

From the project directory:

```bash
cd are-we-flying
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
touch .env
```

Use any installed Python **3.12 or newer** in place of `python3.12`. Windows activation is `.venv\Scripts\activate`. Add the environment variables listed below to `.env` locally; never paste credentials in chat or commit it. `.gitignore` excludes it and virtual environments. The demo and live CLI do not require Twilio credentials.

## Environment variables

| Variable | Value |
|---|---|
| TWILIO_ACCOUNT_SID | Your account SID beginning AC |
| TWILIO_AUTH_TOKEN | Your Twilio auth token |
| TWILIO_PHONE_NUMBER | Your SMS-capable Twilio number, E.164, e.g. +1… |
| ALLOWED_PHONE_NUMBER | Your personal sending number, E.164 |
| AIRPORT_ID | KRYY |
| PORT | 5001 (avoids the macOS AirPlay port conflict) |
| PUBLIC_WEBHOOK_URL | Exact HTTPS ngrok URL including /sms |
| MAGNETIC_VARIATION_DEG | Verified signed variation, east positive / west negative |

Create a local `.env` and add the variables in the table above; environment files are never tracked. The first four and the public URL are required to start the SMS server. KRYY is the airport default. Blank magnetic variation prevents a directional weather determination; it does not prevent the server or other commands from working. Configuration errors stop startup with an actionable message and no secrets.

## Running Flask locally

Terminal 1, from the project directory:

```bash
source .venv/bin/activate
python run.py
```

After first configuring the public URL as described below, browse [localhost:5001](http://localhost:5001) for `Are We Flying? is running.` or [health](http://localhost:5001/health) for `{"status":"ok"}`. Flask binds to loopback only; debug and its interactive debugger are disabled. Use Ctrl-C to stop.

## Starting ngrok

Install the ngrok agent using the [official installation instructions](https://ngrok.com/docs/getting-started/). On macOS with Homebrew:

```bash
brew install ngrok
ngrok config add-authtoken YOUR_NGROK_AUTHTOKEN
```

Enter your own ngrok token locally. Then Terminal 2:

```bash
ngrok http 5001
```

Copy the HTTPS forwarding URL. For first-time setup you can start ngrok before Flask to obtain this URL. Set in `.env`:

```dotenv
PUBLIC_WEBHOOK_URL=https://YOUR-NGROK-URL.ngrok-free.app/sms
```

Start or restart Flask after changing `.env`. Free URLs may change when ngrok restarts: update **both** this variable and the Twilio webhook. Use the exact domain ngrok actually displays, even if it differs from these examples.

### Quick start after setup

Terminal 1: `source .venv/bin/activate` → `python run.py`

Terminal 2: `ngrok http 5001`

Copy HTTPS URL → update `.env` and restart Flask if needed → paste URL plus `/sms` into Twilio → text `ARE WE FLYING?`.

The app only works while **your computer is on, Flask is running, ngrok is running, and internet access works**. No cloud server is required or created.

## Configuring the Twilio webhook

1. In Twilio Console, open **Phone Numbers → Manage → Active numbers**.
2. Select your SMS-capable Twilio phone number.
3. Under **Messaging Configuration**, set **A message comes in** to **Webhook**.
4. Enter `https://YOUR-NGROK-URL.ngrok-free.app/sms`.
5. Select **HTTP POST** and save.
6. Ensure the number uses this webhook rather than a conflicting Messaging Service handler.
7. This direct-TwiML SMS reply flow requires an account that supports custom TwiML responses. Twilio's current SMS trial documentation says direct TwiML XML responses are not supported during the trial. Upgrade the account and complete any messaging onboarding/registration Twilio requires for your number before expecting real SMS replies. See [Twilio SMS trial limitations](https://www.twilio.com/docs/usage/trials/try-out-sms). Phone verification alone does not remove this restriction.

Validation uses Twilio's official `RequestValidator`, your auth token, all submitted form fields, and the **configured public URL**. It does not trust Host or X-Forwarded headers. Twilio signs the external HTTPS URL even though Flask sees local HTTP. Do not add a trailing slash, query string, or disable signature validation. Documentation: [Twilio request security](https://www.twilio.com/docs/usage/security).

## Testing the SMS flow

Save the Twilio number in your contacts. From the `ALLOWED_PHONE_NUMBER`:

1. Text `ARE WE FLYING?`; expect the full PASS/FAIL/UNKNOWN report.
2. Check the Flask terminal for an authorized request, API result, observation timestamp and evaluation.
3. Confirm the SMS arrives. Emoji reports may span multiple billable SMS segments.
4. Text `METAR`; expect raw KRYY METAR, observed UTC and age. This command displays data even when stale; it is not a PASS.
5. Text `LIMITS`; expect your five personal limits, with no API request.
6. Text `HELP`; expect command help.

The supplied automated tests do not send real SMS. End-to-end Twilio/ngrok delivery must be verified manually with your credentials. Ngrok/Twilio inspectors may retain message content and phone numbers: treat their local dashboards/account logs as private.

## Running tests

```bash
python -m pytest -q
```

Tests mock all network access and use Twilio's real signing library with fake credentials. A global guard prevents accidental HTTP calls. They cover thresholds, stale/future timestamps, cloud layers, gusts, reciprocal components, conservative variable winds, malformed data, API errors, signed webhook commands and authorization. `requirements-tested.txt` records the exact dependency versions used for the final test run; use it instead of `requirements.txt` if reproducing that environment.

## Local debug mode

```bash
python -m app.cli weather
```

Makes one real AWC request and prints the SMS report, RESULT, and each runway's headwind/tailwind and crosswind. No Twilio or ngrok needed. It uses your configured variation, and reports UNKNOWN if it is unset or data is unsafe.

## Using local demo weather

```bash
python -m app.cli demo good
python -m app.cli demo crosswind
python -m app.cli demo ceiling
python -m app.cli demo visibility
python -m app.cli demo wind
python -m app.cli demo ifr
```

These are credential-free, offline, synthetic scenarios with fresh UTC timestamps. Each prints a prominent demo banner plus the SMS response. They call the actual parser/evaluator; no duplicated decision logic. `good` passes; each other scenario fails its named criterion. `ifr` also fails ceiling and visibility. The synthetic 4 SM visibility example intentionally keeps category VFR to demonstrate independent checks. Demo commands are unavailable via `/sms`.

## Changing personal minimums

Edit `Minimums` in `app/config.py`, then restart Flask and rerun tests. `LIMITS` renders the same configuration the evaluator uses. Airport geometry is also centralized there. No secrets belong in this file.

## Changing airports

This version is intentionally guarded against applying KRYY geometry to another airport. Update the `Settings` runway tuple, airport default, `from_env` airport guard, `.env`, magnetic variation and tests together, using current official data. Setting only `AIRPORT_ID` to a different airport fails safely. Future airport/profile loaders, forecast checks or other weather sources can be added around the existing models; none are implemented here.

## Safety limitations

This is a convenience check, **not a legal or final aeronautical go/no-go decision**. It does not replace official weather, preflight planning, NOTAM/TFR review, aircraft or school limitations, instructor decisions, or pilot judgment. It only checks the listed criteria at the observation time, not weather en route, trends, forecasts, precipitation, thunderstorms, icing, density altitude, terrain, runway conditions or aircraft performance. PASS can coexist with hazardous weather outside those criteria. Cloud/visibility/wind uncertainty, missing fields, stale or future observations return UNKNOWN. Source format changes may conservatively produce UNKNOWN until the parser is updated.

## Troubleshooting

| Symptom | Check |
|---|---|
| Twilio does not reach webhook | Number's Messaging handler, POST setting, HTTPS URL, internet, ngrok request inspector and Twilio Messaging logs |
| ngrok URL changed | Update Twilio **and** PUBLIC_WEBHOOK_URL; restart Flask |
| Flask not running / tunnel 502 | Activate environment, run `python run.py`, test `/health`, check port 5001 conflicts |
| Invalid signature / 403 | Exact public URL including `/sms`, account auth token, POST form encoding; direct unsigned curl calls are intentionally rejected |
| 403 unauthorized | Invalid/malformed signature or ambiguous form fields gives 403. A correctly signed unauthorized phone/account/destination gets 200 with empty TwiML and no reply |
| API unavailable | Check internet and [AWC status](https://aviationweather.gov/status/); the app returns UNKNOWN without retries or polling |
| Environment missing | Create `.env`, fill values locally, run from project root and restart; numbers need E.164 format |
| Weather always UNKNOWN | Read the reason; verify variation, current observation age, station, schema and required fields |
| Error 12300 on a Trial account despite valid XML | Current SMS trials do not support direct TwiML XML responses; see the trial restrictions above. The account must support this reply flow |
| No SMS despite HTTP 200 | Empty response means unauthorized sender/account/destination; otherwise check Twilio delivery errors, trial restrictions and messaging eligibility |

The API uses the [official AWC endpoint and guidance](https://aviationweather.gov/data/api/) with a descriptive User-Agent and 5-second connection / 10-second read timeout. No aggressive polling, automatic retries or scheduled texts. A slow upstream can still cause Twilio to time out; inspect delivery logs and try again later. Signed webhook retries are not deduplicated in this small database-free version.

## Verification record

- Runway magnetic headings: user-supplied 094°/274°, **not officially verified**.
- Magnetic variation: configured as `-4` (4° west) per user request and the [KRYY airport record published by AirNav](https://www.airnav.com/airport/KRYY), accessed 2026-09-19. The record labels this value **04W (2005)**; this is an airport-record value, not a verified 2026 geomagnetic-model estimate. Runway headings remain the supplied approximate 094°/274° values.
- Live AWC response format inspected during implementation; automated tests remain offline.
- Real Twilio/ngrok SMS flow: pending your credentials and manual setup.
- No deployment, secrets, or outbound SMS were created.

Local verification: Python 3.12.14; 143 pytest tests passed, including all six CLI demos and WhatsApp authorization tests. The Flask health endpoint and ngrok tunnel were checked. WhatsApp replies were subsequently confirmed by the user; SMS delivery remains subject to Twilio account restrictions.

## WhatsApp Sandbox demo

The app now accepts authorized WhatsApp requests at the same `/sms` endpoint. It preserves full `whatsapp:` addresses, validates signatures, and requires the configured account, your allowed number, and the configured sandbox destination. SMS support remains available. Weather evaluation is shared.

```dotenv
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
```

Match this to the number shown in your Console. Keep `ALLOWED_PHONE_NUMBER` as plain E.164 (`+1...`); the app adds the WhatsApp prefix for matching. Blank `TWILIO_WHATSAPP_NUMBER` disables WhatsApp.

1. Open the legacy Twilio WhatsApp Sandbox and join using its QR code or account-specific join message from your allowed phone.
2. In Sandbox settings, set **When a message comes in** to your `PUBLIC_WEBHOOK_URL`, using POST. The current local URL is in `.env`.
3. Restart Flask after configuration changes. Keep Flask and ngrok running.
4. In WhatsApp, message the **sandbox number**, first `LIMITS`, then `ARE WE FLYING?`.

The [legacy Sandbox](https://www.twilio.com/docs/whatsapp/sandbox) supports TwiML replies for testing. Membership expires after three days; rejoin when needed. In contrast, the [new WhatsApp trial](https://www.twilio.com/docs/usage/trials/try-out-whatsapp) does not support direct TwiML XML replies. If you only have that interface, confirm legacy Sandbox access with Twilio before relying on this flow. No WhatsApp message has been sent by the automated tests.
