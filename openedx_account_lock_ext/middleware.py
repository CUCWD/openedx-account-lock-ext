"""Request scope, Django page restrictions, and authenticated DRF dispatch."""

from django.utils.deprecation import MiddlewareMixin

from . import policy, recovery
from .adapters import guarded_callback
from .credentials import current_request
from .responses import blocked


class AccountLockMiddleware(MiddlewareMixin):
    """Run after all native view middleware, before the actual course/account view."""

    async_capable = False

    def __call__(self, request):
        """Keep credential protection scoped to this request, including exceptions."""
        token = current_request.set(request)
        try:
            return super().__call__(request)
        finally:
            current_request.reset(token)

    def process_view(self, request, callback, callback_args, callback_kwargs):
        """Adapt protected DRF callbacks or apply policy to ordinary Django views."""
        is_recovery = recovery.relevant(request)
        if not is_recovery and not policy.relevant(request, callback_kwargs):
            return None
        if hasattr(callback, "cls"):
            # Astroid cannot infer the callable type returned by FunctionType.
            # pylint: disable-next=not-callable
            return guarded_callback(callback)(request, *callback_args, **callback_kwargs)
        if is_recovery:
            response = recovery.response(request, callback_kwargs)
            if response is not None:
                return response
        if policy.denied(request, callback_kwargs):
            return blocked(request)
        return None
