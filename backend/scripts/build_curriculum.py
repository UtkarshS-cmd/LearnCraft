"""Build the CBSE Class IX + X curriculum packages and learning roadmaps.

Generates per-subject chapter files keyed by subject_id (so Class IX and
Class X coexist), merges new chapters into the existing Class X files, and
emits a term-wise learning roadmap. Run::

    python scripts/build_curriculum.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CUR = ROOT / "data" / "curriculum"
sys.path.insert(0, str(ROOT))

YEAR = "2026-27"
SRC = "NCERT textbook catalog accessed 2026-09; NCERT syllabus 2026-27"


def blocks(points, example=None, check=None):
    out = [{"type": "text", "text": p} for p in points]
    if example:
        out.append({"type": "example", "text": example})
    if check:
        out.append({"type": "check", "text": check})
    return out


def lesson(prefix, slug, title, summary, objectives, prereq, minutes, difficulty, points, example=None, check=None):
    return {
        "lesson_id": f"{prefix}-l-{slug}", "slug": slug, "title": title, "summary": summary,
        "learning_objectives": objectives, "prerequisites": prereq,
        "estimated_minutes": minutes, "difficulty": difficulty,
        "content_blocks": blocks(points, example, check),
        "source_reference": f"NCERT, {SRC}",
    }


def mcq(qid, prompt, correct, wrong, explanation, difficulty="EASY", marks=1, skill="Apply"):
    options = [{"option_id": "a", "text": correct, "is_correct": True}]
    for i, w in enumerate(wrong):
        options.append({"option_id": chr(98 + i), "text": w, "is_correct": False})
    return {
        "question_id": qid, "difficulty": difficulty, "question_type": "MCQ",
        "marks": marks, "skill": skill, "prompt": prompt, "answer": correct,
        "explanation": explanation, "options": options,
    }


def q_short(qid, prompt, answer, explanation, difficulty="MEDIUM", marks=2, skill="Remember"):
    return {
        "question_id": qid, "difficulty": difficulty,
        "question_type": "SHORT_ANSWER", "marks": marks, "skill": skill,
        "prompt": prompt, "answer": answer, "explanation": explanation,
    }


def chapter(prefix, num, title, slug, summary, lessons, questions):
    return {
        "chapter_id": f"{prefix}-ch-{slug}", "chapter_number": num, "slug": slug,
        "title": title, "summary": summary, "source_reference": f"NCERT, {SRC}",
        "topics": [{
            "topic_id": f"{prefix}-t-{slug}", "slug": slug, "title": title,
            "lessons": lessons, "questions": questions,
        }],
    }


def _kp(text):
    """'Term :: description | Term :: description' -> [(term, description)]."""
    pairs = []
    for part in text.split("|"):
        if "::" in part:
            term, desc = part.split("::", 1)
            pairs.append((term.strip(), desc.strip()))
    return pairs


def expand(prefix, num, title, slug, summary, objectives, terms, example, sig):
    """Expand one compact chapter record into lesson + questions.

    - 1 lesson: overview, objectives, key-term glossary, worked example.
    - 1 concept MCQ per key term (distractors from sibling terms).
    - the hand-written signature MCQ.
    - 1 short-answer definition question.
    """
    pairs = _kp(terms)
    obj = [o.strip() for o in objectives.split(";") if o.strip()]
    points = [
        f"Overview: {summary}",
        "In this chapter you will:",
        *[f"- {o}" for o in obj],
        "Key terms to master:",
        *[f"- {t}: {d}" for t, d in pairs],
    ]
    les = lesson(prefix, slug, title, summary, obj, [], 35, "MEDIUM", points, example,
                 f"Can you explain '{pairs[0][0]}' in your own words?")
    qid = lambda n: f"{prefix}-q-{slug}-{n:03d}"  # noqa: E731
    questions = []
    for i, (term, desc) in enumerate(pairs[:4]):
        others = [t for t, _ in pairs if t != term][:3]
        questions.append(mcq(
            qid(i + 1), f"Which term matches: {desc}?", term, others,
            f"'{term}' is defined as {desc}", skill="Remember"))
    if sig:
        questions.append(mcq(qid(len(questions) + 1), *sig))
    first_term, first_desc = pairs[0]
    questions.append(q_short(
        qid(len(questions) + 1), f"Define '{first_term}'.", first_desc,
        f"{first_term}: {first_desc}"))
    return chapter(prefix, num, title, slug, summary, [les], questions)



# ---------------------------------------------------------------------------
# Chapter records
#
# A record is a compact tuple:
#   (num, slug, title, summary, "obj1; obj2; ...",
#    "Term :: description | Term :: description | ...",
#    example_or_None, mcq_or_None)
#
# Lessons, concept-matching MCQs and short-answer questions are generated from
# the record so every chapter ships with study material and practice items.
# ---------------------------------------------------------------------------

def _kp(text):
    """'Term :: description | Term :: description' -> [(term, description)]."""
    pairs = []
    for part in text.split("|"):
        if "::" in part:
            term, desc = part.split("::", 1)
            pairs.append((term.strip(), desc.strip()))
        else:
            pairs.append((part.strip(), ""))
    return [p for p in pairs if p[0]]


def _objs(text):
    return [o.strip() for o in text.split(";") if o.strip()]


def make_chapter(cls, short, num, slug, title, summary, obj_text, kp_text, example, mcq):
    base = f"cbse-{cls}-{YEAR}-{short}"
    terms = _kp(kp_text)
    objectives = _objs(obj_text)

    # --- lessons -----------------------------------------------------
    concept_points = [f"{t} — {d}" if d else t for t, d in terms]
    l1 = lesson(
        base, slug, title, summary, objectives, [], 25, "FOUNDATION",
        [f"Key idea {i+1}: {p}" for i, p in enumerate(concept_points[:3])],
        example,
        f"Can you explain {terms[0][0]} in your own words without notes?",
    )
    l2 = lesson(
        base, f"{slug}-practice", f"{title} — Practice and Revision",
        f"Consolidate {title.lower()} with a study plan, exam strategy and a quick recap checklist.",
        ["Build a revision routine for this chapter", "Attempt board-style questions with confidence"],
        [slug], 20, "CORE",
        [
            "Study plan: read the concepts lesson, then solve every NCERT exercise question for this chapter before attempting the quiz.",
            "Exam tip: questions from this chapter usually test " + (terms[0][0].lower() if terms else "core definitions") + " — always show your working step by step.",
            "Recap checklist: " + " ".join(f"({i+1}) {t}." for i, (t, _d) in enumerate(terms[:4])),
        ],
        None,
        f"Write two sentences linking {terms[1][0].lower() if len(terms) > 1 else terms[0][0].lower()} to an everyday example.",
    )
    lessons = [l1, l2]

    # --- questions ---------------------------------------------------
    questions = []
    if len(terms) >= 3:
        t0, d0 = terms[0]
        distractors = [d for _t, d in terms[1:3]]
        questions.append(q(
            base, slug, 1, f"Which statement correctly describes {t0.lower()}?",
            d0, distractors, f"{t0}: {d0}",
        ))
        t2, d2 = terms[2]
        wrong_terms = [t for t, _ in terms if t != t2][:3]
        questions.append(q(
            base, slug, 2, f"Which concept is described as: “{d2}”?",
            t2, wrong_terms, f"The description matches {t2}.",
        ))
    if mcq:
        prompt, correct, wrong, expl = mcq
        questions.append(q(base, slug, 3, prompt, correct, wrong, expl, difficulty="MEDIUM"))
    if terms:
        t1, d1 = terms[1] if len(terms) > 1 else terms[0]
        questions.append(q_short(
            base, slug, 4,
            f"Define {t1.lower()} and state its significance in {title.lower()}.",
            d1 or t1, f"A complete answer states the definition and links it to the chapter context.",
        ))

    ch = chapter(base, num, title, slug, summary, lessons, questions)
    return ch

# ---------------------------------------------------------------------------
# Class IX chapter records (NCERT rationalised 2026-27)
# (slug, title, summary, objectives, key_points, example, mcq)
# ---------------------------------------------------------------------------

IX_MATH = [
    ("number-systems", "Number Systems",
     "Rational and irrational numbers, real numbers on the number line, and laws of exponents.",
     "Distinguish rational from irrational numbers; Represent real numbers on the number line; Apply laws of exponents to real numbers",
     "Rational number :: a number expressible as p/q with q ≠ 0; Irrational number :: a number whose decimal expansion is non-terminating and non-recurring; Real number :: the complete set of rational and irrational numbers; Successive magnification :: locating a number by zooming into the number line repeatedly; Laws of exponents :: a^m · a^n = a^(m+n) extend to all real bases",
     "√2 is irrational because its decimal expansion 1.4142135… never terminates or repeats.",
     ("Which of these is an irrational number?", "√2", ["3/4", "0.25", "-7"], "√2 has a non-terminating, non-recurring decimal expansion, so it is irrational.")),
    ("polynomials", "Polynomials",
     "Degrees and types of polynomials, remainder and factor theorems, and algebraic identities.",
     "Identify degrees and types of polynomials; Apply the remainder and factor theorems; Use standard algebraic identities",
     "Polynomial :: an expression with whole-number powers of variables only; Zero of a polynomial :: a value of x where p(x) = 0; Remainder theorem :: p(x) divided by (x − a) leaves remainder p(a); Factor theorem :: (x − a) is a factor of p(x) exactly when p(a) = 0; Identity :: an equation true for every variable value, e.g. (a + b)² = a² + 2ab + b²",

IX_MATH += [
    ("triangles", "Triangles",
     "Congruence rules, inequalities in triangles and the angle sum property.",
     "Apply congruence criteria SAS, ASA, SSS and RHS; Use the angle sum property of triangles; Prove inequalities such as the triangle inequality",
     "Congruent triangles :: triangles equal in shape and size; SAS :: two sides and the included angle fix a triangle; Angle sum property :: interior angles of a triangle add to 180 degrees; Triangle inequality :: any side is shorter than the sum of the other two; Hypotenuse :: the longest side of a right triangle",
     "In triangles ABC and PQR, if AB = PQ, angle A = angle P and AC = PR, the triangles are congruent by SAS.",
     ("Two sides and the included angle of one triangle equal two sides and the included angle of another. The triangles are congruent by…", "SAS", ["AAA", "SSS", "RHS"], "Side-Angle-Side is exactly this pairing.")),
    ("quadrilaterals", "Quadrilaterals",
     "Properties of parallelograms and the midpoint theorem.",
     "State properties of parallelograms; Prove the diagonal properties of rectangles and rhombuses; Apply the midpoint theorem",
     "Parallelogram :: a quadrilateral with both pairs of opposite sides parallel; Diagonal bisects :: each diagonal of a parallelogram bisects it; Rhombus :: a parallelogram with equal sides; Midpoint theorem :: the segment joining midpoints of two sides is parallel to the third side and half of it; Trapezium :: a quadrilateral with exactly one pair of parallel sides",
     "In parallelogram ABCD, diagonal AC divides it into two congruent triangles ABC and CDA.",
     ("The segment joining the midpoints of two sides of a triangle is…", "Parallel to the third side and half its length", ["Equal to the third side", "Perpendicular to the third side", "Twice the third side"], "That is the midpoint theorem.")),
    ("circles", "Circles",
     "Chords, arcs and their distance relationship with the centre.",
     "Prove equal chords subtend equal angles; Relate chord length to distance from the centre; State that the perpendicular from the centre bisects a chord",
     "Chord :: a segment joining two points on a circle; Diameter :: the longest chord through the centre; Equal chords :: chords of equal length subtend equal angles at the centre; Perpendicular bisector :: the perpendicular from the centre to a chord bisects it; Cyclic quadrilateral :: a quadrilateral whose vertices lie on a circle",
     "Chords of equal length in a circle stand at the same distance from the centre.",
     ("Equal chords of a circle subtend…", "Equal angles at the centre", ["Different angles at the centre", "Right angles at the centre", "No fixed angle"], "Equal chords subtend equal angles at the centre.")),
    ("herons-formula", "Heron's Formula",
     "Area of any triangle from its three side lengths.",
     "Compute the semi-perimeter of a triangle; Apply Heron's formula to find area; Use Heron's formula for quadrilaterals split into triangles",
     "Semi-perimeter :: s = (a + b + c) / 2; Heron's formula :: area = sqrt(s(s − a)(s − b)(s − c)); Scalene triangle :: a triangle with all three sides different; Perimeter :: the total boundary length of a figure",
     "For a triangle with sides 3, 4 and 5, s = 6 and the area is sqrt(6 · 3 · 2 · 1) = 6 square units.",
     ("For sides 3, 4, 5 the semi-perimeter s equals…", "6", ["12", "5", "7.5"], "s = (3 + 4 + 5) / 2 = 6.")),
    ("surface-areas-and-volumes", "Surface Areas and Volumes",
     "Surface area and volume of cones, spheres, hemispheres and cylinders.",
     "Compute curved and total surface areas of solids; Find volumes of cones, cylinders, spheres and hemispheres; Combine solids in composite problems",
     "Cone :: a solid with a circular base tapering to an apex; Slant height :: l = sqrt(r² + h²) for a cone; Sphere surface area :: 4πr²; Hemisphere volume :: (2/3)πr³; Cylinder volume :: πr²h",
     "A cone with radius 3 and height 4 has slant height 5 and volume (1/3)π · 9 · 4 = 12π.",
     ("The volume of a cone is what fraction of the cylinder with the same base and height?", "One third", ["One half", "Two thirds", "Equal"], "Cone volume is (1/3)πr²h.")),
    ("statistics", "Statistics",
     "Collecting, organising and representing data; mean, median and mode.",
     "Draw bar graphs, histograms and frequency polygons; Compute the mean of grouped data; Find the median and mode of a data set",
     "Frequency :: the number of times a value occurs; Histogram :: a bar graph for grouped continuous data; Mean :: the sum of values divided by their count; Median :: the middle value of ordered data; Mode :: the most frequent value",
     "For the data 2, 3, 3, 5, 8 the mode is 3, the median is 3 and the mean is 4.2.",
     ("The most frequent observation in a data set is called the…", "Mode", ["Mean", "Median", "Range"], "Mode is defined as the most frequent value.")),

# ---------------------------------------------------------------------------
# Class IX Science (NCERT rationalised 2026-27, 12 chapters)
# ---------------------------------------------------------------------------

IX_SCIENCE = [
    ("matter-in-our-surroundings", "Matter in Our Surroundings",
     "States of matter, change of state and the particle nature of matter.",
     "Describe the particle model of matter; Explain change of state using latent heat; Relate evaporation to cooling",
     "Matter :: anything that has mass and occupies space; Diffusion :: spreading of particles from high to low concentration; Latent heat :: hidden heat that changes state without raising temperature; Sublimation :: solid changing directly to gas; Evaporation :: surface phenomenon causing cooling",
     "Wet clothes dry faster on a windy day because moving air carries away water vapour, speeding evaporation.",
     ("Camphor disappears when kept open because of…", "Sublimation", ["Melting", "Condensation", "Freezing"], "Camphor converts directly from solid to vapour — sublimation.")),
    ("is-matter-around-us-pure", "Is Matter Around Us Pure",
     "Mixtures, solutions, colloids, suspensions and separation techniques.",
     "Distinguish mixtures from pure substances; Identify solutions, colloids and suspensions; Choose suitable separation techniques",
     "Pure substance :: a single kind of particle throughout; Solution :: a homogeneous mixture of solute and solvent; Colloid :: particles too small to see but large enough to scatter light (Tyndall effect); Suspension :: a heterogeneous mixture that settles on standing; Centrifugation :: separation using density differences by spinning",
     "Milk is a colloid — it scatters a beam of light (Tyndall effect) but looks homogeneous.",
     ("Scattering of light by colloid particles is called the…", "Tyndall effect", ["Brownian drift", "Electrolysis", "Sublimation"], "Colloids show the Tyndall effect.")),
    ("atoms-and-molecules", "Atoms and Molecules",
     "Laws of chemical combination, mole concept and formula writing.",
     "State the law of conservation of mass and constant proportions; Write chemical formulae using valency; Apply the mole concept to compute particles and mass",
     "Atom :: the smallest particle of an element taking part in a reaction; Molecule :: a group of atoms bonded together; Atomic mass unit :: 1/12 the mass of a carbon-12 atom; Mole :: 6.022 × 10²³ particles; Molecular formula :: the actual number of atoms of each element in a molecule",
     "Water always has hydrogen and oxygen in a 1:8 mass ratio — the law of constant proportions.",
     ("One mole of a substance contains…", "6.022 × 10²³ particles", ["6.022 × 10²² particles", "22.4 particles", "1000 particles"], "Avogadro's number is 6.022 × 10²³.")),
    ("structure-of-the-atom", "Structure of the Atom",
     "Subatomic particles, atomic models, valency, isotopes and isobars.",
     "Describe Thomson, Rutherford and Bohr models; Define atomic number and mass number; Explain isotopes and isobars with examples",
     "Proton :: a positively charged particle in the nucleus; Neutron :: a neutral nuclear particle; Valency :: the combining capacity of an atom; Isotopes :: atoms of the same element with different mass numbers; Isobars :: atoms of different elements with the same mass number",
     "Carbon-14 and carbon-12 are isotopes: same protons (6), different neutrons.",
     ("Atoms of the same element with different mass numbers are…", "Isotopes", ["Isobars", "Ions", "Allotropes"], "Isotopes differ only in neutron count.")),
    ("the-fundamental-unit-of-life", "The Fundamental Unit of Life",
     "Cell structure, organelles and the cell theory.",
     "State the cell theory; Identify major organelles and their functions; Distinguish plant and animal cells",
     "Cell :: the basic structural and functional unit of life; Plasma membrane :: a selectively permeable boundary; Osmosis :: movement of water across a semipermeable membrane; Mitochondria :: the powerhouse producing ATP; Plastids :: plant organelles including chloroplasts for photosynthesis",
     "Raisins swell in plain water by osmosis — water moves into the higher-concentration cell sap.",
     ("Which organelle is called the powerhouse of the cell?", "Mitochondria", ["Ribosome", "Golgi body", "Lysosome"], "Mitochondria produce ATP, the cell's energy currency.")),
    ("tissues", "Tissues",
     "Plant and animal tissues and their specialisations.",
     "Classify plant tissues into meristematic and permanent; Identify animal tissue types; Relate tissue structure to function",
     "Meristematic tissue :: dividing tissue responsible for plant growth; Xylem :: transports water and minerals upward; Phloem :: transports food in plants; Neuron :: the structural unit of the nervous system; Connective tissue :: supports and links other tissues, e.g. blood and bone",
     "Growth in plant height comes from apical meristem at the shoot tip.",
     ("Which plant tissue transports food made in leaves?", "Phloem", ["Xylem", "Parenchyma", "Cork"], "Phloem carries prepared food to all parts.")),
]
]
     "For p(x) = x³ − 3x² + 4, p(2) = 0, so (x − 2) is a factor.",
     ("What does the remainder theorem state for p(x) divided by (x − a)?", "The remainder is p(a)", ["The remainder is 0", "The remainder is a", "The quotient is p(a)"], "Substituting x = a in p(x) gives the remainder directly.")),
    ("coordinate-geometry", "Coordinate Geometry",
     "The Cartesian plane, plotting points and the quadrant system.",
     "Describe the Cartesian plane and its quadrants; Plot ordered pairs correctly; Read coordinates of a point from a graph",
     "Cartesian plane :: the plane formed by two perpendicular number lines called axes; Origin :: the intersection of the axes, coordinates (0, 0); Abscissa :: the x-coordinate of a point; Ordinate :: the y-coordinate of a point; Quadrant :: one of four regions the axes divide the plane into",
     "The point (−3, 2) lies in quadrant II because x is negative and y is positive.",
     ("In which quadrant does the point (−3, −2) lie?", "Quadrant III", ["Quadrant I", "Quadrant II", "Quadrant IV"], "Both coordinates negative is quadrant III.")),
    ("linear-equations-in-two-variables", "Linear Equations in Two Variables",
     "Solutions of ax + by + c = 0 and their graphs as straight lines.",
     "Identify linear equations in two variables; Find solution pairs; Draw the graph of a linear equation",
     "Linear equation :: an equation of the form ax + by + c = 0 with a, b not both zero; Solution :: an ordered pair (x, y) satisfying the equation; Graph of a linear equation :: always a straight line; Intercept :: the point where the line crosses an axis; Infinitely many solutions :: every point on the line is a solution",
     "For x + 2y = 6, (2, 2) is a solution because 2 + 4 = 6.",
     ("The graph of a linear equation in two variables is always a…", "Straight line", ["Parabola", "Circle", "Pair of points"], "Every solution lies on one straight line.")),
    ("euclids-geometry", "Introduction to Euclid's Geometry",
     "Euclid's definitions, axioms and postulates, and deductive reasoning.",
     "State Euclid's key definitions; Distinguish axioms from postulates; Use Euclid's axioms in simple deductions",
     "Axiom :: a statement accepted without proof across mathematics; Postulate :: an assumption specific to geometry; Fifth postulate :: through a point outside a line exactly one parallel line can be drawn; Theorem :: a statement proven from axioms and earlier results; Point :: that which has no part, per Euclid",
     "Euclid's first axiom — things equal to the same thing are equal — underlies all equation solving.",
     ("Euclid's fifth postulate is concerned with…", "Parallel lines", ["Circles", "Areas of triangles", "Prime numbers"], "It guarantees exactly one parallel line through an external point.")),
    ("lines-and-angles", "Lines and Angles",
     "Angle pairs from intersecting lines and from a transversal cutting parallel lines.",
     "Classify complementary and supplementary angles; Prove properties of vertically opposite angles; Use angle properties with parallel lines and a transversal",
     "Complementary angles :: two angles summing to 90°; Supplementary angles :: two angles summing to 180°; Vertically opposite angles :: equal angles opposite each other when two lines intersect; Transversal :: a line crossing two or more lines; Corresponding angles :: equal angles in matching positions on parallel lines",
     "Co-interior angles between parallel lines always sum to 180°.",
     ("Two angles measuring 60° and 30° are…", "Complementary", ["Supplementary", "Vertically opposite", "Reflex"], "Their sum is exactly 90°, so they are complementary.")),
]
