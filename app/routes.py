import logging
from flask import Blueprint, Response, current_app, request
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse
from .aviation_weather import fetch_metar, WeatherError
from .weather_parser import parse_weather
from .evaluator import evaluate
from .sms import command, format_evaluation, format_metar, format_limits, HELP, UNKNOWN_COMMAND, unknown

routes = Blueprint('routes', __name__)
log = logging.getLogger(__name__)

@routes.get('/')
def index() -> str:
    return 'Are We Flying? is running.'

@routes.get('/health')
def health() -> dict:
    return {'status': 'ok'}

@routes.post('/sms')
def sms() -> Response:
    s = current_app.config['SETTINGS']
    # Pin the complete public URL; never reconstruct it from untrusted proxy headers.
    if request.query_string or request.mimetype != 'application/x-www-form-urlencoded':
        return Response(status=403)
    reply = MessagingResponse()
    # Duplicate identity or command fields are ambiguous even if signed.
    if any(len(request.form.getlist(k)) != 1 for k in ('From', 'To', 'AccountSid', 'Body')):
        return Response(status=403)
    # Match complete channel/address pairs; never strip a channel prefix.
    sms_authorized = (request.form['From'] == s.allowed_phone
                      and request.form['To'] == s.twilio_phone)
    whatsapp_authorized = (bool(s.whatsapp_phone)
                           and request.form['From'] == 'whatsapp:' + s.allowed_phone
                           and request.form['To'] == s.whatsapp_phone)
    if (not (sms_authorized or whatsapp_authorized)
            or request.form['AccountSid'] != s.account_sid):
        log.warning('Unauthorized messaging request (phone numbers omitted)')
        return Response(str(reply), mimetype='application/xml')
    cmd = command(request.form['Body'])
    try:
        if cmd in ('ARE WE FLYING', 'CAN I FLY', 'FLY', 'WEATHER', 'METAR'):
            log.info('Inbound authorized weather request: %s', cmd)
            w = parse_weather(fetch_metar(s.airport), s.airport)
            if cmd == 'METAR':
                # Still refuse mismatched stations; other missing fields need not prevent raw display.
                text = unknown('METAR airport mismatch.') if any('airport' in i for i in w.issues) else format_metar(w)
            else:
                text = format_evaluation(w, evaluate(w, s))
        elif cmd == 'LIMITS':
            text = format_limits(s)
        elif cmd == 'HELP':
            text = HELP.format(airport=s.airport)
        else:
            text = UNKNOWN_COMMAND
    except WeatherError as exc:
        text = unknown(str(exc))
    except Exception:
        log.exception('Unexpected weather processing failure')
        text = unknown("I couldn't retrieve or interpret the weather right now.")
    # Twilio limits a Message body to 1600 characters. Never truncate a decision.
    if len(text) > 1500:
        text = unknown('Weather report is too long to safely display by SMS. Use the local CLI.')
    reply.message(text)
    return Response(str(reply), mimetype='application/xml')
