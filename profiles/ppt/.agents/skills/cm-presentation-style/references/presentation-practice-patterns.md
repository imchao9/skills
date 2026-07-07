# Presentation Practice Patterns

Use these practices as a quality baseline for CM-style internal technical decks, formal PPTX deliverables, and external promotional HTML presentations.

## Source References

- MIT Communication Lab, Technical Presentation: `https://mitcommlab.mit.edu/meche/commkit/technical-presentation/`
- PLOS Computational Biology, Ten simple rules for effective presentation slides: `https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1009554`
- Harvard Catalyst, Slides / assertion-evidence guidance: `https://catalyst.harvard.edu/writing-communication-center/visualize-science/slides/`
- TED Blog, 10 tips for better slide decks: `https://blog.ted.com/10-tips-for-better-slide-decks/`
- Duarte, slide design tips: `https://www.duarte.com/blog/perfect-your-slide-design/`
- Harvard Digital Accessibility, Create Accessible PowerPoint Presentations: `https://accessibility.huit.harvard.edu/microsoft-powerpoint`
- Section508.gov, Accessible Presentations: `https://www.section508.gov/create/presentations/`

## Practice 1: Structure Before Slides

Do not start with templates.

Create:

- goal: decision, training, persuasion, report, demo.
- audience map: what each reviewer or viewer cares about.
- state shift: what the audience believes before and after.
- argument map: problem, principle, option, tradeoff, risk, acceptance.
- slide plan: one role per slide.

MIT emphasizes that presentations move linearly in time, so the content order must be planned before slide design.

## Practice 2: One Idea Per Slide

Each slide needs one central claim or question.

Use the title as the claim, not a generic label:

- Weak: `Architecture`
- Strong: `验证码规则接口是登录链路和风控决策的稳定契约`

If one slide needs two conclusions, split it.

## Practice 3: Assertion + Evidence

Use assertion-evidence structure for technical slides:

- headline states the message.
- visual evidence supports it: diagram, chart, screenshot, table, code path, log excerpt.
- labels and captions explain how to read the evidence.

Avoid bullet-only slides unless the slide is a checklist, agenda, or decision list.

## Practice 4: Make Slides Support Speech, Not Replace It

Visible text should guide attention. It should not duplicate the speaker note.

Use:

- concise headline.
- 1 dominant visual or table.
- short labels.
- speaker notes for nuance.

TED and PLOS both warn that text-heavy slides split attention between reading and listening.

## Practice 5: Use Visual Hierarchy Deliberately

Before styling, define the scan order:

1. title or main claim.
2. dominant evidence.
3. supporting annotation.
4. footer/source.

Use size, position, weight, spacing, and one accent color to enforce that order. If the eye does not know where to start, the slide fails.

## Practice 6: Evidence Must Be Inspectable

For technical and product work, prefer real artifacts:

- architecture diagram.
- flow diagram.
- screenshot.
- metric.
- code/log excerpt.
- before/after comparison.

Avoid decorative stock imagery when the audience needs to inspect the actual product, system, or result.

## Practice 7: Plan for Questions

For technical review decks, add hidden or appendix material for expected challenges:

- why not alternative X.
- performance boundary.
- security/privacy impact.
- rollback.
- test plan.
- cost and operational ownership.

Do not overload the core deck with every possible objection; route objections into appendix or speaker notes.

## Practice 8: Accessibility Is Part of Quality

At minimum:

- unique descriptive slide titles.
- readable sans-serif text.
- high contrast.
- do not use color alone to convey meaning.
- alt text or textual equivalents for meaningful images in distributable PPTX/HTML.
- logical reading order for PPTX.

For projected decks, body text should generally be 18pt or larger in PPTX, and HTML screenshots must be readable at presentation distance.

## Practice 9: Keep Motion and Effects Subordinate

Use animation only to reveal sequence or reduce cognitive load.

Avoid:

- decorative page transitions.
- moving elements that do not teach sequence.
- critical content hidden behind unsupported animation.

For important external deliverables, keep a static fallback screenshot or PDF.

## Practice 10: QA Must Include Meaning, Not Only Rendering

Renderer QA:

- no broken images.
- no overflow or overlap.
- correct dimensions.
- screenshots for every page.

Review QA:

- is the goal clear?
- is each slide one idea?
- is the claim supported by evidence?
- can a distracted viewer get the takeaway?
- can the speaker naturally present it?
- can claims be traced to source or assumptions?

## CM Operating Rule

The best CM-style deck is not the prettiest deck. It is the deck where reviewers know:

- what decision is needed.
- what evidence supports it.
- what risks remain.
- what happens next.

For external HTML, replace "decision" with "next action", but keep the same evidence discipline.
