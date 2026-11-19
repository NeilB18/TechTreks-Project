"""Keep secrets out of the logs.

GroupMe sends the person's access token back in the address (/accounts/groupme/callback?access_token=...),
and Django's request log prints whole addresses. A GroupMe token opens that person's whole GroupMe account,
so it must never land in a log. This filter rewrites it to access_token=[hidden] before anything is written.
"""

import logging
import re

SECRET = re.compile(r"(access_token=)[^&\s\"']+", re.IGNORECASE)


class RedactTokens(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        hidden = SECRET.sub(r"\1[hidden]", message)
        if hidden != message:
            record.msg, record.args = hidden, ()
        return True
