"""Group-based policy with caching confined to the current HTTP request."""

from .conf import GROUP


def is_locked(user, request=None):
    """Classify authenticated nonprivileged users without cross-request caching."""
    if not user or not user.is_authenticated or user.is_staff or user.is_superuser:
        return False
    if not user.pk:
        return False
    cache = None
    key = (user._meta.label_lower, user.pk)  # pylint: disable=protected-access
    if request is not None:
        raw_request = getattr(request, "_request", request)
        cache = getattr(raw_request, "_account_lock_membership", None)
        if cache is None:
            cache = {}
            raw_request._account_lock_membership = cache  # pylint: disable=protected-access
        if key in cache:
            return cache[key]
    # Do not reuse a potentially cached/prefetched User.groups relation from Open edX.
    locked = user.groups.filter(name=GROUP).exists()
    if cache is not None:
        cache[key] = locked
    return locked
