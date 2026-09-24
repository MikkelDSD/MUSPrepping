"""Phrase library and generator for warm, specific recognition ("ros") in MUS.

Pure Python, no database access: the routes look up strengths/highlights and pass them in.
All phrases use `{navn}` (the employee's first name) and highlight phrases also `{titel}`.
"""

import random

TONES = {
    "varm": {
        "label": "Varm",
        "openers": [
            "Kære {navn}. Inden vi taler om fremtiden, vil jeg gerne starte med at sige tak – for alt det, du er og gør her hos os.",
            "{navn}, jeg har glædet mig til den her samtale, fordi den giver mig en god anledning til at fortælle dig, hvor meget du betyder for os.",
            "Det første, jeg gerne vil sige i dag, {navn}, er, at jeg sætter virkelig stor pris på dig.",
        ],
        "closers": [
            "Du skal vide, at du gør en forskel hver eneste dag – og at det bliver set. Tak fordi du er en del af holdet.",
            "Jeg er oprigtigt glad for, at du er her, {navn}. Du gør vores arbejdsplads til et bedre sted at være.",
            "Tak for dit hjerte, din indsats og din måde at være kollega på. Det betyder mere, end du måske tror.",
        ],
    },
    "begejstret": {
        "label": "Begejstret",
        "openers": [
            "{navn}, sikke et år du har haft! Jeg er ærligt talt imponeret, og det vil jeg gerne fortælle dig lige fra start.",
            "Jeg bliver helt i godt humør af at forberede den her samtale, {navn} – der er så meget godt at sige!",
            "Lad mig bare sige det med det samme, {navn}: Du har været fantastisk.",
        ],
        "closers": [
            "Jeg glæder mig vildt til at se, hvad du finder på næste år. Bliv ved med at være præcis dig!",
            "Du er en gave for teamet, {navn} – og jeg er stolt over at være din leder.",
            "Kæmpe tak for din indsats. Du løfter os alle sammen!",
        ],
    },
    "rolig": {
        "label": "Rolig og anerkendende",
        "openers": [
            "{navn}, jeg vil gerne bruge lidt tid på at se tilbage på det forløbne år sammen med dig – for der er meget, jeg har lagt mærke til og sætter pris på.",
            "Når jeg ser tilbage på året, {navn}, står det klart for mig, hvor solidt et bidrag du har leveret.",
            "Tak fordi du tager dig tid til den her samtale, {navn}. Jeg vil gerne begynde med det, jeg synes, du gør rigtig godt.",
        ],
        "closers": [
            "Jeg vil gerne sige tak for din indsats og din stabilitet. Den er værdifuld – for teamet og for mig.",
            "Du skal vide, at dit arbejde bliver værdsat. Det er en fornøjelse at have dig med.",
            "Tak, {navn}. Du er en vigtig del af det, vi lykkes med.",
        ],
    },
}

DEFAULT_TONE = "varm"

STRENGTH_PHRASES = {
    "samarbejde": [
        "Du gør dem omkring dig bedre – folk søger dig, fordi du lytter og løfter i flok.",
        "Du er limen i teamet. Når vi lykkes sammen, er det ofte fordi, du har bygget bro mellem folk.",
        "Din måde at samarbejde på skaber tryghed. Man ved, at man står stærkere, når du er med.",
    ],
    "hjaelpsomhed": [
        "Du er altid klar til at give en hånd, også når du selv har travlt – det lægger alle mærke til.",
        "Dine kolleger ved, at de kan komme til dig. Den generøsitet er guld værd.",
        "Du hjælper uden at gøre det til et stort nummer, og netop derfor betyder det så meget.",
    ],
    "positiv_energi": [
        "Du bringer en energi med dig, der smitter – rummet bliver lysere, når du kommer ind.",
        "Selv på de travle dage holder du humøret oppe, og det gør en kæmpe forskel for stemningen.",
        "Din positive tilgang giver os andre mod på opgaverne.",
    ],
    "humor": [
        "Din humor gør hverdagen lettere. Et godt grin på det rigtige tidspunkt er virkelig værdifuldt.",
        "Du har en fantastisk evne til at finde det sjove i situationen – og det samler teamet.",
    ],
    "faglighed": [
        "Din faglighed er i top. Når der skal findes et solidt svar, er du en af dem, vi vender os mod.",
        "Du leverer arbejde af høj kvalitet, og man kan mærke, at du tager dit fag alvorligt.",
        "Din dybe viden er en tryghed for os alle – og du deler den gavmildt.",
    ],
    "laeringslyst": [
        "Din nysgerrighed og lyst til at lære er inspirerende. Du står aldrig stille.",
        "Du tager nye ting til dig med en imponerende åbenhed, og det flytter også os andre.",
        "Det er en fornøjelse at se, hvordan du hele tiden udvikler dig.",
    ],
    "kreativitet": [
        "Du ser muligheder, hvor andre ser forhindringer – dine idéer har gjort en reel forskel.",
        "Din kreativitet giver os nye vinkler og friske løsninger. Tak for, at du tør tænke anderledes.",
        "Du har et særligt blik for, hvordan tingene kan gøres smartere og bedre.",
    ],
    "overblik": [
        "Du har et fantastisk overblik. Når det hele snurrer, er du den, der holder styr på trådene.",
        "Din struktur og dit overblik giver ro til hele teamet.",
        "Du ser helheden og husker detaljerne – det er en sjælden kombination.",
    ],
    "initiativ": [
        "Du venter ikke på, at nogen siger til – du ser, hvad der skal gøres, og tager fat.",
        "Dit initiativ har sat mange gode ting i gang. Det er præcis den slags drivkraft, vi har brug for.",
        "Du tager ejerskab, og det mærkes i alt, hvad du rører ved.",
    ],
    "paalidelighed": [
        "Man kan altid regne med dig. Når du siger, at noget bliver gjort, så bliver det gjort.",
        "Din pålidelighed er et fundament, som resten af teamet kan bygge på.",
        "Du er stabil som en klippe, og det giver os alle sammen ro i maven.",
    ],
    "mod": [
        "Du tør sige tingene, som de er – med respekt og omtanke. Det gør os klogere.",
        "Du går ikke af vejen for de svære opgaver, og det kræver mod. Det har jeg stor respekt for.",
        "Du har turdet prøve nyt, selv når det var usikkert – det er modigt og beundringsværdigt.",
    ],
    "kundefokus": [
        "Du har altid kunden for øje, og det kan mærkes i de tilbagemeldinger, vi får.",
        "Den omhu, du viser over for dem, vi er her for, gør os stolte.",
        "Du forstår, hvad der virkelig betyder noget for kunderne – og du leverer på det.",
    ],
    "ledelse": [
        "Du går forrest og viser vejen – ikke med store ord, men med dit eksempel.",
        "Andre ser op til dig, og du bruger den tillid klogt og varmt.",
        "Du tager ansvar for helheden og hjælper andre med at vokse. Det er ægte lederskab.",
    ],
}

GENERIC_PHRASES = [
    "Du bidrager med noget helt særligt, som jeg er rigtig glad for at have på holdet.",
    "Jeg sætter stor pris på din indsats og din måde at gå til opgaverne på.",
    "Du har været en vigtig del af det, vi har skabt sammen i år.",
]

HIGHLIGHT_INTROS = [
    "Og så er der nogle konkrete ting, jeg især gerne vil fremhæve:",
    "Jeg har også lagt mærke til nogle helt konkrete ting:",
    "Lad mig nævne et par øjeblikke, der står tydeligt for mig:",
]

HIGHLIGHT_PHRASES = [
    "{titel} – det gjorde en reel forskel for teamet.",
    "{titel}. Det var flot arbejde, og det blev bemærket.",
    "{titel} – det viste virkelig, hvad du kan.",
    "{titel}. Tak for den indsats!",
]

APPRECIATIVE_QUESTIONS = [
    "Hvad er du mest stolt af fra det seneste år?",
    "Hvornår har du haft det allerbedst på arbejdet – og hvad var det, der gjorde det så godt?",
    "Hvilke opgaver giver dig energi?",
    "Hvad sætter du mest pris på ved dine kolleger?",
    "Hvis du kunne bestemme, hvad ville du så gerne lære mere om det næste år?",
    "Hvad kan jeg som leder gøre mere af – eller mindre af – for at støtte dig?",
    "Hvor ser du dig selv om et par år, og hvordan kan vi hjælpe dig derhen?",
    "Er der noget, du går og bærer på, som du gerne vil tale om?",
]


def first_name(name: str) -> str:
    return name.strip().split()[0] if name and name.strip() else "du"


def generate_praise(
    name: str,
    strengths: list[dict],
    highlights: list[dict] | None = None,
    tone: str = DEFAULT_TONE,
    seed: int | None = None,
) -> dict:
    """Compose a warm recognition text.

    `strengths` are dicts with a `key` (see STRENGTH_PHRASES); `highlights` dicts with a `title`.
    The same `seed` always yields the same text, so "Ny variant" is just a new seed.
    """
    rng = random.Random(seed)
    tone_key = tone if tone in TONES else DEFAULT_TONE
    t = TONES[tone_key]
    navn = first_name(name)

    paragraphs = [rng.choice(t["openers"]).format(navn=navn)]

    body = [rng.choice(STRENGTH_PHRASES[s["key"]]) for s in strengths if s.get("key") in STRENGTH_PHRASES]
    if not body:
        body = [rng.choice(GENERIC_PHRASES)]
    paragraphs.append(" ".join(body))

    if highlights:
        phrases = rng.sample(HIGHLIGHT_PHRASES, k=len(HIGHLIGHT_PHRASES))
        lines = [
            phrases[i % len(phrases)].format(titel=h["title"].strip().rstrip("."))
            for i, h in enumerate(highlights)
        ]
        paragraphs.append(rng.choice(HIGHLIGHT_INTROS) + "\n" + "\n".join(f"• {line}" for line in lines))

    paragraphs.append(rng.choice(t["closers"]).format(navn=navn))

    return {"tone": tone_key, "paragraphs": paragraphs, "text": "\n\n".join(paragraphs)}


def conversation_questions(count: int = 5, seed: int | None = None) -> list[str]:
    """A handful of appreciative-inquiry questions for the conversation guide."""
    rng = random.Random(seed)
    return rng.sample(APPRECIATIVE_QUESTIONS, k=min(count, len(APPRECIATIVE_QUESTIONS)))
