"""JSON Lines protocol: one worker serializes SQLite access, callers may pipeline IDs."""

import json
import logging
import os
from pathlib import Path
import sys
from .service import Service


def main():
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)
    recovery = os.environ.get("GESTIMATOR_RECOVERY_DIR")
    service = Service(Path(recovery) if recovery else None)

    def emit(message):
        print(json.dumps(message, ensure_ascii=False), flush=True)

    try:
        for line in sys.stdin:
            identity = None
            try:
                if len(line) > 2_000_000:
                    raise ValueError("Request too large")
                request = json.loads(line)
                if not isinstance(request, dict):
                    raise ValueError("Expected request object")
                identity = request.get("id")
                if not isinstance(identity, str) or len(identity) > 100:
                    raise ValueError("Expected request id")
                method = request.get("method")
                params = request.get("params", {})
                if not isinstance(method, str) or not isinstance(params, dict):
                    raise ValueError("Invalid method or params")
                if method == "shutdown":
                    emit(dict(id=identity, result=True))
                    break
                result = service.call(
                    method,
                    params,
                    lambda message: emit(
                        dict(id=identity, event="progress", message=message)
                    ),
                )
                try:
                    service.checkpoint_recovery()
                except Exception:
                    logging.exception("Could not write project recovery copy")
                    emit(dict(id=identity, event="progress", message="Recovery copy could not be updated"))
                emit(dict(id=identity, result=result))
            except (ValueError, KeyError, TypeError, IndexError) as exc:
                emit(
                    dict(
                        id=identity,
                        error=dict(code="INVALID_REQUEST", message=str(exc)),
                    )
                )
            except OSError as exc:
                emit(dict(id=identity, error=dict(code="FILE_ERROR", message=str(exc))))
            except Exception:
                logging.exception("Backend request failed")
                emit(
                    dict(
                        id=identity,
                        error=dict(
                            code="BACKEND_ERROR",
                            message="Operation failed; see backend log",
                        ),
                    )
                )
    finally:
        service.close()


if __name__ == "__main__":
    main()
