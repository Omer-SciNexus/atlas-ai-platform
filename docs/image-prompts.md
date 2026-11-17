# Atlas image prompts

Every image the Atlas project needs, with the full prompt for OpenAI image generation.
Each prompt is complete: copy the text block, paste it into ChatGPT or the API, and save the result at the path given.

## Rules

- **Format:** PNG. File names are lowercase-with-dashes.
- **Two places:**
  - `docs/assets/` holds images for the README, docs, case study and social media.
  - `apps/web/public/images/` holds images the web app shows. Next.js serves this folder at `/images/...`.
- **API settings:** `model="gpt-image-1"`, `quality="high"`. Use the `size` and `background` given for each image.
- **"Crop to"** means: generate at the given size, then crop or resize to the final size (Figma, Canva, Photopea or Paint).
- **Text:** none of the images contain text. Add titles later in Figma or Canva.
- **Don't generate these with AI:** the architecture diagram, eval charts, app screenshots and ADR diagrams. They must be real.

## Folder map

```
docs/assets/
├── brand/
│   ├── atlas-logo.png                 #1
│   └── atlas-logo-white.png           #2
├── readme/
│   ├── atlas-hero-banner.png          #3
│   └── atlas-social-preview.png       #4
├── case-study/
│   ├── rag-citations.png              #5
│   ├── multi-tenant-isolation.png     #6
│   ├── agents-human-approval.png      #7
│   ├── evals-guardrails.png           #8
│   └── nl-to-sql.png                  #9
├── marketing/
│   ├── linkedin-post-cover.png        #10
│   ├── linkedin-profile-banner.png    #11
│   └── demo-video-thumbnail.png       #12
└── blog/
    ├── phase-1-basic-rag.png          #13
    ├── phase-2-advanced-rag-evals.png #14
    ├── phase-3-llm-gateway.png        #15
    ├── phase-4-agents-mcp.png         #16
    ├── phase-5-nl-to-sql.png          #17
    ├── phase-6-security.png           #18
    └── phase-7-aws-deploy.png         #19

apps/web/public/images/
├── brand/
│   ├── atlas-logo.png                 (copy of #1)
│   └── atlas-logo-white.png           (copy of #2)
├── avatar/
│   └── ai-assistant.png               #20
├── backgrounds/
│   └── login-background.png           #21
├── empty-states/
│   ├── no-documents.png               #22
│   ├── no-conversations.png           #23
│   ├── waiting-approval.png           #24
│   └── no-access.png                  #25
├── errors/
│   └── not-found.png                  #26
└── tenants/
    ├── demo-tenant-a-logo.png         #27
    └── demo-tenant-b-logo.png         #28

apps/web/app/
├── icon.png                           (resize #1 to 512x512)
└── apple-icon.png                     (resize #1 to 180x180)
```

---

## Brand

### #1 Logo

- **Save as:** `docs/assets/brand/atlas-logo.png` (also copy to `apps/web/public/images/brand/atlas-logo.png`)
- **Size:** 1024x1024 · **Background:** transparent

```text
Create a minimal logo mark for an enterprise AI platform called "Atlas".
The idea: a simple globe made of a few clean curved meridian lines, with one
small glowing node on it connected by thin lines, like a knowledge network.
The outer shape of the globe also looks like a shield, to suggest trust and
security. Geometric, symmetric, balanced. It must stay clear and readable at
small sizes such as a 32px favicon, so use solid flat shapes, thick enough
lines and at most 3 colors: electric indigo (#4F46E5), teal (#14B8A6) and
deep navy (#0B1B3A). Centered, with generous padding, on a fully transparent
background. Flat vector style, modern and professional, like a fintech or
security company logo. No text, no letters, no numbers, no extra elements,
no shadows, no watermarks.
```

### #2 Logo, white version (for dark backgrounds)

- **Save as:** `docs/assets/brand/atlas-logo-white.png` (also copy to `apps/web/public/images/brand/atlas-logo-white.png`)
- **Size:** 1024x1024 · **Background:** transparent
- **How:** in ChatGPT, upload `atlas-logo.png` first, then paste this prompt.

```text
Recreate exactly this same logo mark, with the same shape, proportions and
details, but make every part solid pure white (#FFFFFF). Keep the background
fully transparent. Do not add, remove or change any element. No text, no
shadows, no outlines in other colors.
```

---

## README and GitHub

### #3 README hero banner

- **Save as:** `docs/assets/readme/atlas-hero-banner.png`
- **Size:** 1536x1024 · **Crop to:** 1600x600 (keep the center and right side)

```text
A wide hero illustration for an enterprise AI knowledge platform. In the
center-right, a glowing translucent sphere made of connected nodes, like a
knowledge graph. Floating around it: abstract document cards that look like
financial reports (horizontal lines that stand for text, and small bar
charts), one database cylinder, and one chat bubble. Thin glowing light paths
connect every object to the sphere, like data flowing in. A soft, faint
shield shape surrounds the sphere to suggest security. Deep navy background
with a very faint grid pattern. Keep the left third of the image almost
empty, plain dark navy, for a title that will be added later.
Style: modern, clean, professional tech illustration. Flat vector with soft
depth and subtle gradients. Color palette: deep navy (#0B1B3A), electric
indigo (#4F46E5), teal (#14B8A6), soft white (#F8FAFC), with small amber
(#F59E0B) accents. Lots of empty space, simple geometric shapes, thin clean
lines, soft glow on key elements. Calm, trustworthy, enterprise feel, like a
fintech or security company. No text, no letters, no numbers, no real brand
logos, no watermarks, no human faces.
```

### #4 GitHub social preview

- **Save as:** `docs/assets/readme/atlas-social-preview.png`
- **Size:** 1536x1024 · **Crop to:** 1280x640
- **Upload:** GitHub repo, then Settings, then Social preview.

```text
A wide banner image. On the right half, an isometric view of a secure digital
vault made of glowing stacked platforms. Each platform is one separate
customer space, each in a slightly different tint (indigo, teal, amber), and
they are clearly separated by thin glass walls. Small AI agent icons, shown as
simple glowing orbs, travel between the platforms only along glowing approved
paths. The left half of the image is plain dark navy with a soft gradient,
empty, for a project title that will be added later.
Style: modern, clean, professional tech illustration. Flat vector with soft
depth and subtle gradients. Color palette: deep navy (#0B1B3A), electric
indigo (#4F46E5), teal (#14B8A6), soft white (#F8FAFC), with small amber
(#F59E0B) accents. Lots of empty space, simple geometric shapes, thin clean
lines, soft glow on key elements. Calm, trustworthy, enterprise feel, like a
fintech or security company. No text, no letters, no numbers, no real brand
logos, no watermarks, no human faces.
```

---

## Case study (one image per main feature)

### #5 RAG with citations

- **Save as:** `docs/assets/case-study/rag-citations.png`
- **Size:** 1536x1024

```text
Concept illustration about AI answers that always show their sources. In the
center, one floating AI answer card with a few abstract lines that stand for
text. From the answer card, three thin glowing lines go back to three source
document pages placed around it. On each document page, exactly one short
passage is highlighted in amber, showing the exact place the answer came
from. Dark navy background with a faint grid. Calm, clear, lots of space.
Style: modern, clean, professional tech illustration. Flat vector with soft
depth and subtle gradients. Color palette: deep navy (#0B1B3A), electric
indigo (#4F46E5), teal (#14B8A6), soft white (#F8FAFC), with small amber
(#F59E0B) accents. Lots of empty space, simple geometric shapes, thin clean
lines, soft glow on key elements. Calm, trustworthy, enterprise feel, like a
fintech or security company. No text, no letters, no numbers, no real brand
logos, no watermarks, no human faces.
```

### #6 Multi-tenant isolation

- **Save as:** `docs/assets/case-study/multi-tenant-isolation.png`
- **Size:** 1536x1024

```text
Concept illustration about strong data separation between companies. Three
separate glass boxes stand side by side in a row. Each box has its own soft
tint (indigo, teal, amber) and holds its own small stack of documents and a
small database cylinder. Below them is one shared glowing AI core. The core
connects to each box only through that box's own small locked gate with a
padlock symbol. Nothing passes from one box to another; the walls between
the boxes are clearly solid. Dark navy background, isometric view.
Style: modern, clean, professional tech illustration. Flat vector with soft
depth and subtle gradients. Color palette: deep navy (#0B1B3A), electric
indigo (#4F46E5), teal (#14B8A6), soft white (#F8FAFC), with small amber
(#F59E0B) accents. Lots of empty space, simple geometric shapes, thin clean
lines, soft glow on key elements. Calm, trustworthy, enterprise feel, like a
fintech or security company. No text, no letters, no numbers, no real brand
logos, no watermarks, no human faces.
```

### #7 Agents with human approval

- **Save as:** `docs/assets/case-study/agents-human-approval.png`
- **Size:** 1536x1024

```text
Concept illustration about AI agents that need human approval for important
actions. A glowing path runs from left to right. Along it, three glowing AI
agent orbs each do one task, shown by simple icons: a magnifying glass
(search), a small bar chart (analyze) and a document with a pen (write).
Before the last step, the path stops at a checkpoint gate with a large round
check-mark button. A simple stylized human hand (no arm detail, no face)
reaches toward the button to approve. After the gate, the path continues and
glows brighter. Dark navy background.
Style: modern, clean, professional tech illustration. Flat vector with soft
depth and subtle gradients. Color palette: deep navy (#0B1B3A), electric
indigo (#4F46E5), teal (#14B8A6), soft white (#F8FAFC), with small amber
(#F59E0B) accents. Lots of empty space, simple geometric shapes, thin clean
lines, soft glow on key elements. Calm, trustworthy, enterprise feel, like a
fintech or security company. No text, no letters, no numbers, no real brand
logos, no watermarks, no human faces.
```

### #8 Evals and guardrails

- **Save as:** `docs/assets/case-study/evals-guardrails.png`
- **Size:** 1536x1024

```text
Concept illustration about testing AI quality and blocking unsafe answers. A
stream of abstract glowing answer cards flows from left to right through
three thin transparent filter screens. Most cards pass through and turn
teal. A few cards are stopped at a screen and turn amber, each with a small
warning triangle symbol. On the right side, a simple floating dashboard panel
with abstract bar charts and one rising line chart, showing quality going up.
Dark navy background with a faint grid.
Style: modern, clean, professional tech illustration. Flat vector with soft
depth and subtle gradients. Color palette: deep navy (#0B1B3A), electric
indigo (#4F46E5), teal (#14B8A6), soft white (#F8FAFC), with small amber
(#F59E0B) accents. Lots of empty space, simple geometric shapes, thin clean
lines, soft glow on key elements. Calm, trustworthy, enterprise feel, like a
fintech or security company. No text, no letters, no numbers, no real brand
logos, no watermarks, no human faces.
```

### #9 NL-to-SQL

- **Save as:** `docs/assets/case-study/nl-to-sql.png`
- **Size:** 1536x1024

```text
Concept illustration about turning a plain-language question into a database
query. On the left, a chat bubble filled with soft wavy lines that stand for
a spoken question. In the middle, a glowing crystal prism; light from the
chat bubble enters it and comes out as straight, ordered beams. On the right,
the beams reach a structured table grid and a database cylinder, and a small
bar chart rises out of the database as the answer. Clear left-to-right flow.
Dark navy background.
Style: modern, clean, professional tech illustration. Flat vector with soft
depth and subtle gradients. Color palette: deep navy (#0B1B3A), electric
indigo (#4F46E5), teal (#14B8A6), soft white (#F8FAFC), with small amber
(#F59E0B) accents. Lots of empty space, simple geometric shapes, thin clean
lines, soft glow on key elements. Calm, trustworthy, enterprise feel, like a
fintech or security company. No text, no letters, no numbers, no real brand
logos, no watermarks, no human faces.
```

---

## Marketing

### #10 LinkedIn post cover

- **Save as:** `docs/assets/marketing/linkedin-post-cover.png`
- **Size:** 1536x1024 · **Crop to:** 1200x627

```text
An eye-catching but professional cover image. A large glowing knowledge
sphere made of connected nodes floats above a dark, glossy navy surface and
reflects on it. Around the sphere float five small glowing icons: a document
with a magnifying glass, a shield, a round AI orb, a database cylinder and a
cloud. Thin light lines link all of them to the sphere. Cinematic feel, with
soft light coming from above. Keep the top quarter of the image plain and
empty for a headline that will be added later.
Style: modern, clean, professional tech illustration. Flat vector with soft
depth and subtle gradients. Color palette: deep navy (#0B1B3A), electric
indigo (#4F46E5), teal (#14B8A6), soft white (#F8FAFC), with small amber
(#F59E0B) accents. Lots of empty space, simple geometric shapes, thin clean
lines, soft glow on key elements. Calm, trustworthy, enterprise feel, like a
fintech or security company. No text, no letters, no numbers, no real brand
logos, no watermarks, no human faces.
```

### #11 LinkedIn profile banner

- **Save as:** `docs/assets/marketing/linkedin-profile-banner.png`
- **Size:** 1536x1024 · **Crop to:** 1584x396 (take a thin strip from the middle; resize up if needed)

```text
A very wide, calm, abstract banner. All important content sits in a thin
horizontal band across the vertical middle of the image; the top and bottom
are plain dark navy. In that band, a soft line of connected glowing nodes
runs from left to right like a data network, with five small icons placed
along it: a document, a shield, a round AI orb, a database cylinder and a
cloud. Keep the far-left part of the band empty, because a profile photo
will cover it. Subtle and professional, not busy.
Style: modern, clean, professional tech illustration. Flat vector with soft
depth and subtle gradients. Color palette: deep navy (#0B1B3A), electric
indigo (#4F46E5), teal (#14B8A6), soft white (#F8FAFC), with small amber
(#F59E0B) accents. Lots of empty space, simple geometric shapes, thin clean
lines, soft glow on key elements. Calm, trustworthy, enterprise feel, like a
fintech or security company. No text, no letters, no numbers, no real brand
logos, no watermarks, no human faces.
```

### #12 Demo video thumbnail

- **Save as:** `docs/assets/marketing/demo-video-thumbnail.png`
- **Size:** 1536x1024 · **Crop to:** 1280x720

```text
A bold video thumbnail. On the right half, a large glowing knowledge sphere,
and next to it a bright AI answer card connected by glowing lines to two
source documents with amber highlighted passages. Strong contrast: bright
teal and indigo glow against a very dark navy background. Big, simple shapes
that stay clear when the image is small. The left half is plain dark navy,
empty, for a large title that will be added later.
Style: modern, clean, professional tech illustration. Flat vector with soft
depth and subtle gradients. Color palette: deep navy (#0B1B3A), electric
indigo (#4F46E5), teal (#14B8A6), soft white (#F8FAFC), with small amber
(#F59E0B) accents. Simple geometric shapes, thin clean lines, soft glow on
key elements. Trustworthy, enterprise feel, like a fintech or security
company. No text, no letters, no numbers, no real brand logos, no
watermarks, no human faces.
```

---

## Blog headers (one per roadmap phase)

All blog headers: **Size:** 1536x1024 · **Crop to:** 1600x840

### #13 Phase 1: Basic RAG

- **Save as:** `docs/assets/blog/phase-1-basic-rag.png`

```text
A wide blog header image. In the center, a neat stack of abstract document
pages flowing upward, one by one, into a large glowing magnifying-glass lens
that turns them into small glowing points of light. Dark navy background
with a faint grid and soft glow. Keep the top third plain and empty for a
title that will be added later.
Style: modern, clean, professional tech illustration. Flat vector with soft
depth and subtle gradients. Color palette: deep navy (#0B1B3A), electric
indigo (#4F46E5), teal (#14B8A6), soft white (#F8FAFC), with small amber
(#F59E0B) accents. Lots of empty space, simple geometric shapes, thin clean
lines, soft glow on key elements. Calm, trustworthy, enterprise feel, like a
fintech or security company. No text, no letters, no numbers, no real brand
logos, no watermarks, no human faces.
```

### #14 Phase 2: Advanced RAG and evals

- **Save as:** `docs/assets/blog/phase-2-advanced-rag-evals.png`

```text
A wide blog header image. In the center, a round target board with several
glowing teal hits close to the middle, and next to it a set of rising bar
charts with a line chart going up. Dark navy background with a faint grid
and soft glow. Keep the top third plain and empty for a title that will be
added later.
Style: modern, clean, professional tech illustration. Flat vector with soft
depth and subtle gradients. Color palette: deep navy (#0B1B3A), electric
indigo (#4F46E5), teal (#14B8A6), soft white (#F8FAFC), with small amber
(#F59E0B) accents. Lots of empty space, simple geometric shapes, thin clean
lines, soft glow on key elements. Calm, trustworthy, enterprise feel, like a
fintech or security company. No text, no letters, no numbers, no real brand
logos, no watermarks, no human faces.
```

### #15 Phase 3: LLM gateway

- **Save as:** `docs/assets/blog/phase-3-llm-gateway.png`

```text
A wide blog header image. In the center, one large glowing gateway arch.
Many small light streams enter it from the left, and on the right they split
into three clean, separate glowing paths that lead to three different
abstract glowing orbs, like different AI models. Dark navy background with a
faint grid and soft glow. Keep the top third plain and empty for a title
that will be added later.
Style: modern, clean, professional tech illustration. Flat vector with soft
depth and subtle gradients. Color palette: deep navy (#0B1B3A), electric
indigo (#4F46E5), teal (#14B8A6), soft white (#F8FAFC), with small amber
(#F59E0B) accents. Lots of empty space, simple geometric shapes, thin clean
lines, soft glow on key elements. Calm, trustworthy, enterprise feel, like a
fintech or security company. No text, no letters, no numbers, no real brand
logos, no watermarks, no human faces.
```

### #16 Phase 4: Agents and MCP

- **Save as:** `docs/assets/blog/phase-4-agents-mcp.png`

```text
A wide blog header image. In the center, a round glowing central hub. Around
it, five glowing AI orbs are plugged into the hub with clean, neat cables,
and each orb holds a simple tool icon: a document, a database cylinder, a
chat bubble, a calendar and a gear. Dark navy background with a faint grid
and soft glow. Keep the top third plain and empty for a title that will be
added later.
Style: modern, clean, professional tech illustration. Flat vector with soft
depth and subtle gradients. Color palette: deep navy (#0B1B3A), electric
indigo (#4F46E5), teal (#14B8A6), soft white (#F8FAFC), with small amber
(#F59E0B) accents. Lots of empty space, simple geometric shapes, thin clean
lines, soft glow on key elements. Calm, trustworthy, enterprise feel, like a
fintech or security company. No text, no letters, no numbers, no real brand
logos, no watermarks, no human faces.
```

### #17 Phase 5: NL-to-SQL

- **Save as:** `docs/assets/blog/phase-5-nl-to-sql.png`

```text
A wide blog header image. In the center, a chat bubble on the left that
gradually transforms, from left to right, into a clean structured table grid
on the right. The soft wavy lines inside the bubble become straight rows and
columns. Dark navy background with a faint grid and soft glow. Keep the top
third plain and empty for a title that will be added later.
Style: modern, clean, professional tech illustration. Flat vector with soft
depth and subtle gradients. Color palette: deep navy (#0B1B3A), electric
indigo (#4F46E5), teal (#14B8A6), soft white (#F8FAFC), with small amber
(#F59E0B) accents. Lots of empty space, simple geometric shapes, thin clean
lines, soft glow on key elements. Calm, trustworthy, enterprise feel, like a
fintech or security company. No text, no letters, no numbers, no real brand
logos, no watermarks, no human faces.
```

### #18 Phase 6: Security hardening

- **Save as:** `docs/assets/blog/phase-6-security.png`

```text
A wide blog header image. In the center, a large shield made of three
layered glowing rings, one inside another, with a solid padlock in the very
middle. A few small amber sparks hit the outer ring and stop there. Dark
navy background with a faint grid and soft glow. Keep the top third plain
and empty for a title that will be added later.
Style: modern, clean, professional tech illustration. Flat vector with soft
depth and subtle gradients. Color palette: deep navy (#0B1B3A), electric
indigo (#4F46E5), teal (#14B8A6), soft white (#F8FAFC), with small amber
(#F59E0B) accents. Lots of empty space, simple geometric shapes, thin clean
lines, soft glow on key elements. Calm, trustworthy, enterprise feel, like a
fintech or security company. No text, no letters, no numbers, no real brand
logos, no watermarks, no human faces.
```

### #19 Phase 7: AWS deploy

- **Save as:** `docs/assets/blog/phase-7-aws-deploy.png`

```text
A wide blog header image. In the center, several glowing cloud-shaped
platforms stacked like the floors of a modern building, connected by thin
vertical light lines, with small server blocks resting on each floor. Dark
navy background with a faint grid and soft glow. Keep the top third plain
and empty for a title that will be added later.
Style: modern, clean, professional tech illustration. Flat vector with soft
depth and subtle gradients. Color palette: deep navy (#0B1B3A), electric
indigo (#4F46E5), teal (#14B8A6), soft white (#F8FAFC), with small amber
(#F59E0B) accents. Lots of empty space, simple geometric shapes, thin clean
lines, soft glow on key elements. Calm, trustworthy, enterprise feel, like a
fintech or security company. No text, no letters, no numbers, no real brand
logos (no AWS logo), no watermarks, no human faces.
```

---

## Web app

### #20 AI assistant avatar

- **Save as:** `apps/web/public/images/avatar/ai-assistant.png`
- **Size:** 1024x1024 · **Background:** transparent · **Resize to:** 256x256

```text
A small round avatar icon for an AI assistant in a chat app. A soft glowing
orb in electric indigo (#4F46E5) and teal (#14B8A6), with a simple inner
pattern of a few connected nodes, like a tiny globe. Friendly and calm. No
face, no eyes, no mouth, no robot features. Clean, crisp edges that stay
clear at 32px. Centered, filling most of the image, on a fully transparent
background. Flat vector style with a subtle gradient. No text, no letters,
no watermarks.
```

### #21 Login page background

- **Save as:** `apps/web/public/images/backgrounds/login-background.png`
- **Size:** 1536x1024 · **Crop to:** 1920x1080 (resize up)

```text
A calm abstract background image for a secure login page. Deep navy
(#0B1B3A) base. Very soft, blurred shapes of connected nodes and faint thin
grid lines in electric indigo (#4F46E5) and teal (#14B8A6), placed mostly
near the edges and corners and fading toward the center. The center of the
image is plain and darker, because a white login card will sit there. Low
contrast, quiet, not distracting. No objects in the center. No text, no
letters, no numbers, no logos, no watermarks, no human faces.
```

### #22 Empty state: no documents

- **Save as:** `apps/web/public/images/empty-states/no-documents.png`
- **Size:** 1024x1024 · **Background:** transparent · **Resize to:** 400x400

```text
A small, simple spot illustration for an empty screen in a web app: an empty
open folder with a soft glowing upload arrow floating just above it,
pointing up. Few details, friendly, works well at 200px. Flat vector with
soft gradients. Colors: electric indigo (#4F46E5), teal (#14B8A6), soft
white (#F8FAFC), one small amber (#F59E0B) accent. Centered on a fully
transparent background. No text, no letters, no numbers, no logos, no
watermarks, no human faces.
```

### #23 Empty state: no conversations

- **Save as:** `apps/web/public/images/empty-states/no-conversations.png`
- **Size:** 1024x1024 · **Background:** transparent · **Resize to:** 400x400

```text
A small, simple spot illustration for an empty screen in a web app: two
overlapping rounded chat bubbles, both empty, with one small sparkle next to
them. Few details, friendly, works well at 200px. Flat vector with soft
gradients. Colors: electric indigo (#4F46E5), teal (#14B8A6), soft white
(#F8FAFC), one small amber (#F59E0B) accent. Centered on a fully transparent
background. No text, no letters, no numbers, no logos, no watermarks, no
human faces.
```

### #24 Empty state: waiting for approval

- **Save as:** `apps/web/public/images/empty-states/waiting-approval.png`
- **Size:** 1024x1024 · **Background:** transparent · **Resize to:** 400x400

```text
A small, simple spot illustration for a web app screen: a small hourglass
standing next to a shield with a check-mark on it, showing that an action is
waiting for approval. Few details, calm, works well at 200px. Flat vector
with soft gradients. Colors: electric indigo (#4F46E5), teal (#14B8A6), soft
white (#F8FAFC), amber (#F59E0B) sand in the hourglass. Centered on a fully
transparent background. No text, no letters, no numbers, no logos, no
watermarks, no human faces.
```

### #25 Empty state: no access

- **Save as:** `apps/web/public/images/empty-states/no-access.png`
- **Size:** 1024x1024 · **Background:** transparent · **Resize to:** 400x400

```text
A small, simple spot illustration for a web app "no access" screen: one
closed rounded padlock with a soft amber (#F59E0B) glow around it. Friendly,
not scary, not aggressive. Few details, works well at 200px. Flat vector
with soft gradients. Colors: electric indigo (#4F46E5), teal (#14B8A6), soft
white (#F8FAFC), amber glow. Centered on a fully transparent background. No
text, no letters, no numbers, no logos, no watermarks, no human faces.
```

### #26 Page not found (404)

- **Save as:** `apps/web/public/images/errors/not-found.png`
- **Size:** 1024x1024 · **Background:** transparent · **Resize to:** 400x400

```text
A small, simple spot illustration for a "page not found" screen: a little
glowing round AI orb, with no face, holding an unfolded paper map, floating
at the edge of a small floating platform where the path suddenly ends.
Friendly and slightly funny. Few details, works well at 200px. Flat vector
with soft gradients. Colors: electric indigo (#4F46E5), teal (#14B8A6), soft
white (#F8FAFC), one small amber (#F59E0B) accent. Centered on a fully
transparent background. No text, no letters, no numbers, no logos, no
watermarks, no human faces.
```

### #27 Demo tenant A logo (fictional company)

- **Save as:** `apps/web/public/images/tenants/demo-tenant-a-logo.png`
- **Size:** 1024x1024 · **Background:** transparent · **Resize to:** 256x256

```text
A simple logo mark for a fictional mid-size investment firm, used only as
demo data. An abstract shape made of two upward-pointing geometric forms,
side by side, that suggest growth. It must not look like any real bank,
investment firm or financial brand. Solid flat shapes in teal (#14B8A6) and
deep navy (#0B1B3A). Centered, with padding, on a fully transparent
background. No text, no letters, no numbers, no shadows, no watermarks.
```

### #28 Demo tenant B logo (fictional company)

- **Save as:** `apps/web/public/images/tenants/demo-tenant-b-logo.png`
- **Size:** 1024x1024 · **Background:** transparent · **Resize to:** 256x256

```text
A simple logo mark for a fictional regional insurance company, used only as
demo data. An abstract shape: a rounded square with a simple curved arc
inside it, like a protective roof. It must not look like any real insurance
company, bank or financial brand. Solid flat shapes in amber (#F59E0B) and
deep navy (#0B1B3A). Centered, with padding, on a fully transparent
background. No text, no letters, no numbers, no shadows, no watermarks.
```

---

## Made from the logo (no new prompt)

| File | How |
|---|---|
| `apps/web/app/icon.png` | Resize `atlas-logo.png` to 512x512. Next.js uses it as the favicon automatically. |
| `apps/web/app/apple-icon.png` | Resize `atlas-logo.png` to 180x180 on a solid navy (#0B1B3A) background, because iOS doesn't support transparency. |

## If a result is not good

- **Too busy:** add `Use fewer elements, more empty space, simpler.`
- **Wrong colors:** add `Use only these colors: #0B1B3A, #4F46E5, #14B8A6, #F8FAFC, #F59E0B.`
- **Text appeared in the image:** add `Absolutely no text or letters anywhere.` and generate again.
- **Style doesn't match the others:** in ChatGPT, upload one good image first and write `Create a new image in exactly the same style as this one:` before the prompt.
