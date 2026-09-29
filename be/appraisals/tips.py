"""Rotating daily sales tips for sofa, recliner, and seating hardware."""

from __future__ import annotations

import copy
from datetime import date
from typing import Any

DEFAULT_DAILY_TIP_PACKS: list[dict[str, Any]] = [
    {
        'id': 'reach-workshops',
        'title': 'Reach the makers who buy today',
        'why': 'Closed sales sit in workshops. Waiting in the shop rarely fills a daily target.',
        'tips': [
            'Before 10am, call five sofa makers you already sold to. Ask what they are cutting this week.',
            'Visit one workshop in person. Take a sofa stand, a recliner mechanism, and a meeting-chair base they can hold.',
            'Ask which room it is for: home sofa, hotel lobby, or boardroom. The hardware changes with the job.',
            'Leave a sample set of four stands with felt pads. Follow up the day they start upholstery.',
            'Book tomorrow’s visit before you leave. Dates close sales; “I’ll pass by” does not.',
        ],
    },
    {
        'id': 'choose-sofa-stands',
        'title': 'Help them choose the right sofa stand',
        'why': 'Makers buy from the person who stops a wobbly sofa — not from a photo of chrome legs.',
        'tips': [
            'Measure with them. Finished seat height should land around 43–51 cm for most adults.',
            'Load first, style second. A 3-seater plus people needs a rated stand, not the lightest look.',
            'Sell a set of four. For long 3- and 4-seaters, add a center support so the middle does not sag.',
            'Match the floor: felt pads on tiles, rubber on smooth floors, taller stands if they clean underneath.',
            'Post a short how-to, not only a product picture: height, load, set of four, finish, and fixing plate.',
        ],
    },
    {
        'id': 'recliners-meeting',
        'title': 'Talk recliners and meeting seats like a technician',
        'why': 'High-end seating fails on the mechanism and the base — that is your opening.',
        'tips': [
            'Ask wall space before you quote a recliner. Wall-huggers need about 10–15 cm; standard mechanisms need 30–45 cm behind the back.',
            'Confirm weight rating and how often it will recline. Hotels and waiting rooms need a stronger mechanism than a home TV chair.',
            'Sell the kit: mechanism, handle or cable, bushes, and spare screws. One missing part kills the job.',
            'For meeting chairs, check the base and swivel separately from the foam. Commercial bases carry more load than dining chairs.',
            'After they collect, show how to tighten bolts and never stand on the footrest. That call brings the next order.',
        ],
    },
    {
        'id': 'workshop-experience',
        'title': 'Make the workshop visit worth repeating',
        'why': 'People remember how you treated the job on their floor.',
        'tips': [
            'Start with their job, not your catalogue. What are they covering today — corner sofa, recliner, or office seating?',
            'Demonstrate on their frame. Let them feel the stand plate and the recliner action.',
            'Write the order clearly: quantity (sets of four), finish, height, and delivery day. Repeat it back.',
            'On delivery, check the set is complete — stands, screws, pads — before you leave the gate.',
            'Follow up the next day: did the stands sit level? Fix it fast and they will call you first next week.',
        ],
    },
    {
        'id': 'teach-then-sell',
        'title': 'Teach today, sell this week',
        'why': 'A useful post travels further than a picture of stock.',
        'tips': [
            'Post five lines: how to choose sofa stands — height, load, number of legs, finish, and floor type.',
            'Film 20 seconds of a recliner opening. Name the parts: mechanism, cable, footrest, back lock.',
            'Answer one real question in the caption: will these stands hold a 3-seater? Show the rating.',
            'Tag one workshop you helped this month and say what you solved, not only what you stock.',
            'Share a meeting-chair tip: commercial bases need a higher load rating than home dining chairs.',
        ],
    },
]


def _normalize_tip_pack(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    title = str(raw.get('title') or '').strip()
    tips_raw = raw.get('tips')
    if not title or not isinstance(tips_raw, list):
        return None
    tips = [str(tip).strip() for tip in tips_raw if str(tip).strip()]
    if len(tips) < 3:
        return None
    pack_id = str(raw.get('id') or '').strip()
    if not pack_id:
        pack_id = title.lower().replace(' ', '-')[:48]
    return {
        'id': pack_id,
        'title': title,
        'why': str(raw.get('why') or '').strip(),
        'tips': tips[:8],
    }


def normalize_daily_tip_packs(raw: Any) -> list[dict[str, Any]]:
    incoming = None
    if isinstance(raw, dict):
        incoming = raw.get('daily_tip_packs')
    elif isinstance(raw, list):
        incoming = raw
    if not isinstance(incoming, list) or not incoming:
        return copy.deepcopy(DEFAULT_DAILY_TIP_PACKS)
    packs = [pack for pack in (_normalize_tip_pack(row) for row in incoming) if pack]
    return packs or copy.deepcopy(DEFAULT_DAILY_TIP_PACKS)


def pick_daily_tips(template: dict[str, Any] | None, today: date | None = None) -> dict[str, Any]:
    packs = normalize_daily_tip_packs(template or {})
    today = today or date.today()
    index = (today.toordinal()) % len(packs)
    pack = copy.deepcopy(packs[index])
    pack['tips'] = pack['tips'][:5]
    pack['index'] = index
    pack['count'] = len(packs)
    return pack
