# PDF Heading Extractor Documentation

## Overview

The PDF Heading Extractor is a Python-based tool designed to automatically extract document titles and hierarchical headings (H1-H4) from PDF files. It uses advanced font analysis, natural language processing, and pattern recognition to identify and classify headings with high accuracy.

## Features

- **Automatic Title Extraction**: Intelligently identifies document titles from the first page
- **Hierarchical Heading Detection**: Classifies headings into H1, H2, H3, and H4 levels based on font size and formatting
- **Font Analysis**: Analyzes document fonts to establish heading thresholds automatically
- **NLP Validation**: Uses spaCy for intelligent text validation (optional)
- **Duplicate Prevention**: Removes duplicate headings and title repetitions
- **Clean Output**: Provides structured JSON output with title and outline information

## Installation

### Prerequisites

```bash
pip install PyMuPDF spacy scikit-learn numpy
```

### Optional: Install spaCy English Model

```bash
python -m spacy download en_core_web_sm
```

**Note**: The tool will work without spaCy but with reduced text validation capabilities.

## Project Structure

```
project/
├── pdf_extractor.py          # Main extractor script
├── inputs/                   # Input PDF files directory
│   ├── document1.pdf
│   └── document2.pdf
└── output8/                  # Output JSON files directory
    ├── document1.json
    └── document2.json
```

## Usage

### Basic Usage

1. Place your PDF files in the `./inputs` directory
2. Run the script:
   ```bash
   python pdf_extractor.py
   ```
3. Check the `./output8` directory for generated JSON files

### Programmatic Usage

```python
from pdf_extractor import PDFHeadingExtractor

# Initialize the extractor
extractor = PDFHeadingExtractor()

# Extract headings from a PDF
result = extractor.extract_headings('path/to/document.pdf')

# Access the results
print(f"Title: {result['title']}")
print(f"Number of headings: {len(result['outline'])}")

# Process the outline
for heading in result['outline']:
    print(f"{heading['level']}: {heading['text']} (Page {heading['page']})")
```

## Output Format

The tool generates JSON files with the following structure:

```json
{
  "title": "Understanding AI",
  "outline": [
    {
      "level": "H1",
      "text": "Introduction",
      "page": 1
    },
    {
      "level": "H2",
      "text": "What is AI?",
      "page": 2
    },
    {
      "level": "H3",
      "text": "History of AI",
      "page": 3
    }
  ]
}
```

### Output Fields

- **title**: The extracted document title (string)
- **outline**: Array of heading objects
  - **level**: Heading level (H1, H2, H3, or H4)
  - **text**: The heading text content
  - **page**: Page number where the heading appears (1-based)

## Configuration Options

### PDFHeadingExtractor Parameters

The `PDFHeadingExtractor` class can be configured with the following parameters:

```python
class PDFHeadingExtractor:
    def __init__(self):
        self.min_heading_length = 5      # Minimum characters for valid headings
        self.max_heading_length = 200    # Maximum characters for valid headings
        self.header_footer_margin = 50   # Pixels to ignore at page edges
```

### Customizable Patterns

The extractor excludes certain patterns automatically:

- Page numbers (`page 1`, `page 2`, etc.)
- Pure numbers
- Dates in common formats
- Copyright notices
- Confidential/Draft markings
- URLs and email addresses

## Algorithm Details

### 1. Title Extraction

The algorithm examines the first 15 lines of the first page and:
- Validates text length (10-300 characters)
- Excludes common non-title patterns
- Selects the most appropriate candidate
- Falls back to filename if no suitable title found

### 2. Font Analysis

The tool analyzes fonts across multiple pages:
- Samples up to 10 pages plus middle and last pages
- Identifies the most common font size (body text)
- Calculates heading thresholds based on size ratios:
  - H1: 2.0× body size
  - H2: 1.6× body size
  - H3: 1.3× body size
  - H4: 1.1× body size

### 3. Heading Classification

For each text element, the algorithm:
- Validates text content and length
- Applies font size thresholds
- Checks for bold formatting
- Uses NLP validation (if available)
- Prevents title duplication
- Removes exact duplicates

### 4. Post-Processing

The final outline undergoes:
- Sorting by page and position
- Duplicate removal
- Fragment detection and cleanup
- Text normalization

## Troubleshooting

### Common Issues

**Issue**: No headings extracted
- **Solution**: Check if PDF has searchable text (not scanned images)
- **Solution**: Verify font sizes are sufficiently different

**Issue**: Too many false positives
- **Solution**: Adjust `min_heading_length` and `max_heading_length`
- **Solution**: Install spaCy model for better text validation

**Issue**: Missing headings
- **Solution**: Check if headings use non-standard formatting
- **Solution**: Review font analysis thresholds

### Debug Information

Enable debug output by modifying the `process_pdf` function:

```python
def process_pdf(input_path: str, output_dir: str):
    extractor = PDFHeadingExtractor()
    result = extractor.extract_headings(input_path)
    
    # Debug output
    print(f"Font analysis: {result.get('font_stats', 'N/A')}")
    
    # ... rest of function
```

## Performance Considerations

- **Memory**: Large PDFs may require substantial memory for font analysis
- **Speed**: Processing time scales with document length and complexity
- **Accuracy**: Documents with consistent formatting yield better results

## Limitations

- Requires searchable PDF text (not scanned documents)
- Performance depends on consistent font usage
- May struggle with highly creative or inconsistent layouts
- Header/footer detection relies on margin-based heuristics

## Dependencies

### Required
- **PyMuPDF (fitz)**: PDF text extraction and analysis
- **scikit-learn**: Clustering algorithms (imported but not actively used)
- **numpy**: Numerical operations

### Optional
- **spaCy**: Natural language processing for text validation
- **en_core_web_sm**: English language model for spaCy

## License and Support

This tool is provided as-is for educational and commercial use. For support or feature requests, please refer to the project documentation or contact the development team.

## Version History

- **v1.0**: Initial release with basic heading extraction
- **v1.1**: Added NLP validation and improved font analysis
- **v1.2**: Enhanced duplicate detection and output formatting
- **v2.0**: Updated output format to match specifications