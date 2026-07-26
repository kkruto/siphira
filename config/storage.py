import logging

from whitenoise.storage import CompressedManifestStaticFilesStorage

logger = logging.getLogger(__name__)


class ResilientManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """Manifest storage that degrades instead of taking the site down.

    Django's default raises ValueError the moment a template references a
    static file that is not in the manifest — so a single missing asset stops
    EVERY page with a bare "Internal Server Error". That is a bad trade for a
    personal site: an unstyled page is a cosmetic problem a visitor can still
    read and act on, a 500 is a dead site.

    Degrading takes BOTH overrides below. `manifest_strict = False` only covers
    the "not in the manifest" case; if the file is also absent from disk, the
    parent's hashed_name() raises "could not be found" on its own, and the page
    500s anyway. Verified by reproducing both.

    This is a safety net, not the control. The deploy is still where a missing
    build must be caught: scripts/bootstrap.sh builds Tailwind before
    collectstatic runs, and scripts/deploy.sh fails the deploy outright if
    static/dist/site.css is absent. This only bounds the damage if both fail.
    """

    manifest_strict = False

    def hashed_name(self, name, content=None, filename=None):
        try:
            return super().hashed_name(name, content, filename)
        except ValueError:
            # The asset is genuinely missing from STATIC_ROOT. Serve the
            # unhashed path: it will very likely 404, but a 404 on one
            # stylesheet costs styling, while raising here costs the page.
            logger.error(
                'static asset %r is missing from STATIC_ROOT — serving the '
                'unhashed path. The front-end build did not run or did not '
                'ship; check scripts/deploy.sh step 3.', name
            )
            return name
