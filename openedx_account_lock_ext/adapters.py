"""Per-callback DRF adaptation preserving each endpoint's authentication policy."""

from functools import lru_cache
from types import FunctionType

from rest_framework.exceptions import APIException
from rest_framework.views import APIView

from . import conf, policy, recovery
from .identity import is_locked
from .responses import DETAIL


class AccountLocked(APIException):
    """Stable DRF denial rendered by the endpoint's normal dispatch machinery."""

    status_code = 403
    default_detail = {"error": "account_locked", "detail": DETAIL}
    default_code = "account_locked"


class GuardMixin(APIView):
    """Run policy checks after native authentication, permissions and throttles."""

    def initial(self, request, *args, **kwargs):
        """Keep the original authentication lifecycle and then enforce restrictions."""
        super().initial(request, *args, **kwargs)
        recovery_response = recovery.response(request, kwargs) if recovery.relevant(request) else None
        if recovery_response is not None:
            # DRF recovery views only have completion/token routes, never reset initiation.
            raise AccountLocked()
        if policy.denied(request, kwargs):
            raise AccountLocked()

    def finalize_response(self, request, response, *args, **kwargs):
        """Remove sensitive bootstrap fields before rendering the response."""
        if is_locked(request.user, request):
            response["Cache-Control"] = "no-store, private"
            if policy.bootstrap(request) and response.status_code == 200 and isinstance(response.data, dict):
                response.data = {
                    key: value for key, value in response.data.items() if key in conf.get("BOOTSTRAP_FIELDS")
                }
        return super().finalize_response(request, response, *args, **kwargs)


@lru_cache(maxsize=512)
def guarded_callback(callback: FunctionType) -> FunctionType:
    """Substitute a local view subclass while retaining outer callback decorators."""
    original = callback.__dict__["cls"]
    guarded: type[APIView] = type(
        f"Managed{original.__name__}",
        (GuardMixin, original),
        {"__module__": __name__},
    )
    # Calling guarded.as_view() here would discard decorators such as login_required,
    # non_atomic_requests and csrf_protect around the original callback. Clone the
    # as_view closure/decorator chain instead; never mutate shared classes or functions.
    replacements = []

    def clone(function: FunctionType) -> FunctionType:
        cells = []
        for cell in function.__closure__ or ():
            value = cell.cell_contents
            if value is original:
                value = guarded
                replacements.append(True)
            elif isinstance(value, FunctionType) and getattr(value, "cls", None) is original:
                value = clone(value)
            cells.append(_cell(value))
        copy = FunctionType(
            function.__code__, function.__globals__, function.__name__, function.__defaults__, tuple(cells) or None
        )
        copy.__dict__.update(function.__dict__)
        copy.__kwdefaults__ = function.__kwdefaults__
        copy.__annotations__ = function.__annotations__
        copy.__module__ = function.__module__
        copy.__doc__ = function.__doc__
        return copy

    guarded_view = clone(callback)
    if not replacements:
        raise RuntimeError("Unsupported DRF callback closure; update the Teak adapter before enabling this route.")
    return guarded_view


def _cell(value):
    """Create a Python closure cell for an isolated callback copy."""
    closure = (lambda: value).__closure__
    assert closure is not None
    return closure[0]
