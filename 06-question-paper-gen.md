# Question Paper Generator — Complete Standalone Agent Prompt

## Project Identity

| Field | Value |
|-------|-------|
| **Project Folder** | `C:\Users\namsi\Desktop\Projects\Question Paper Generation` |
| **Tech Stack** | Python/Flask backend + Vanilla JS frontend |
| **Vercel URL** | https://question-paper-generation.vercel.app/ |
| **GitHub Repo** | `NamanSingh69/Question-Paper-Generator` (already exists) |
| **Vercel Env Vars** | `GEMINI_API_KEY` is set |

### Key Files
- `app.py` — Flask backend with paper generation, PDF creation, and download endpoints (`/generate_files`, `/download/report_pdf`)
- `static/index.html` — Main HTML page with multi-step configuration form (Bloom's Taxonomy, difficulty levels, etc.)
- `static/` — CSS, JS, static assets
- `static/gemini-client.js` — Should be v2 (28KB) — verify or copy from reference
- `api/` — Vercel Serverless Functions
- `vercel.json` — Route configuration
- `requirements.txt` — Python dependencies

---

## Shared Infrastructure Context (CRITICAL)

### Design System — "UX Mandate"
4 core states: Loading (skeletons), Success (toasts), Empty (null states), Error (actionable recovery). Never `alert()`.

### Gemini Client (Python/Vanilla JS)
`gemini-client.js` v2 (28KB): Pro/Fast toggle, rate limit counter, model cascade.
### Smart Model Cascade (March 2026)
**Primary (Free Preview):** `gemini-3.1-pro-preview` → `gemini-3-flash-preview` → `gemini-3.1-flash-lite-preview`
**Fallback (Free Stable):** `gemini-2.5-pro` → `gemini-2.5-flash` → `gemini-2.5-flash-lite`
**Note:** `gemini-2.0-*` deprecated March 3, 2026. Do NOT use.
- Config: `window.GEMINI_CONFIG = { needsRealTimeData: false }` (static generation project)
- Pro = first model in cascade, Fast = second model

### Security: `os.environ.get("GEMINI_API_KEY")`, never hardcode
### Mobile: viewport meta, 375px–1920px, touch targets ≥ 44px

---

## Current Live State (Verified March 10, 2026)

| Feature | Status | Details |
|---------|--------|---------|
| Site loads | ✅ 200 OK | Complex multi-step form for generating quizzes with Bloom's Taxonomy configuration |
| Login wall | ✅ None | |
| Pro/Fast Toggle | ❌ MISSING | No model selector or toggle found in the UI |
| Rate Limit Counter | ❌ MISSING | |
| Empty State | ✅ Present | Initial clean form with "Paper Generation Canvas" instructional text |
| Skeleton Loaders | ❌ NOT OBSERVED | Due to validation bug preventing form submission |
| Toasts | ✅ Present | Red error toast for validation issues (e.g., word count) |
| Mobile Responsive | ✅ Yes | Form stacks at 375px |
| Console Errors | ⚠️ Minor | favicon.ico 404 |
| **Critical Bug** | ❌ Word count validation broken | Even inserting 100+ words yields "Content must be at least 100 words long" error |

---

## Required Changes

### 1. Fix Word Count Validation Bug (CRITICAL — Blocking Paper Generation)
The word count validation in the frontend is broken — even inserting well over 100 words still triggers the error toast "Content must be at least 100 words long".

**Debugging steps:**
1. Search for the validation logic: `grep -r "100 words" static/` or `grep -r "word.*count\|words.*long" *.js *.html`
2. Common causes:
   - The word count function may be counting characters instead of words
   - It may be splitting on the wrong delimiter (e.g., `\n` instead of `\s+`)
   - It may be checking the wrong input field
3. **Correct word count logic:**
   ```javascript
   function countWords(text) {
     return text.trim().split(/\s+/).filter(word => word.length > 0).length;
   }
   ```
4. Test with 100+ word input to confirm the validation passes

### 2. Add Pro/Fast Toggle (via gemini-client.js v2)
- Verify `static/gemini-client.js` exists and is v2 (28KB)
- If missing/outdated, the file needs the full v2 implementation with:
  - Floating ⚡ PRO / 🚀 FAST toggle button
  - Rate limit counter (`X/15 remaining`)
  - Model cascade (Pro fallback to Flash on 429/503)
- Add to `static/index.html` before `</body>`:
  ```html
  <script>window.GEMINI_CONFIG = { needsRealTimeData: false };</script>
  <script src="/static/gemini-client.js"></script>
  ```

### 3. Add Skeleton Loaders for Paper Generation
When "Generate Exam Paper" is clicked:
- Show animated skeleton placeholders in the output area
- Skeletons should mimic the shape of generated questions (title, question text lines, option bullets)
- Use shimmer animation matching the existing color scheme

### 4. Verify PDF Generation & Download Pipeline
Previous conversations noted issues with:
- `/generate_files` endpoint — ensure it creates the PDF correctly
- `/download/report_pdf` endpoint — ensure it returns the PDF file for download
- Check `vercel.json` route mapping for these endpoints
- Test the full flow: generate paper → preview → download PDF

### 5. Server-Side API Key
- Backend must use `os.environ.get("GEMINI_API_KEY")`
- Search for hardcoded keys: `grep -r "AIza" *.py`
- Remove any found and replace with env var access

### 6. Mobile Responsiveness
- The multi-step form with Bloom's Taxonomy checkboxes must be tappable on mobile (each checkbox ≥ 44×44px touch target)
- Difficulty sliders must be usable on touch screens
- Generated paper output must scroll vertically, not overflow
- PDF download button must be prominent and easily tappable

### 7. GitHub & Deployment
- Push to `Question-Paper-Generator` repo
- `git add -A && git commit -m "fix: word count validation, add gemini client v2, skeletons, mobile hardening" && git push`
- Redeploy: `npx vercel --prod --yes`
- Verify at https://question-paper-generation.vercel.app/

---

## Verification Checklist
1. ✅ Site loads without errors
2. ✅ Pro/Fast toggle visible (floating button or header)
3. ✅ Rate limit counter visible
4. ✅ Enter 100+ words of content → validation passes (NOT "must be at least 100 words")
5. ✅ Configure exam parameters → click Generate → skeleton loaders appear
6. ✅ Paper generates → success toast fires
7. ✅ PDF download works end-to-end
8. ✅ Resize to 375px → form fully usable, checkboxes tappable
9. ✅ DevTools console → zero errors
