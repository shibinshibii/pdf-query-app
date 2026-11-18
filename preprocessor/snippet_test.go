package main

import (
	"fmt"
	"strings"
	"testing"
)

// 1. Test Technical Task Sheet (Engineering / Spec Document)
func TestBackendTaskSheetTechStack(t *testing.T) {
	pdfPath := "/data/hobby/pdf-reviewer/backend/uploads/Backend_Developer_Task_Sheet.pdf"
	page, err := ExtractBBoxLayout(pdfPath, 1)
	if err != nil {
		t.Fatalf("Failed to extract layout: %v", err)
	}

	query := "what are the strict tech stack requirements?"
	answer := "You must use Node.js, Express.js, PostgreSQL with Prisma or Sequelize, FFmpeg, and Multer."
	terms := []string{"Node.js", "Express.js", "PostgreSQL", "FFmpeg", "Multer"}

	x0, y0, x1, y1, found := FindTargetSection(page, query, answer, terms)
	if !found {
		t.Fatalf("Expected section to be found")
	}

	fmt.Printf("[TestBackendTaskSheetTechStack] box=(%.1f, %.1f, %.1f, %.1f)\n", x0, y0, x1, y1)

	// Verify that the crop area contains "Tech Stack"
	blocks := FlattenAndAnalyzeBlocks(page)
	matched := false
	for _, b := range blocks {
		if b.YMin >= y0 && b.YMax <= y1 && strings.Contains(b.Text, "Tech Stack") {
			matched = true
			break
		}
	}
	if !matched {
		t.Errorf("Tech Stack was not found within the cropped bounding box")
	}
}

// 2. Test Product Manual (OneDrive Getting Started Guide)
func TestOneDriveCloudStorage(t *testing.T) {
	pdfPath := "/data/hobby/pdf-reviewer/backend/uploads/Getting_started_with_OneDrive.pdf"
	page, err := ExtractBBoxLayout(pdfPath, 2)
	if err != nil {
		t.Fatalf("Failed to extract layout: %v", err)
	}

	query := "how much free storage does OneDrive provide?"
	answer := "OneDrive provides 5 GB of free storage, or you can upgrade to Microsoft 365 for 1 TB."
	terms := []string{"5 GB", "Microsoft 365", "storage"}

	x0, y0, x1, y1, found := FindTargetSection(page, query, answer, terms)
	if !found {
		t.Fatalf("Expected section to be found")
	}

	fmt.Printf("[TestOneDriveCloudStorage] box=(%.1f, %.1f, %.1f, %.1f)\n", x0, y0, x1, y1)

	// Verify that the crop area contains "5 GB" and "Cloud storage"
	blocks := FlattenAndAnalyzeBlocks(page)
	matchedStorage := false
	matchedHeading := false
	for _, b := range blocks {
		if b.YMin >= y0 && b.YMax <= y1 {
			if strings.Contains(b.Text, "5 GB") {
				matchedStorage = true
			}
			if strings.Contains(b.Text, "Cloud storage") {
				matchedHeading = true
			}
		}
	}
	if !matchedStorage || !matchedHeading {
		t.Errorf("Expected 'Cloud storage' and '5 GB' within crop, got storage=%v heading=%v", matchedStorage, matchedHeading)
	}
}

// 3. Test Three User Queries on Shibin_P_Python_Developer.pdf
func TestUserThreeQueries(t *testing.T) {
	pdfPath := "/data/hobby/pdf-reviewer/backend/uploads/Shibin_P_Python_Developer.pdf"
	page, err := ExtractBBoxLayout(pdfPath, 1)
	if err != nil {
		t.Fatalf("Failed to extract layout: %v", err)
	}

	// Query 1: University
	q1 := "which university shibin graduated from"
	a1 := "Calicut University"
	_, y0_1, _, y1_1, found1 := FindTargetSection(page, q1, a1, []string{"Calicut University", "Calicut", "University"})
	fmt.Printf("Q1 (University): found=%v, y=(%.1f - %.1f)\n", found1, y0_1, y1_1)

	// Query 2: Experience
	q2 := "how many years of experience he have?"
	a2 := "Based on the provided context, Shibin P has 1.7 years of experience."
	_, y0_2, _, y1_2, found2 := FindTargetSection(page, q2, a2, []string{"1.7 years", "experience"})
	fmt.Printf("Q2 (Experience): found=%v, y=(%.1f - %.1f)\n", found2, y0_2, y1_2)

	// Query 3: Skills
	q3 := "what are the skills he have"
	a3 := "Based on the provided context, Shibin P has the following skills: Programming Languages: Python, JavaScript, TypeScript, PHP, Golang, HTML, CSS Backend: Django, Django REST Framework, REST APIs, FastAPI, Laravel, Celery, JWT Data & AI: MySQL, PostgreSQL, Redis, LlamaIndex, RAG, Gemini API"
	_, y0_3, _, y1_3, found3 := FindTargetSection(page, q3, a3, []string{"Programming Languages", "Python", "Django", "FastAPI"})
	fmt.Printf("Q3 (Skills): found=%v, y=(%.1f - %.1f)\n", found3, y0_3, y1_3)

	// Query 4: Projects
	q4 := "what are the projects he done?"
	a4 := "Based on the provided context, the projects he did are: drf-routes: DRF API Docs Tool, PDF Reviewer: FastAPI React LlamaIndex Gemini"
	_, y0_4, _, y1_4, found4 := FindTargetSection(page, q4, a4, []string{"drf-routes", "PDF Reviewer", "projects"})
	fmt.Printf("Q4 (Projects): found=%v, y=(%.1f - %.1f)\n", found4, y0_4, y1_4)

	// Assertions
	if y0_1 < 650.0 {
		t.Errorf("Q1 (University) should target Education section (y > 650), got y0=%.1f", y0_1)
	}
	if y0_2 < 150.0 || y0_2 > 200.0 {
		t.Errorf("Q2 (Experience) should target Professional Summary (y0 ~ 166), got y0=%.1f", y0_2)
	}
	if y0_3 < 240.0 || y0_3 > 270.0 {
		t.Errorf("Q3 (Skills) should target Skills section (y0 ~ 255), got y0=%.1f", y0_3)
	}
	if y0_4 < 590.0 || y0_4 > 620.0 {
		t.Errorf("Q4 (Projects) should target Projects section (y0 ~ 603), got y0=%.1f", y0_4)
	}
}
