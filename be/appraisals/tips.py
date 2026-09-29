"""Rotating daily sales tips: follow up, talk well, and win more customers."""

from __future__ import annotations

import copy
from datetime import date
from typing import Any

DEFAULT_DAILY_TIP_PACKS: list[dict[str, Any]] = [
    {
        'id': 'follow-up',
        'title': 'Follow up before they forget you',
        'why': 'Most closed sales come from people you already know — if you call them back.',
        'tips': [
            'Before 10am, call five customers you already sold to. Ask how the last job is going.',
            'If they said “I will take, later,” call today. Later rarely comes on its own.',
            'After a delivery, call the next morning: did everything arrive, and is anything missing?',
            'Write three follow-up names before you leave the shop, then tick them off.',
            'If they are busy, ask when to call back — and call at that time.',
        ],
    },
    {
        'id': 'talk-well',
        'title': 'Talk with customers, not at them',
        'why': 'People buy from someone who listens and speaks clearly.',
        'tips': [
            'Greet first, then ask what they are working on. Do not open with the price list.',
            'Repeat what they asked in their words, so they know you heard them.',
            'Use simple language. If they look unsure, slow down and explain once more.',
            'Do not argue about price. Ask what they need the item to do, then help them choose.',
            'Thank them for their time even when they do not buy today. Leave the door open.',
        ],
    },
    {
        'id': 'more-customers',
        'title': 'Find one new customer today',
        'why': 'New names fill the target when regulars are quiet.',
        'tips': [
            'Ask a happy customer: who else in their line of work might need the same things?',
            'Visit one new workshop or site you have not sold to this month.',
            'Collect a name, phone, and what they usually buy. Write it down the same day.',
            'Introduce yourself in one sentence: who you help, and how they can reach you.',
            'Go back to yesterday’s new contact with a short follow-up, not a hard pitch.',
        ],
    },
    {
        'id': 'keep-them',
        'title': 'Make it easy for them to call you first',
        'why': 'Repeat customers close the daily target faster than cold visits.',
        'tips': [
            'Save every customer’s name and what they last bought before you forget.',
            'If you cannot supply today, say when you can — then keep that promise.',
            'If something is wrong, own it quickly and fix it. Quiet problems lose customers.',
            'Check in on quiet customers: “We have not spoken this month — how is work?”',
            'After a good sale, ask when they will next need a restock, and set a reminder.',
        ],
    },
    {
        'id': 'ask-then-help',
        'title': 'Ask, then help',
        'why': 'Good questions show respect and uncover the next order.',
        'tips': [
            'Ask what they are building this week, not only what they want to buy.',
            'Ask who will use it — home, hotel, or office — then advise from that.',
            'If they hesitate, ask what would make the choice easier, then answer that.',
            'Offer the next useful item only after you have solved what they came for.',
            'End every visit with a next step: a quote, a sample, or a time you will call.',
        ],
    },
]

LEGACY_TIP_PACK_IDS = frozenset({
    'reach-workshops',
    'choose-sofa-stands',
    'recliners-meeting',
    'workshop-experience',
    'teach-then-sell',
})


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
    if not packs:
        return copy.deepcopy(DEFAULT_DAILY_TIP_PACKS)
    ids = {pack['id'] for pack in packs}
    if ids <= LEGACY_TIP_PACK_IDS:
        return copy.deepcopy(DEFAULT_DAILY_TIP_PACKS)
    return packs


def pick_daily_tips(template: dict[str, Any] | None, today: date | None = None) -> dict[str, Any]:
    packs = normalize_daily_tip_packs(template or {})
    today = today or date.today()
    index = (today.toordinal()) % len(packs)
    pack = copy.deepcopy(packs[index])
    pack['tips'] = pack['tips'][:5]
    pack['index'] = index
    pack['count'] = len(packs)
    return pack
