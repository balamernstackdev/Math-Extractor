# Mathpix Clone - Technical Documentation

## 1. Executive Summary

This project is a high-precision OCR (Optical Character Recognition) application specialized for mathematical equations. It mimics the functionality of Mathpix Snip, allowing users to:
1.  **Capture/Upload** images of mathematical equations (handwritten or printed).
2.  **Convert** them into LaTeX and MathML formats.
3.  **Preview** the rendered equations instantly.
4.  **Export** to various formats (MS Word, clipboard).

The system prioritizes **accuracy** and **validity**, using a "Strict Pipeline" that combines local OCR models (`pix2tex`), heuristic cleaning, and AI fallbacks (OpenAI GPT-4) to ensure the generated MathML is structurally correct and visually faithful to the source.

---

## 2. System Architecture

The application follows a **Model-View-Controller (MVC)** inspired architecture, separating the UI (PyQt6) from the business logic (OCR Services).

### 2.1 High-Level Layers

*   **UI Layer (`ui/`)**: Handles user interaction, rendering, and state management.
    *   **Main Window**: The shell application.
    *   **Preview Panel**: The core interaction hub for viewing and editing results.
    *   **Overlay**: Screen capture tools.
*   **Service Layer (`services/`)**: Contains the business logic.
    *   **OCR Services**: `pix2tex` integration, image preprocessing.
    *   **Pipeline**: The orchestration logic for converting LaTeX to MathML.
    *   **Persistence**: History tracking and caching.
*   **Core (`core/`)**: Configuration (`config.py`) and logging (`logger.py`).

### 2.2 Directory Structure

```text
d:\test-r&d\mathpix_clone\
├── core/                  # Global settings and utilities
├── services/
│   ├── ocr/               # Core OCR and conversion logic
│   │   ├── latex_to_mathml.py  # Critical conversion engine
│   │   ├── ocr_worker.py       # Background thread for processing
│   │   └── strict_pipeline.py  # Orchestrator for validations
│   └── persistence/       # data storage (history)
├── ui/                    # PyQt6 Widgets
│   ├── preview_panel.py   # Main result view
│   ├── main_window.py     # Application shell
│   └── ...
└── utils/                 # Helper scripts
```

---

## 3. Core Workflows

### 3.1 The OCR Pipeline (Image → MathML)

The `OCRWorker` class orchestrates this process in a background thread to keep the UI responsive.

1.  **Image Acquisition**: User captures or drags an image.
2.  **Cache Check**: System checks if this image hash exists in `EquationCache`.
3.  **OCR (`pix2tex`)**: The `LatexOCR` model converts the image to a raw LaTeX string.
4.  **Normalization**:
    *   `LatexNormalizer` strips invisible characters and formatting noise.
    *   `LatexFixer` balances delimiters (`\left`, `\right`) and fixes common OCR typos (e.g., `\bf` -> `\mathbf`).
5.  **Conversion (`LatexToMathML`)**:
    *   Converts cleaned LaTeX to MathML using `latex2mathml`.
    *   Applies structural fixes (e.g., `<msub>` vs `<munder>`).
6.  **Validation**:
    *   Checks for "shredded" tags (indicating OCR errors).
    *   Verifies XML structure.
7.  **Fallback (AI)**:
    *   If validation fails, the `StrictMathpixPipeline` sends the raw LaTeX/Image to OpenAI GPT-4 for "Repair".
8.  **Output**: The final valid MathML is sent to the UI.

### 3.2 The Paste & Clean Workflow

Located in `ui/preview_panel.py` -> `EditableMathMLEdit`.

1.  **Paste Event**: User pastes text into the editor.
2.  **Detection**: System detects if the text is corrupted LaTeX (e.g., `\mathrm{t}\mathrm{ext}`) commonly found when copying from PDFs.
3.  **Cleaning**: Regex patterns merge fragmented commands and remove artifacts.
4.  **Conversion**: If the pasted text is LaTeX, it is auto-converted to MathML.

---

## 4. Key Components

### 4.1 `services/ocr/latex_to_mathml.py`
**Responsibility**: The specific engine for translating LaTeX syntax into MathML XML.
*   **Key Features**:
    *   **Multiline Support**: Detects `align`, `gather`, `cases` environments and builds `<mtable>` structures.
    *   **Repair Logic**: Automatically adds missing `\right` delimiters to prevent crash.
    *   **Limit Enforcement**: Ensures sums and integrals render limits correctly (vertical vs horizontal).

### 4.2 `ui/preview_panel.py`
**Responsibility**: The user-facing component for results.
*   **Key Features**:
    *   **QtWebEngine**: Renders the MathML using a robust browser engine (Chromium-based) for perfect fidelity.
    *   **Interactive Editing**: Users can edit the raw code, triggering real-time re-rendering.
    *   **Status Indicators**: Shows "Confidence Score" and validation status (Green/Red dots).

### 4.3 `services/ocr/ocr_worker.py`
**Responsibility**: Background processing.
*   **Key Features**:
    *   **Signals**: Emits `partial_result_ready` for instant feedback and `result_ready` for final validated output.
    *   **Error Handling**: Catches specific `pix2tex` failures and routes them to the AI fallback if enabled.

---

## 5. Improvement Roadmap

### 5.1 Proposed Feature Enhancements
| Feature | Description | Priority | Status |
|:---|:---|:---|:---|
| **Visual Editor** | Integrate a WYSIWYG math editor (e.g., MathLive) into the Preview Panel. | High | ✅ Done |
| **History Actions** | Allow users to click history items to re-load them. | Medium | ✅ Done |
| **Batch Queue** | A visible queue for processing 50+ images without freezing. | High | ✅ Done |
| **Word Export** | Native `.docx` export with embedded MathML. | Medium | ✅ Done |

### 5.2 Technical Debt Refactoring
| Component | Issue | Proposed Solution | Status |
|:---|:---|:---|:---|
| `latex_to_mathml.py` | "God Object" handling too many concerns. | Split into `Validator`, `Normalizer`, and `Converter`. | ✅ Done |
| `PreviewPanel` | UI code mixed with logic. | Extract logic to `PreviewController`. | ✅ Done |
| `OCRWorker` | One thread per file (inefficient). | Implement `QThreadPool` for scalable batch processing. | High |
