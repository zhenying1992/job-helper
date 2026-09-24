import logging

logger = logging.getLogger(__name__)

def catch_error(f):
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as ex:
            logger.error(ex, exc_info=True)

    return wrapper