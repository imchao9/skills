# Presentation Platform References

Use this file when the user asks to compare or draw inspiration from Adobe, Google Slides, Microsoft PowerPoint, Canva, Pitch, Beautiful.ai, Slidesgo, or similar presentation platforms.

## Adobe Express

Official references:

- Presentation templates: `https://www.adobe.com/express/templates/presentation`
- Presentation maker: `https://www.adobe.com/express/create/presentation`
- Presentation workflow help: `https://helpx.adobe.com/express/web/documents-and-presentations/manage-pages.html`
- Pitch/presentation guidance: `https://www.adobe.com/uk/express/discover/how-to/presentation`

What to borrow:

- Template-first speed for social, marketing, pitch, and lightweight business presentations.
- Brand assets: logo, fonts, colors, imagery.
- Strong visual treatment for public-facing pages and non-technical storytelling.
- Export-oriented workflow: PowerPoint or PDF output from a browser tool.

CM usage:

- Good inspiration for external promotional HTML and quick pitch pages.
- Do not use as the main model for internal technical review; Adobe-style templates often optimize for visual polish before technical evidence.

## Google Slides

Official references:

- Product page: `https://workspace.google.com/products/slides/`
- Tips for great presentations: `https://support.google.com/a/users/answer/9282978`
- Template/theme help: `https://support.google.com/docs/answer/1705254`
- Workspace template update: `https://workspaceupdates.googleblog.com/2024/11/new-templates-in-google-slides.html`

What to borrow:

- Collaboration-first workflow: comments, action items, sharing controls, team co-editing.
- Theme builder: reusable layouts, consistent logo, colors, text size.
- Template library organized by use case: sales pitch, roadmap, lesson plan, workshop, team activity.
- Standardized organization templates.

CM usage:

- Good model for reusable profile installation and team-editable artifacts.
- For collaborative client/team workflows, export or import into Google Slides after generating a high-quality local PPTX.

## Microsoft PowerPoint + Copilot

Official references:

- PowerPoint Designer: `https://support.microsoft.com/en-us/powerpoint/create-professional-slide-layouts-with-designer`
- Copilot presentation designer: `https://powerpoint.cloud.microsoft/create/en/ai-presentation-designer/`
- Create with Copilot: `https://support.microsoft.com/en-us/powerpoint/copilot/create-a-new-presentation-with-copilot-in-powerpoint`
- Keep presentations on-brand with Copilot: `https://support.microsoft.com/en-us/powerpoint/copilot/keep-your-presentation-on-brand-with-copilot`
- Pitch deck templates: `https://powerpoint.cloud.microsoft/create/en/pitch-deck-templates/`

What to borrow:

- Formal PPTX delivery expectations.
- Brand-kit and organization-template alignment.
- Designer-assisted layout cleanup.
- Native PPT compatibility, object editability, and distribution.

CM usage:

- Use for final PPTX output after CM structure and style are stable.
- For Codex, prefer the `Presentations` plugin as the implementation layer for serious PPTX, not ad hoc python-pptx.

## Canva

Official references:

- Presentations: `https://www.canva.com/presentations/`
- Professional templates: `https://www.canva.com/presentations/templates/professional/`
- Pitch deck templates: `https://www.canva.com/presentations/templates/pitch-deck/`
- Brand guidelines templates: `https://www.canva.com/presentations/templates/brand-guidelines/`
- AI presentations: `https://www.canva.com/create/ai-presentations/`

What to borrow:

- Fast visual exploration and broad template variety.
- Brand guideline presentation patterns.
- Social/media-friendly visual language.
- AI-generated first drafts for non-technical storytelling.

CM usage:

- Good for moodboard and external promo references.
- Avoid overusing Canva-style decorative template language for technical review decks.

## Pitch

Official reference:

- `https://pitch.com/`

What to borrow:

- Team presentation workspace framing.
- AI workflow focused on on-brand slides, collaboration, and polished business decks.
- Modern SaaS-like visual language.

CM usage:

- Good reference for external SaaS/product presentation flows.
- Useful mental model: prompt -> presentation -> brand-consistent collaboration.

## Beautiful.ai

Official references:

- Templates: `https://www.beautiful.ai/presentations`
- Slide templates: `https://www.beautiful.ai/slide-templates`
- Presentation software: `https://www.beautiful.ai/presentation-software`

What to borrow:

- Smart slide constraints that prevent broken spacing and alignment.
- Guided workflow: outline -> design -> refine.
- Structural template categories: title, agenda, table, Gantt, flowchart, comparison, chart.
- Brand control and global consistency.

CM usage:

- Strong reference for automatic layout constraints and static scoring.
- For `cm-presentation-style`, add checks that mimic smart-slide behavior: density, alignment, title length, diagram area, repeated layout balance.

## Slidesgo / SlidesCarnival

References:

- Slidesgo: `https://slidesgo.com/`
- SlidesCarnival: `https://www.slidescarnival.com/`

What to borrow:

- Large theme library for mood exploration.
- Good examples of section dividers, agenda pages, education layouts, and simple pitch templates.

CM usage:

- Use only as visual moodboard input.
- Do not treat downloaded templates as quality proof; most still need CM scorecard review.

## Practical Selection

- Internal technical review: CM style + humanize structure + diagrams + html preview; use Presentations only when PPTX is required.
- External promo HTML: CM style + report-inspired layout + real screenshots/product visuals.
- Client editable deck: CM style + Presentations plugin or PowerPoint route.
- Fast marketing draft: Adobe Express / Canva inspiration, then CM scorecard.
- Team collaboration: Google Slides / Pitch-inspired workflow, with comments and shared templates.
- Auto-layout constraints: Beautiful.ai-inspired static QA and layout rules.

## Key Takeaway

Most platforms compete on templates, collaboration, brand kits, and AI draft speed. CM should compete on a stronger generation discipline:

`source -> claim ledger -> structure -> diagram spec -> style -> render -> screenshot QA -> review scorecard`

Use platform references as inspiration, not as a substitute for evidence and review quality.
