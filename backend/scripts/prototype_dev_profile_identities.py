from __future__ import annotations

import hashlib
import random
import sys
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.database import SessionLocal
from app.models.profile import Profile


SAMPLE_SIZE = 100
SEED = 20261008

FIRST_NAMES = (
    "aaron", "adrian", "aisha", "amara", "amelia", "amina", "andrew",
    "anna", "anthony", "aria", "ariel", "ayla", "ben", "bella",
    "benjamin", "brandon", "brianna", "caleb", "camila", "carla",
    "caroline", "charles", "chloe", "christian", "daniel", "david",
    "diana", "diego", "elena", "elias", "elijah", "ella", "emilia",
    "emma", "eric", "eva", "faith", "fatima", "felix", "gabriel",
    "grace", "hannah", "harper", "henry", "ian", "isabel", "james",
    "jasmine", "jason", "julia", "julian", "karen", "kevin", "lara",
    "laura", "leah", "leo", "liam", "lina", "lucas", "lucia", "luca",
    "maya", "mia", "michael", "mila", "naomi", "natalie", "nathan",
    "nina", "noah", "nora", "oliver", "olivia", "omar", "oscar",
    "paul", "rachel", "rafael", "rebecca", "riley", "robert", "ruby",
    "samuel", "sara", "sarah", "sebastian", "simon", "sofia", "sophia",
    "steven", "talia", "thomas", "tobias", "victor", "violet", "william",
    "yasmin", "zoe",
)

LAST_NAMES = (
    "adebayo", "adler", "anderson", "andrews", "baker", "bello", "benitez",
    "berg", "bernard", "brooks", "brown", "carter", "castillo", "chen",
    "clarke", "cohen", "collins", "davis", "dean", "diaz", "edwards",
    "ellis", "evans", "fischer", "foster", "garcia", "gomez", "grant",
    "green", "griffin", "hall", "hansen", "harris", "hayes", "henderson",
    "hernandez", "hill", "holland", "hughes", "ibrahim", "jackson",
    "james", "johnson", "jones", "kareem", "kennedy", "khan", "king",
    "klein", "kumar", "lee", "lewis", "lopez", "martin", "martinez",
    "mason", "miller", "mitchell", "moore", "morgan", "morris", "muller",
    "murphy", "nelson", "nguyen", "nichols", "nielsen", "noble", "nolan",
    "norris", "nwosu", "okafor", "olsen", "ortiz", "owens", "parker",
    "patel", "pearson", "peterson", "phillips", "porter", "powell",
    "price", "ramirez", "reid", "richards", "rivera", "roberts",
    "robinson", "ross", "ruiz", "sanchez", "sanders", "schmidt", "scott",
    "shah", "shaw", "singh", "smith", "stewart", "sullivan", "taylor",
    "thomas", "thompson", "torres", "turner", "walker", "wallace",
    "walsh", "ward", "watson", "williams", "wilson", "wood", "wright",
    "young", "zimmer",
)


def make_username(
    rng: random.Random,
    first: str,
    last: str,
    used: set[str],
) -> str:
    candidates = (
        f"{first}{last}",
        f"{first}_{last}",
        f"{first}{last[0]}",
        f"{first[0]}{last}",
        f"{first}{rng.randint(10, 999)}",
        f"{first}_{rng.randint(10, 9999)}",
        f"{first}{rng.choice(('a', 'e', 'i', 'o', 'u'))}{last[0]}",
    )

    for candidate in candidates:
        username = candidate.lower()[:30]
        if 2 <= len(username) <= 30 and username not in used:
            used.add(username)
            return username

    while True:
        username = (
            f"{first}{rng.randint(1000, 999999)}"
        ).lower()[:30]
        if username not in used:
            used.add(username)
            return username


def make_display_name(rng: random.Random) -> str:
    first = rng.choice(FIRST_NAMES)
    last = rng.choice(LAST_NAMES)
    return f"{first.capitalize()} {last.capitalize()}"


def make_avatar_url(username: str, display_name: str) -> str:
    seed = f"{username}-{display_name.lower().replace(' ', '-')}"
    return (
        "https://api.dicebear.com/9.x/initials/svg"
        f"?seed={seed}"
    )


def main() -> None:
    rng = random.Random(SEED)

    with SessionLocal() as db:
        existing = set(
            db.scalars(
                select(Profile.username)
            ).all()
        )

    used = {username.lower() for username in existing}
    generated: list[dict[str, str]] = []

    for _ in range(SAMPLE_SIZE):
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        username = make_username(rng, first, last, used)
        display_name = f"{first.capitalize()} {last.capitalize()}"
        avatar = make_avatar_url(username, display_name)

        generated.append(
            {
                "username": username,
                "display_name": display_name,
                "avatar": avatar,
                "visibility": "public",
            }
        )

    print(f"Seed:                 {SEED}")
    print(f"Existing usernames:   {len(existing)}")
    print(f"Generated identities: {len(generated)}")
    print("Database changes:     0")
    print()

    for index, identity in enumerate(generated, start=1):
        print(
            f"{index:03d} | "
            f"{identity['username']:<30} | "
            f"{identity['display_name']:<24} | "
            f"{identity['avatar']}"
        )

    usernames = [item["username"] for item in generated]

    assert len(usernames) == len(set(usernames))
    assert all(2 <= len(username) <= 30 for username in usernames)
    assert all(username[0].isalpha() for username in usernames)
    assert all(
        all(
            character.islower()
            or character.isdigit()
            or character == "_"
            for character in username
        )
        for username in usernames
    )
    assert all(
        1 <= len(item["display_name"]) <= 100
        for item in generated
    )
    assert all(item["visibility"] == "public" for item in generated)

    fingerprint = hashlib.sha256(
        "\n".join(
            f"{item['username']}|{item['display_name']}|{item['avatar']}"
            for item in generated
        ).encode()
    ).hexdigest()

    print()
    print(f"Generator fingerprint: {fingerprint}")
    print("PROTOTYPE: PASS")
    print("Database changes made: 0")


if __name__ == "__main__":
    main()
