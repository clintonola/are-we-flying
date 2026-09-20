import logging
import os
import sys
from dotenv import load_dotenv
from app import create_app

if __name__ == '__main__':
    if sys.version_info < (3, 12):
        raise SystemExit('Python 3.12+ is required.')
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    try:
        app = create_app()
    except ValueError as exc:
        raise SystemExit(f'Configuration error: {exc}') from None
    try:
        port = int(os.getenv('PORT', '5001'))
        if not 1 <= port <= 65535:
            raise ValueError()
    except ValueError:
        raise SystemExit('PORT must be an integer from 1 to 65535.') from None
    logging.info('Flask server starting on http://127.0.0.1:%s (debug disabled)', port)
    app.run(host='127.0.0.1', port=port, debug=False)
