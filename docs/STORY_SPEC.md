# Story spec

Status: draft, 2026-11-07. Written from the Cullionboy Kellys pilot and Mike's review of it. Mike decides what is accepted. Read with `docs/RESEARCH_PRINCIPLES.md` and the "Story voice" section of `CLAUDE.md`.

## Purpose and reader

A family story tells one family's years in a townland to a reader with no genealogy background. It should read as warmly as someone who knows the family telling it, and say nothing the evidence does not support. The evidence stays one tap away in "The records behind this" panel. The story does not argue from it.

## Three rules

1. **Evidence only.** Every name, date, age, place and relationship in the story is in the family's evidence (census, Griffith's, the tree). No speculation, no leads, no open questions on the page.
2. **Warmth comes from the people, not from commentary.** Tell what happened to them, using the human details the evidence already holds. Do not add feeling.
3. **Silence over guessing.** If the evidence does not say, the story does not say. It does not hedge around a gap and does not point at it.

## Voice

- Third person, past tense, plain words, always (Mike, 2026-11-07). The teller is the local seanchai in a rambling house: unhurried, warm, someone who knows these families and tells them to people who do not. The teller never says "I" or "we" and never claims to be a relative.
- People are the subject of sentences: "Bella was head of the house", not "Bella is recorded as head".
- Write for the ear. Short sentences, names repeated rather than pronouns where it keeps people clear, one thing at a time. Read it aloud before accepting it.
- Short paragraphs of two to four sentences. One move per paragraph. Chronological order.
- A reader who knows nothing about records should never need to learn what a census, a valuation or a GEDCOM is.
- Each family leads with one or two sentences that give its span in the townland.

## Names, dates and numbers

- Full name at first mention, then first names within a family. Use the name the person used (Rose) and give the recorded forms once, plainly ("Rosanna on her birth record and Rose Anne on the census form").
- Spellings as recorded. Where one family appears under several spellings and Mike has verified them as one, say so once ("her name is also written Carr").
- Full dates for weddings, deaths and registrations. Years only for the rest. "About" for estimated years and for ages that drift between returns. Ages in words inside sentences ("thirteen"), figures in dates.
- Land in the units of the source (twenty-two acres). Townland names as the sources spell them.
- Use only links Mike has accepted. An unaccepted link between two records is not mentioned.

## Where the warmth comes from

Use the small human facts the evidence holds, and place them well.

- A wedding on the bride's thirty-first birthday.
- Sons named for their grandfathers.
- Children born at their grandmother's house rather than their own.
- A birth registered on the day the grandmother died.
- A father's death a few months before the census that finds his widow heading the house.

Other techniques: concrete counts ("four grown sons were at home"), letting the order of events carry the weight, and ending on a fact rather than a lesson.

## What stays out

- Speculation and its softeners: "tempting to think", "probably", "it seems".
- Oral-tradition asides ("as the family told it") and any "family always said".
- Leads and open questions. The project presents evidence and does not chase leads.
- Source talk: "the records show", "is recorded as", "the census taker", IDs, citations, confidence, match language.
- Feeling words ("sadly", "tragically"), rhetorical questions, morals.
- Anyone Mike has not cleared for privacy. Causes of death are given only when recorded plainly and the death is over 50 years old.

## Uncertainty and conflict

The page does not carry them. They live in the records panel and in the townland `STATUS.md`, where Mike can see them, and the story states only what is accepted. Age drift is expressed with "about". Where two accepted records disagree on something the story needs, it takes the figure the evidence supports best and leaves the other out. The disagreement goes in `STATUS.md`. Nothing is silently resolved: the decision is recorded.

## Shape of a family story

1. **Lead.** The family's span in the townland.
2. **Beginnings.** The earliest evidence: a Griffith's holding, or the earliest person in the tree.
3. **Marriage and household.** Who married whom, where, and who lived in the house.
4. **Children.** Who they were, where born, how many lived.
5. **Turning points.** Deaths, and departures only where the evidence shows them.
6. **The later generation.** The latest evidence held, ending on a plain fact.

Length follows the evidence. More sources give a longer story, and a thin family gets a short one with no padding. The Kellys are close to the longest so far, and a few other families may match or pass them. There is no fixed cap.

Reach follows the evidence too. A story goes as far past 1926 as the family's evidence takes it. Mike checks privacy before anything is added to the source GEDCOM, so the story uses what the data holds. The 100/75/50 check in `tools/validate.py` stays as an automatic backstop, and Mike overrides it in `privacy_overrides.csv` where he has judged otherwise.

## Evidence tiers

- **Tree-backed.** The full shape above. Pilot: the Kellys.
- **Census chain.** Where Mike has accepted links between returns, the story follows each person across them: "Ellen was twelve in 1901, twenty-two in 1911 and still at home in 1926". No marriages or deaths unless a source states them.
- **One return only.** A short account of the household in that year, and nothing about before or after.
- **No authored story.** The generated surname plate, which states only what the returns record.

## Reference passages

Before (census report):

> Thomas Kelly (60) and Margaret headed the household in 1901 with four adult sons: Thomas, Joseph, John and James. By 1911 Thomas and Marget are 74, Joseph (35) is married to Bella (32) and John Patrick (30) is single.

After (family story):

> Joseph was thirty-four when he married Isabella McGettigan, known as Bella, at St Patrick's Church in Donegal town on 6 February 1910. It was her thirty-first birthday. She was from Druminnin, the daughter of Hugh McGettigan and Mary McAna. By 1911 she was living in Cullionboy with Joseph, his parents and his brother John Patrick.

The full approved passage is the Kellys plate in `townlands/cullionboy/content.json`.

## Review checklist

- Is every fact in the family's evidence, and every link accepted?
- Does any sentence guess, hedge around a gap, or point at a lead?
- Does any sentence talk about sources, records, matching or the tree?
- Is the warmth carried by a fact, not an adjective?
- Has Mike cleared everyone named, and does the validator pass?
- Does it read aloud like a person talking, with no genealogy terms?
- Any conflict or gap noticed has been written to `STATUS.md`, not the page.

## Absence and departure

Absence from a return is not told as a departure. A person who is not in a house in a later return is simply not mentioned there. A departure, emigration or death is told only when a source states it. When Mike has the evidence he adds it to the source GEDCOM files, and the story then tells it.

## Photographs

The story refers to a family's photographs where they add to it, in the same plain voice: "There is a photograph of Bella with her daughters Rose and Mary Kate." It states only what the caption and the datasets hold: who is named, never who is where, and no date or age unless the media record carries one. Photographs are shown beside the story on the family's Photos tab (`docs/MEDIA_SPEC.md`).

Proposed, for Mike to confirm: do not build per-person tagging now. The caption names the people, and the `family` column places the photograph on the right plate. Fill `people_shown` only when it adds something the caption does not, such as which person is which, and only when Mike supplies it. Add person-level links to the tree later if a photograph has to appear under more than one family or beside one person's paragraph.

## Settled 2026-11-07

1. Third person always, in the voice of a seanchai in a rambling house.
2. Go as far as the evidence takes. Mike does the privacy check before adding evidence.
3. Departures and absences are told only where there is evidence.
4. Length is driven by the evidence.
5. Photographs are referred to in the story. Tagging is proposed above and not yet decided.

## Later

A fact sheet per family, and a check that fails any date, name, age or place in a story that is not in the fact sheet, are specified separately with the census GEDCOM design.
