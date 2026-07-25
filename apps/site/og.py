"""Per-post Open Graph cards, rendered with Pillow.

Without this every shared link previews identically. Cards are drawn on demand
and cached on disk, so the cost is paid once per post.
"""
import logging
import textwrap
from pathlib import Path

from django.conf import settings
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

W, H = 1200, 630
BG = (250, 250, 249)        # warm white  #FAFAF9
INK = (31, 41, 55)          # charcoal    #1F2937
SAGE = (132, 169, 140)      # sage green  #84A98C
SAND = (214, 198, 184)      # sand        #D6C6B8
MUTED = (120, 128, 122)

CACHE_DIR = Path(settings.BASE_DIR) / 'og_cache'


def _font(size, bold=False):
    """Best-effort font lookup. Falls back to Pillow's bitmap default rather
    than raising — an ugly card beats a 500 on a social crawler."""
    candidates = [
        f'/usr/share/fonts/truetype/dejavu/DejaVuSans{"-Bold" if bold else ""}.ttf',
        f'C:/Windows/Fonts/{"seguisb" if bold else "segoeui"}.ttf',
        '/System/Library/Fonts/Supplemental/Arial{}.ttf'.format(' Bold' if bold else ''),
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def render_card(title, kicker='', meta=''):
    img = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(img)

    # Sage rule along the top and a sand block bottom-right for brand shape.
    d.rectangle([0, 0, W, 12], fill=SAGE)
    d.rounded_rectangle([W - 300, H - 210, W - 60, H - 60], radius=24, fill=SAND)

    y = 110
    if kicker:
        d.text((70, y), kicker.upper(), font=_font(26, bold=True), fill=SAGE)
        y += 56

    title_font = _font(64, bold=True)
    # Wrap narrower when the title is long so it never collides with the block.
    for line in textwrap.wrap(title, width=26)[:4]:
        d.text((70, y), line, font=title_font, fill=INK)
        y += 82

    d.text((70, H - 100), meta or 'siphira.fluximpact.org',
           font=_font(28), fill=MUTED)
    return img


def card_for_post(post):
    """Returns bytes of the PNG, cached on disk and invalidated by mtime."""
    CACHE_DIR.mkdir(exist_ok=True)
    stamp = int(post.updated_at.timestamp())
    path = CACHE_DIR / f'post-{post.slug}-{stamp}.png'

    if not path.exists():
        # Drop older renders of this same post so the cache can't grow forever.
        for stale in CACHE_DIR.glob(f'post-{post.slug}-*.png'):
            stale.unlink(missing_ok=True)
        kicker = post.category.name if post.category else 'Writing'
        img = render_card(post.title, kicker, f'Siphira John · {post.read_time} min read')
        img.save(path, 'PNG', optimize=True)

    return path.read_bytes()


def card_default(title, kicker=''):
    CACHE_DIR.mkdir(exist_ok=True)
    path = CACHE_DIR / f'page-{kicker or "home"}.png'
    if not path.exists():
        render_card(title, kicker, 'siphira.fluximpact.org').save(path, 'PNG', optimize=True)
    return path.read_bytes()
