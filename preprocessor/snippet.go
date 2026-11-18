package main

import (
	"crypto/md5"
	"encoding/hex"
	"encoding/xml"
	"fmt"
	"io"
	"math"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
)

// BBox XML models for pdftotext -bbox-layout (wrapped in XHTML)
type BBoxHTML struct {
	XMLName xml.Name `xml:"html"`
	Body    BBoxBody `xml:"body"`
}

type BBoxBody struct {
	Doc BBoxDoc `xml:"doc"`
}

type BBoxDoc struct {
	Pages []BBoxPage `xml:"page"`
}

type BBoxPage struct {
	Width  float64    `xml:"width,attr"`
	Height float64    `xml:"height,attr"`
	Flows  []BBoxFlow `xml:"flow"`
}

type BBoxFlow struct {
	Blocks []BBoxBlock `xml:"block"`
}

type BBoxBlock struct {
	XMin  float64    `xml:"xMin,attr"`
	YMin  float64    `xml:"yMin,attr"`
	XMax  float64    `xml:"xMax,attr"`
	YMax  float64    `xml:"yMax,attr"`
	Lines []BBoxLine `xml:"line"`
}

type BBoxLine struct {
	XMin  float64    `xml:"xMin,attr"`
	YMin  float64    `xml:"yMin,attr"`
	XMax  float64    `xml:"xMax,attr"`
	YMax  float64    `xml:"yMax,attr"`
	Words []BBoxWord `xml:"word"`
}

type BBoxWord struct {
	XMin float64 `xml:"xMin,attr"`
	YMin float64 `xml:"yMin,attr"`
	XMax float64 `xml:"xMax,attr"`
	YMax float64 `xml:"yMax,attr"`
	Text string  `xml:",chardata"`
}

// FlatBlock represents a physical layout block with typography metrics
type FlatBlock struct {
	XMin          float64
	YMin          float64
	XMax          float64
	YMax          float64
	Text          string
	AvgLineHeight float64
	IsHeading     bool
}

// ExtractBBoxLayout runs `pdftotext -f N -l N -bbox-layout` and parses the XML structure.
func ExtractBBoxLayout(pdfPath string, pageNum int) (*BBoxPage, error) {
	cmd := exec.Command("pdftotext", "-f", fmt.Sprintf("%d", pageNum), "-l", fmt.Sprintf("%d", pageNum), "-bbox-layout", pdfPath, "-")
	output, err := cmd.Output()
	if err != nil {
		return nil, fmt.Errorf("pdftotext -bbox-layout failed: %w", err)
	}

	var html BBoxHTML
	if err := xml.Unmarshal(output, &html); err != nil {
		return nil, fmt.Errorf("failed to parse layout XML: %w", err)
	}

	if len(html.Body.Doc.Pages) == 0 {
		return nil, fmt.Errorf("no page data found in bbox-layout")
	}

	return &html.Body.Doc.Pages[0], nil
}

// FlattenAndAnalyzeBlocks extracts layout blocks and detects structural headings via geometry/typography.
func FlattenAndAnalyzeBlocks(page *BBoxPage) []FlatBlock {
	var blocks []FlatBlock
	var lineHeights []float64

	// First pass: extract text and collect line heights across page
	for _, flow := range page.Flows {
		for _, b := range flow.Blocks {
			var words []string
			var totalHeight float64
			var lineCount int

			for _, line := range b.Lines {
				h := line.YMax - line.YMin
				if h > 2.0 && h < 120.0 {
					lineHeights = append(lineHeights, h)
					totalHeight += h
					lineCount++
				}
				for _, w := range line.Words {
					cleaned := strings.TrimSpace(w.Text)
					if cleaned != "" {
						words = append(words, cleaned)
					}
				}
			}

			blockText := strings.TrimSpace(strings.Join(words, " "))
			if blockText != "" && (b.YMax-b.YMin) > 4.0 {
				avgH := 0.0
				if lineCount > 0 {
					avgH = totalHeight / float64(lineCount)
				}
				blocks = append(blocks, FlatBlock{
					XMin:          b.XMin,
					YMin:          b.YMin,
					XMax:          b.XMax,
					YMax:          b.YMax,
					Text:          blockText,
					AvgLineHeight: avgH,
				})
			}
		}
	}

	if len(blocks) == 0 {
		return nil
	}

	// Calculate median line height of the document (body text baseline)
	medianH := calcMedian(lineHeights)
	if medianH <= 0 {
		medianH = 10.0
	}

	// Universal structural prefix: "1.", "1.1", "A.", "(1)", "Step 3", "Section 2", "Clause 4", "Article 5", "Table 1", "Task 1"
	structuralPrefix := regexp.MustCompile(`(?i)^\s*(\d+(\.\d+)*|[A-Z]\.|\([a-z0-9]+\)|Step\s+\d+|Section\s+\d+|Article\s+\d+|Chapter\s+\d+|Part\s+\d+|Clause\s+\d+|Table\s+\d+|Figure\s+\d+|Task\s+\d+|Objective:|Tech\s+Stack)\b`)

	// Second pass: Mark structural headings purely by geometry, font scaling, and universal numbering
	for i := range blocks {
		b := &blocks[i]
		t := b.Text
		tUpper := strings.ToUpper(t)

		// 1. Font size significantly larger than median body text
		if b.AvgLineHeight >= 1.22*medianH && len(t) < 120 {
			b.IsHeading = true
			continue
		}

		// 2. Short uppercase title line with actual letters (not bullet symbols) and no sentence punctuation
		if len(t) >= 3 && len(t) < 55 && tUpper == t && regexp.MustCompile(`[A-Za-z]`).MatchString(t) && !strings.Contains(t, ".") && !strings.Contains(t, "?") && !strings.Contains(t, "|") && !strings.Contains(t, "@") {
			b.IsHeading = true
			continue
		}

		// 3. Structural numbering or section marker
		if structuralPrefix.MatchString(t) && len(t) < 90 {
			b.IsHeading = true
			continue
		}
	}

	return blocks
}

func calcMedian(vals []float64) float64 {
	if len(vals) == 0 {
		return 0
	}
	sorted := make([]float64, len(vals))
	copy(sorted, vals)
	sort.Float64s(sorted)
	mid := len(sorted) / 2
	if len(sorted)%2 == 0 {
		return (sorted[mid-1] + sorted[mid]) / 2.0
	}
	return sorted[mid]
}

// Universal English stopwords (domain-agnostic)
var universalStopWords = map[string]bool{
	"a": true, "about": true, "above": true, "after": true, "again": true, "against": true,
	"all": true, "am": true, "an": true, "and": true, "any": true, "are": true, "as": true,
	"at": true, "be": true, "because": true, "been": true, "before": true, "being": true,
	"below": true, "between": true, "both": true, "but": true, "by": true, "could": true,
	"did": true, "do": true, "does": true, "doing": true, "down": true, "during": true,
	"each": true, "few": true, "for": true, "from": true, "further": true, "had": true,
	"has": true, "have": true, "having": true, "he": true, "her": true, "here": true,
	"hers": true, "herself": true, "him": true, "himself": true, "his": true, "how": true,
	"i": true, "if": true, "in": true, "into": true, "is": true, "it": true, "its": true,
	"itself": true, "me": true, "more": true, "most": true, "my": true, "myself": true,
	"no": true, "nor": true, "not": true, "of": true, "off": true, "on": true, "once": true,
	"only": true, "or": true, "other": true, "ought": true, "our": true, "ours": true,
	"ourselves": true, "out": true, "over": true, "own": true, "same": true, "she": true,
	"should": true, "so": true, "some": true, "such": true, "than": true, "that": true,
	"the": true, "their": true, "theirs": true, "them": true, "themselves": true, "then": true,
	"there": true, "these": true, "they": true, "this": true, "those": true, "through": true,
	"to": true, "too": true, "under": true, "until": true, "up": true, "very": true,
	"was": true, "we": true, "were": true, "what": true, "when": true, "where": true,
	"which": true, "while": true, "who": true, "whom": true, "why": true, "with": true,
	"would": true, "you": true, "your": true, "yours": true, "yourself": true, "yourselves": true,
	"paste": true, "upload": true, "resume": true, "pdf": true, "page": true,
}

var wordTokenRe = regexp.MustCompile(`[a-zA-Z0-9_\-\+]+`)

func tokenizeText(text string) []string {
	matches := wordTokenRe.FindAllString(strings.ToLower(text), -1)
	var tokens []string
	for _, m := range matches {
		if len(m) >= 3 && !universalStopWords[m] {
			tokens = append(tokens, m)
		}
	}
	return tokens
}

func extractNGrams(words []string, n int) []string {
	if len(words) < n {
		return nil
	}
	var res []string
	for i := 0; i <= len(words)-n; i++ {
		res = append(res, strings.Join(words[i:i+n], " "))
	}
	return res
}

// FindTargetSection locates the visual citation box on the page using universal text-alignment.
func FindTargetSection(page *BBoxPage, query string, answer string, terms []string) (x0, y0, x1, y1 float64, found bool) {
	blocks := FlattenAndAnalyzeBlocks(page)
	if len(blocks) == 0 {
		return 0, 0, 0, 0, false
	}

	qTokens := tokenizeText(query)
	aTokens := tokenizeText(answer)

	// Build word slices for n-grams from Answer
	allWordsA := wordTokenRe.FindAllString(strings.ToLower(answer), -1)
	a3Grams := extractNGrams(allWordsA, 3)
	a2Grams := extractNGrams(allWordsA, 2)

	// Clean terms passed from backend
	cleanTerms := make([]string, 0, len(terms))
	for _, t := range terms {
		cl := strings.ToLower(strings.TrimSpace(t))
		if len(cl) >= 3 && !universalStopWords[cl] {
			cleanTerms = append(cleanTerms, cl)
		}
	}

	// Numbered section constraint if explicitly requested in query (e.g. 'Step 3', 'Section 4', 'Task 2')
	stepRe := regexp.MustCompile(`(?i)\b(step|section|chapter|part|task|clause|article|rule)\s+(\d+)\b`)
	stepMatch := stepRe.FindStringSubmatch(query)
	var structuralRe *regexp.Regexp
	if len(stepMatch) == 3 {
		// Matches "Section 3", "Step 3", or "3." / "3 -"
		structuralRe = regexp.MustCompile(fmt.Sprintf(`(?i)^\s*(%s\s+)?%s[\.\:\-\s]`, regexp.QuoteMeta(stepMatch[1]), regexp.QuoteMeta(stepMatch[2])))
	}

	// Document title / author question check
	isHeaderQuestion := strings.Contains(strings.ToLower(query), "title") ||
		strings.Contains(strings.ToLower(query), "author") ||
		strings.Contains(strings.ToLower(query), "name") ||
		strings.Contains(strings.ToLower(query), "who is")

	bestScore := -1.0
	bestIdx := -1

	for i, b := range blocks {
		score := 0.0
		bTextLower := strings.ToLower(b.Text)

		// 1. Structural entity match bonus
		if structuralRe != nil && structuralRe.MatchString(b.Text) {
			score += 450.0
		}

		// 2. High-precision exact n-gram matching from Answer (strongest signal)
		for _, ng := range a3Grams {
			if strings.Contains(bTextLower, ng) {
				score += 180.0
			}
		}
		for _, ng := range a2Grams {
			if strings.Contains(bTextLower, ng) {
				score += 70.0
			}
		}

		// 3. Salient Token Overlap from Answer
		bTokens := tokenizeText(b.Text)
		bTokenSet := make(map[string]bool, len(bTokens))
		for _, bt := range bTokens {
			bTokenSet[bt] = true
		}

		for _, at := range aTokens {
			if bTokenSet[at] {
				score += 30.0
			}
		}

		// 4. Salient Token Overlap from Query (de-weighted for page top header unless header query)
		isTopHeader := (i == 0 || b.YMin < 110.0)
		for _, qt := range qTokens {
			if bTokenSet[qt] {
				if isTopHeader && !isHeaderQuestion {
					continue
				}
				score += 15.0
			}
		}

		// 5. Backend extracted terms
		for _, tm := range cleanTerms {
			if strings.Contains(bTextLower, tm) {
				if strings.Contains(tm, " ") {
					score += 140.0
				} else {
					score += 35.0
				}
			}
		}

		// Top header penalty if not a title/author question
		if isTopHeader && !isHeaderQuestion {
			score -= 60.0
		}

		if score > bestScore {
			bestScore = score
			bestIdx = i
		}
	}

	if bestIdx < 0 || bestScore <= 0 {
		return 0, 0, 0, 0, false
	}

	// Find the visual section bounds (walk upwards to section start/heading, walk downwards to next section/heading)
	startIdx := bestIdx
	for k := bestIdx; k > 0; k-- {
		prevB := blocks[k-1]
		currB := blocks[k]
		gap := currB.YMin - prevB.YMax

		// If previous block is a structural heading, include it and stop upward crawl
		if prevB.IsHeading {
			if gap < 45.0 {
				startIdx = k - 1
			}
			break
		}

		// If there is a large visual gap between blocks, it's a section break
		if gap > 32.0 {
			break
		}

		// If total height upwards exceeds 220pt, stop
		if (blocks[bestIdx].YMax - prevB.YMin) > 220.0 {
			break
		}

		startIdx = k - 1
	}

	minX := blocks[startIdx].XMin
	minY := blocks[startIdx].YMin
	maxX := blocks[startIdx].XMax
	maxY := blocks[startIdx].YMax

	for k := startIdx; k <= bestIdx; k++ {
		b := blocks[k]
		if b.XMin < minX {
			minX = b.XMin
		}
		if b.XMax > maxX {
			maxX = b.XMax
		}
		if b.YMax > maxY {
			maxY = b.YMax
		}
	}

	var nextHeadingYMin float64 = -1

	// Look-ahead: accumulate subsequent blocks until next heading or max height
	for j := bestIdx + 1; j < len(blocks); j++ {
		nextB := blocks[j]
		prevB := blocks[j-1]
		gap := nextB.YMin - prevB.YMax

		// Stop if hitting another structural heading
		if nextB.IsHeading {
			nextHeadingYMin = nextB.YMin
			break
		}

		// Stop if large vertical gap (new section)
		if gap > 32.0 && j > bestIdx {
			nextHeadingYMin = nextB.YMin
			break
		}

		// Stop if total height exceeds 340 points
		if (nextB.YMax - minY) > 340.0 {
			break
		}

		// Include this block
		if nextB.XMin < minX {
			minX = nextB.XMin
		}
		if nextB.XMax > maxX {
			maxX = nextB.XMax
		}
		maxY = nextB.YMax
	}

	// Clamping height for visual comfort
	height := maxY - minY
	if height < 80.0 {
		maxY = math.Min(page.Height, minY+80.0)
	}
	if (maxY - minY) > 360.0 {
		maxY = minY + 360.0
	}

	// Ensure adequate width for readability if narrow single line
	if (maxX - minX) < 380.0 {
		maxX = math.Min(page.Width-16.0, minX+400.0)
	}

	// Padding
	padX := 16.0
	padY := 12.0
	x0 = math.Max(0, minX-padX)
	y0 = math.Max(0, minY-padY)
	x1 = math.Min(page.Width, maxX+padX)
	y1 = math.Min(page.Height, maxY+padY)

	// Clean cutoff: do not chop into next heading
	if nextHeadingYMin > 0 && y1 >= nextHeadingYMin {
		y1 = math.Max(y0+50.0, nextHeadingYMin-4.0)
	}

	return x0, y0, x1, y1, true
}

// CropPDFSnippet renders a high-res 180 DPI sub-rectangle crop using pdftoppm.
func CropPDFSnippet(pdfPath string, thumbnailsDir string, filename string, pageNum int, x0, y0, x1, y1 float64) (string, error) {
	// Deterministic hash based on page and rounded coordinates
	key := fmt.Sprintf("p%d_%d_%d_%d_%d", pageNum, int(math.Round(x0)), int(math.Round(y0)), int(math.Round(x1)), int(math.Round(y1)))
	hasher := md5.New()
	hasher.Write([]byte(key))
	hash := hex.EncodeToString(hasher.Sum(nil))[:10]

	destDir := filepath.Join(thumbnailsDir, filename)
	if err := os.MkdirAll(destDir, 0755); err != nil {
		return "", err
	}

	finalFilename := fmt.Sprintf("snippet_p%d_%s.png", pageNum, hash)
	finalPath := filepath.Join(destDir, finalFilename)

	// Cache check
	if _, err := os.Stat(finalPath); err == nil {
		return fmt.Sprintf("/thumbnails/%s/%s", filename, finalFilename), nil
	}

	// PDF points (72 DPI) to 180 DPI pixels: factor = 180.0 / 72.0 = 2.5
	dpi := 180
	scale := float64(dpi) / 72.0

	pixelX := int(math.Round(x0 * scale))
	pixelY := int(math.Round(y0 * scale))
	pixelW := int(math.Round((x1 - x0) * scale))
	pixelH := int(math.Round((y1 - y0) * scale))

	// Ensure minimal dimensions
	if pixelW < 100 {
		pixelW = 100
	}
	if pixelH < 100 {
		pixelH = 100
	}

	tempPrefix := filepath.Join(destDir, fmt.Sprintf("temp_crop_%d_%s", pageNum, hash))
	cmd := exec.Command("pdftoppm",
		"-png",
		"-r", fmt.Sprintf("%d", dpi),
		"-f", fmt.Sprintf("%d", pageNum),
		"-l", fmt.Sprintf("%d", pageNum),
		"-x", fmt.Sprintf("%d", pixelX),
		"-y", fmt.Sprintf("%d", pixelY),
		"-W", fmt.Sprintf("%d", pixelW),
		"-H", fmt.Sprintf("%d", pixelH),
		pdfPath,
		tempPrefix,
	)

	if output, err := cmd.CombinedOutput(); err != nil {
		return "", fmt.Errorf("pdftoppm crop failed: %v, output: %s", err, string(output))
	}

	// pdftoppm appends -<page>.png to the prefix, e.g. temp_crop_1_hash-1.png or temp_crop_1_hash-01.png
	matches, err := filepath.Glob(tempPrefix + "*.png")
	if err != nil || len(matches) == 0 {
		return "", fmt.Errorf("pdftoppm generated no image matching prefix %s", tempPrefix)
	}

	generatedFile := matches[0]
	if err := os.Rename(generatedFile, finalPath); err != nil {
		// Fallback to copy if cross-device
		if err := copyFile(generatedFile, finalPath); err != nil {
			return "", err
		}
		_ = os.Remove(generatedFile)
	}

	// Clean up any other match if present
	for _, m := range matches[1:] {
		_ = os.Remove(m)
	}

	return fmt.Sprintf("/thumbnails/%s/%s", filename, finalFilename), nil
}

func copyFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()

	out, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer out.Close()

	_, err = io.Copy(out, in)
	return err
}
