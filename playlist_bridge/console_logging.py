"""Runtime console verbosity; retained web job output is unaffected."""
import logging

enabled = False
web_mode = False


class AccessFilter(logging.Filter):
    def filter(self, record):
        args = record.args
        if isinstance(args, tuple) and len(args) >= 5:
            method, status = args[1], args[4]
            if method == 'GET' and int(status) < 400:
                if not enabled:
                    return False
                record.levelno = logging.DEBUG
                record.levelname = 'DEBUG'
        return True


def configure(repo):
    global enabled, web_mode
    enabled = bool(repo.load('console_settings').get('debug', False))
    web_mode = True
    logging.getLogger('uvicorn.error').setLevel(logging.DEBUG if enabled else logging.INFO)
    logger = logging.getLogger('uvicorn.access')
    if not any(isinstance(f, AccessFilter) for f in logger.filters):
        logger.addFilter(AccessFilter())


def register(app):
    from pydantic import BaseModel
    from .api import job_store
    class ConsoleSettings(BaseModel):
        debug: bool = False

    @app.get('/api/settings/console')
    def get():
        return {'debug': bool(job_store().repository.load('console_settings').get('debug', False))}

    @app.put('/api/settings/console')
    def put(request: ConsoleSettings):
        repo = job_store().repository
        repo.save({'console_settings': request.model_dump()})
        configure(repo)
        return request.model_dump()
