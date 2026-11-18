import os
import hashlib
import re
import fitz  # PyMuPDF

# Common template boilerplate phrases to ignore during semantic matching
BOILERPLATE_PATTERNS = [
    r'paste\s+or\s+upload',
    r'job\s+description',
    r'my\s+resume',
    r'prolance\s+resume',
    r'interview\s+preparation\s+guide',
    r'sample\s+answer',
    r'concise\s+and\s+confident',
    r'what\s+is',
    r'how\s+to',
    r'tell\s+me',
    r'can\s+you',
    r'based\s+on',
    r'for\s+each\s+question',
]


def is_boilerplate(text: str) -> bool:
    t = text.lower().strip()
    if len(t) < 4:
        return True
    for p in BOILERPLATE_PATTERNS:
        if re.search(p, t):
            return True
    return False


def find_focused_rect(page: fitz.Page, query: str = "", answer: str = "") -> fitz.Rect | None:
    """
    Finds the tight, focused bounding box on the page corresponding to the specific
    section/paragraph referenced by the query and answer, rather than the entire page.
    Returns None if this page has no authentic relevance to the query or answer.
    """
    matched_anchor = None
    blocks = page.get_text("blocks")
    text_blocks = [
        b for b in blocks
        if b[4].strip() and (b[3] - b[1]) > 8
        and not (b[1] < 55 and ("PROLANCE" in b[4] or "Page" in b[4]))
        and not (b[1] > 730 and b[4].strip().lower().startswith("page "))
    ]

    # 1. Hard check: Numbered entity constraint (e.g. 'Step 2', 'Step 3', 'Section 4')
    entity_m = re.search(r'\b(step|section|chapter|part|phase)\s+(\d+|[ivx]+)\b', query, re.I)
    if entity_m:
        entity_name = entity_m.group(1)
        entity_val = entity_m.group(2)
        # Check if this page defines this specific entity as a section heading (e.g. 'Step 2')
        heading_pattern = rf'^\s*{re.escape(entity_name)}\s+{re.escape(entity_val)}\b'
        for b in text_blocks:
            if re.search(heading_pattern, b[4], re.I | re.M):
                matched_anchor = fitz.Rect(b[:4])
                break

        # If query specifically asked for Step X and this page does NOT define Step X, REJECT!
        if not matched_anchor:
            return None

    # 2. Match exact salient title/concept quotes from the answer (e.g. "Role & JD-Specific Deep Dive")
    if not matched_anchor and answer:
        quotes = re.findall(r'[\"\'\`\*]{1,2}([^\"\'\`\*]{5,50})[\"\'\`\*]{1,2}', answer)
        for q_term in quotes:
            q_clean = q_term.strip()
            if not is_boilerplate(q_clean):
                m = page.search_for(q_clean)
                if m:
                    matched_anchor = m[0]
                    break

    # 3. Match multi-word content phrases from the query (excluding question stop words)
    if not matched_anchor and query:
        stop_words = {'what', 'is', 'are', 'was', 'were', 'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and', 'or', 'how', 'why', 'when', 'tell', 'me', 'about', 'can', 'you', 'give'}
        query_words = [w for w in re.sub(r'[^\w\s]', ' ', query).strip().lower().split() if w not in stop_words]
        for n in range(min(len(query_words), 4), 1, -1):
            for i in range(len(query_words) - n + 1):
                phrase = " ".join(query_words[i:i+n])
                if not is_boilerplate(phrase):
                    m = page.search_for(phrase)
                    if m:
                        matched_anchor = m[0]
                        break
            if matched_anchor:
                break

    # 4. Match non-boilerplate distinct sentence phrases from the answer
    if not matched_anchor and answer:
        ans_clean = re.sub(r'[\*\#\`]', '', answer)
        for sentence in re.split(r'[\.\n]', ans_clean):
            s_words = [w for w in sentence.split() if len(w) > 3 and not is_boilerplate(w)]
            if len(s_words) >= 4:
                for i in range(min(len(s_words) - 3, 3)):
                    phrase = " ".join(s_words[i:i+4])
                    if not is_boilerplate(phrase):
                        m = page.search_for(phrase)
                        if m:
                            matched_anchor = m[0]
                            break
            if matched_anchor:
                break

    # If neither query phrase nor answer phrase matched authentically: NOT RELEVANT
    if not matched_anchor:
        return None

    # Find the block containing or intersecting the anchor
    section_blocks = []
    for b in text_blocks:
        b_rect = fitz.Rect(b[:4])
        if b_rect.intersects(matched_anchor) or (b[1] <= matched_anchor.y1 and b[3] >= matched_anchor.y0):
            section_blocks.append(b)

    # Expand downwards for the section content (max height 280pt)
    if section_blocks:
        start_y = min(b[1] for b in section_blocks)
        end_y = max(b[3] for b in section_blocks)
        for b in text_blocks:
            if b[1] >= end_y and (b[1] - end_y) < 22 and (b[3] - start_y) < 280:
                # Stop if hitting another major step/header
                if re.match(r'^(Step\s+\d+|[A-Z\s]{4,}:)', b[4].strip()):
                    break
                section_blocks.append(b)
                end_y = b[3]
    else:
        section_blocks = [(matched_anchor.x0, matched_anchor.y0, matched_anchor.x1, matched_anchor.y1, "")]

    combined = fitz.Rect(section_blocks[0][:4])
    for b in section_blocks[1:]:
        combined = combined | fitz.Rect(b[:4])

    # Ensure height is clamped (max 320 points, minimum 70 points)
    if combined.height > 320:
        combined.y1 = combined.y0 + 320
    if combined.height < 70:
        combined.y1 = min(page.rect.height, combined.y0 + 70)

    # Add generous horizontal margin and modest vertical margin
    pad_x, pad_y = 16, 12
    clip_rect = fitz.Rect(
        max(0, combined.x0 - pad_x),
        max(0, combined.y0 - pad_y),
        min(page.rect.width, combined.x1 + pad_x),
        min(page.rect.height, combined.y1 + pad_y),
    )
    return clip_rect


def generate_snippet_clip(
    file_path: str,
    page_label: str,
    text_chunk: str,
    output_dir: str,
    query: str = "",
    answer: str = "",
    existing_regions: list | None = None
) -> str | None:
    """
    Finds the exact bounding box of the relevant section on the given PDF page
    and crops a high-resolution snapshot image (180 DPI).
    Returns the generated image filename, or None if the page is not relevant
    or if this section significantly overlaps with an already-accepted source on the same page.
    """
    if not os.path.exists(file_path):
        return None

    os.makedirs(output_dir, exist_ok=True)

    try:
        doc = fitz.open(file_path)

        # Determine 0-based page index
        try:
            page_idx = int(page_label) - 1
        except (ValueError, TypeError):
            page_idx = 0

        if not (0 <= page_idx < len(doc)):
            page_idx = 0

        page = doc[page_idx]

        clip_rect = find_focused_rect(page, query=query, answer=answer)
        if not clip_rect:
            return None

        # Deduplicate heavily overlapping regions on the same page (>50% vertical overlap)
        if existing_regions is not None:
            for ex_page, (ex_x0, ex_y0, ex_x1, ex_y1) in existing_regions:
                if ex_page == str(page_label):
                    inter_y0 = max(clip_rect.y0, ex_y0)
                    inter_y1 = min(clip_rect.y1, ex_y1)
                    inter_h = max(0.0, inter_y1 - inter_y0)
                    min_h = min(clip_rect.height, ex_y1 - ex_y0)
                    if min_h > 0 and (inter_h / min_h) > 0.5:
                        return None

        # Deterministic cache filename based on page and rounded bounding box coordinates
        box_key = f"p{page_label}_{round(clip_rect.x0)}_{round(clip_rect.y0)}_{round(clip_rect.x1)}_{round(clip_rect.y1)}"
        snippet_hash = hashlib.md5(box_key.encode()).hexdigest()[:10]
        out_filename = f"snippet_p{page_label}_{snippet_hash}.png"
        out_path = os.path.join(output_dir, out_filename)

        # Record this accepted region
        if existing_regions is not None:
            existing_regions.append((str(page_label), (clip_rect.x0, clip_rect.y0, clip_rect.x1, clip_rect.y1)))

        # Return cached image if already rendered
        if os.path.exists(out_path):
            return out_filename

        # Render at 180 DPI for crisp, readable typography
        pix = page.get_pixmap(clip=clip_rect, dpi=180)
        pix.save(out_path)
        return out_filename

    except Exception as e:
        print(f"[Snippet Clip Error] Failed to generate snippet clip: {e}")
        return None
