import json
import os
import re
import fitz # PyMuPDF
import spacy
import numpy as np
from collections import defaultdict, Counter
from typing import List, Dict, Optional, Tuple
from sklearn.cluster import KMeans

class PDFHeadingExtractor:
    def __init__(self):
        # Load English NLP model
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            print("Warning: spaCy model not found. NLP validation will be disabled.")
            self.nlp = None
        
        # Configuration
        self.min_heading_length = 5 # Minimum length for valid headings
        self.max_heading_length = 200
        self.header_footer_margin = 50
        self.title_size = None
        
        # Patterns to exclude
        self.exclude_patterns = [
            r'^page \d+$',
            r'^\d+$',
            r'^[A-Za-z]+\s+\d{1,2},\s+\d{4}$', # Dates
            r'^©|©|All rights reserved',
            r'^Confidential',
            r'^Draft',
            r'^\s*$'
        ]
        
        # Track document title to avoid duplication
        self.document_title = None
        self.seen_headings = set()

    def extract_headings(self, pdf_path: str) -> Dict:
        """Extract title and headings from PDF"""
        doc = fitz.open(pdf_path)
        
        # Extract title first
        title = self._extract_title(doc)
        self.document_title = title.strip().lower()
        
        # Analyze font characteristics
        font_analysis = self._analyze_document_fonts(doc)
        
        outline = []
        
        # Process each page
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            page_headings = self._extract_page_headings(page, page_num + 1, font_analysis)
            outline.extend(page_headings)
        
        doc.close()
        
        # Clean up the outline
        outline = self._post_process_outline(outline)
        
        # Return in the requested format (removed font_stats)
        return {
            "title": title,
            "outline": outline
        }

    def _extract_title(self, doc) -> str:
        """Extract document title from first page"""
        first_page = doc.load_page(0)
        
        # Get clean text lines
        page_text = first_page.get_text()
        lines = [line.strip() for line in page_text.split('\n') if line.strip()]
        
        # Find the best title candidate
        for line in lines[:15]: # Check first 15 lines
            line = line.strip()
            if self._is_valid_title(line):
                # Clean up the title
                title = re.sub(r'\s+', ' ', line).strip()
                
                # Get font size for this title
                title_size = self._get_title_font_size(first_page, title)
                if title_size:
                    self.title_size = title_size
                else:
                    self.title_size = 16.0
                
                return title
        
        # Fallback to filename
        return os.path.basename(doc.name).replace(".pdf", "")

    def _is_valid_title(self, text: str) -> bool:
        """Check if text is a valid title candidate"""
        if len(text) < 10 or len(text) > 300:
            return False
        
        # Skip common non-title patterns
        text_lower = text.lower()
        invalid_starts = ['page ', 'copyright', '©', 'confidential', 'draft']
        if any(text_lower.startswith(start) for start in invalid_starts):
            return False
        
        # Skip URLs
        if re.match(r'^https?://', text_lower):
            return False
        
        # Skip pure numbers or dates
        if re.match(r'^\d+$', text) or re.match(r'^\d{1,2}/\d{1,2}/\d{4}$', text):
            return False
        
        return True

    def _get_title_font_size(self, page, title_text: str) -> Optional[float]:
        """Get font size for the title text"""
        blocks = page.get_text("dict")["blocks"]
        title_words = set(title_text.lower().split())
        max_size = 0
        
        for block in blocks:
            if "lines" not in block:
                continue
                
            for line in block["lines"]:
                line_text = ""
                line_size = 0
                
                for span in line["spans"]:
                    line_text += span["text"]
                    line_size = max(line_size, span["size"])
                
                line_words = set(line_text.lower().split())
                # Check if this line contains significant portion of title words
                overlap = len(title_words.intersection(line_words))
                if overlap >= min(3, len(title_words) * 0.6):
                    max_size = max(max_size, line_size)
        
        return max_size if max_size > 0 else None

    def _analyze_document_fonts(self, doc) -> Dict:
        """Analyze font sizes across the document"""
        font_sizes = []
        
        # Sample pages for analysis
        total_pages = len(doc)
        sample_pages = list(range(0, min(total_pages, 10)))
        if total_pages > 10:
            sample_pages.extend([total_pages//2, total_pages-1])
        
        for page_num in sample_pages:
            page = doc.load_page(page_num)
            blocks = page.get_text("dict")["blocks"]
            
            for block in blocks:
                if "lines" not in block:
                    continue
                    
                for line in block["lines"]:
                    for span in line["spans"]:
                        # Skip header/footer
                        if (span["origin"][1] < self.header_footer_margin or 
                            span["origin"][1] > page.rect.height - self.header_footer_margin):
                            continue
                        
                        text = span["text"].strip()
                        if len(text) >= 3:
                            font_sizes.append(span["size"])
        
        if not font_sizes:
            return self._get_default_thresholds()
        
        # Find the most common font size (body text)
        size_counter = Counter(font_sizes)
        body_size = size_counter.most_common(1)[0][0]
        
        # Calculate thresholds
        unique_sizes = sorted(set(font_sizes), reverse=True)
        
        h1_threshold = body_size * 2.0
        h2_threshold = body_size * 1.6
        h3_threshold = body_size * 1.3
        h4_threshold = body_size * 1.1
        
        # Adjust based on actual sizes
        if len(unique_sizes) >= 4:
            h1_threshold = max(h1_threshold, unique_sizes[0])
            h2_threshold = max(h2_threshold, unique_sizes[1])
            h3_threshold = max(h3_threshold, unique_sizes[2])
            if len(unique_sizes) >= 4:
                h4_threshold = max(h4_threshold, unique_sizes[3])
        
        return {
            "base_size": body_size,
            "h1_threshold": h1_threshold,
            "h2_threshold": h2_threshold,
            "h3_threshold": h3_threshold,
            "h4_threshold": h4_threshold,
            "all_sizes": unique_sizes,
            "size_distribution": dict(size_counter)
        }

    def _get_default_thresholds(self) -> Dict:
        """Default thresholds when analysis fails"""
        return {
            "base_size": 12,
            "h1_threshold": 18,
            "h2_threshold": 16,
            "h3_threshold": 14,
            "h4_threshold": 13,
            "all_sizes": [18, 16, 14, 13, 12],
            "size_distribution": {}
        }

    def _extract_page_headings(self, page, page_num: int, font_analysis: Dict) -> List[Dict]:
        """Extract headings from a single page"""
        blocks = page.get_text("dict")["blocks"]
        headings = []
        
        for block in blocks:
            if "lines" not in block:
                continue
                
            for line in block["lines"]:
                if not line.get("spans"):
                    continue
                
                # Combine spans in the same line
                combined_text = ""
                max_size = 0
                min_y = float('inf')
                flags = 0
                font = ""
                
                for span in line["spans"]:
                    combined_text += span["text"]
                    if span["size"] > max_size:
                        max_size = span["size"]
                        flags = span["flags"]
                        font = span["font"]
                    min_y = min(min_y, span["origin"][1])
                
                combined_text = combined_text.strip()
                
                if combined_text and self._is_valid_heading_text(combined_text):
                    heading = self._classify_heading(
                        combined_text, max_size, min_y, page_num, flags, font, font_analysis
                    )
                    if heading:
                        headings.append(heading)
        
        return headings

    def _is_valid_heading_text(self, text: str) -> bool:
        """Validate if text could be a heading"""
        text = text.strip()
        
        # Length check
        if len(text) < self.min_heading_length or len(text) > self.max_heading_length:
            return False
        
        # Skip excluded patterns
        text_lower = text.lower()
        for pattern in self.exclude_patterns:
            if re.match(pattern, text_lower):
                return False
        
        # Skip pure numbers
        if re.match(r'^\d+$', text):
            return False
        
        # Skip very fragmented text
        if re.match(r'^[^a-zA-Z]*[a-zA-Z]{1,2}[^a-zA-Z]*$', text):
            return False
        
        # Skip URLs and emails
        if re.match(r'^https?://|^www\.|@.*\.', text_lower):
            return False
        
        # Check alphanumeric content
        alphanumeric_chars = sum(c.isalnum() for c in text)
        if alphanumeric_chars < max(3, len(text) * 0.5):
            return False
        
        # Check for meaningful words
        words = text.split()
        if not words or all(len(word.strip('.,!?;:')) <= 2 for word in words):
            return False
        
        return True

    def _classify_heading(self, text: str, size: float, y_pos: float, 
                         page_num: int, flags: int, font: str, font_analysis: Dict) -> Optional[Dict]:
        """Classify text as a heading and determine its level"""
        
        # Skip if this is the document title
        if self.document_title and self._is_title_duplicate(text):
            return None
        
        # Skip if same size as title on first page (likely title repetition)
        if (self.title_size and abs(size - self.title_size) < 0.1 and 
            page_num > 1 and not self._looks_like_section_title(text)):
            return None
        
        # Determine heading level
        level = self._determine_heading_level(size, flags, font_analysis)
        if not level:
            return None
        
        # NLP validation
        if not self._is_heading_like(text):
            return None
        
        # Deduplication
        text_key = f"{level}:{text.lower()}"
        if text_key in self.seen_headings:
            return None
        self.seen_headings.add(text_key)
        
        # Return in the requested format (1-based page numbering)
        return {
            "level": level,
            "text": text,
            "page": page_num
        }

    def _is_title_duplicate(self, text: str) -> bool:
        """Check if text is a duplicate of the document title"""
        text_clean = text.strip().lower()
        
        # Exact match
        if text_clean == self.document_title:
            return True
        
        # Check for substantial overlap
        if len(self.document_title) > 10:
            if (text_clean in self.document_title or 
                self.document_title in text_clean or
                self._text_similarity(text_clean, self.document_title) > 0.7):
                return True
        
        return False

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts based on word overlap"""
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0

    def _determine_heading_level(self, size: float, flags: int, font_analysis: Dict) -> Optional[str]:
        """Determine heading level based on font size and formatting"""
        if size >= font_analysis["h1_threshold"]:
            return "H1"
        elif size >= font_analysis["h2_threshold"]:
            return "H2"
        elif size >= font_analysis["h3_threshold"]:
            return "H3"
        elif size >= font_analysis["h4_threshold"]:
            return "H4"
        else:
            # Check if it's bold (formatting-based heading)
            if flags & 2**4: # Bold flag
                if size >= font_analysis["base_size"] * 1.05:
                    return "H4"
        
        return None

    def _looks_like_section_title(self, text: str) -> bool:
        """Check if text looks like a section title"""
        section_patterns = [
            r'^(chapter|section|part|appendix|introduction|conclusion|summary|background)',
            r'^\d+\.', # Numbered sections
            r'^[A-Z][^.]*:', # Capitalized with colon
            r'^(phase|timeline|milestone)',
            r'for each .* it could mean',
        ]
        
        text_lower = text.lower().strip()
        return any(re.match(pattern, text_lower) for pattern in section_patterns)

    def _is_heading_like(self, text: str) -> bool:
        """Validate if text is heading-like using NLP or rules"""
        if not self.nlp:
            return self._is_heading_like_rule_based(text)
        
        # Skip very long text
        if len(text.split()) > 15:
            return False
        
        try:
            doc = self.nlp(text)
            
            # Allow common heading patterns
            if self._looks_like_section_title(text):
                return True
            
            # Allow questions
            if text.strip().endswith('?'):
                return True
            
            # Allow short text
            if len(doc) <= 3:
                return True
            
            # Check content words ratio
            content_pos = {"NOUN", "PROPN", "ADJ", "NUM"}
            content_count = sum(1 for token in doc if token.pos_ in content_pos)
            
            if content_count / len(doc) >= 0.4:
                return True
            
            # Allow proper nouns or numbers
            if any(token.pos_ in {"PROPN", "NUM"} for token in doc):
                return True
            
            return False
            
        except Exception:
            return self._is_heading_like_rule_based(text)

    def _is_heading_like_rule_based(self, text: str) -> bool:
        """Rule-based heading validation"""
        if self._looks_like_section_title(text):
            return True
        
        if text.isupper() or text.istitle():
            return True
        
        if len(text.split()) <= 8:
            return True
        
        if len(text.split()) > 15:
            return False
        
        return True

    def _post_process_outline(self, outline: List[Dict]) -> List[Dict]:
        """Clean up and deduplicate the outline"""
        if not outline:
            return outline
        
        # Sort by page then by position
        outline.sort(key=lambda x: (x['page'], x.get('y_pos', 0)))
        
        # Remove duplicates and fragments
        cleaned_outline = []
        seen_texts = set()
        
        for item in outline:
            text = item['text'].strip()
            text_key = text.lower()
            
            # Skip exact duplicates
            if text_key in seen_texts:
                continue
            
            # Check for fragments
            is_fragment = False
            for seen_text in list(seen_texts):
                # Skip if this is a fragment of something we've seen
                if (len(text_key) < len(seen_text) and 
                    text_key in seen_text and 
                    len(text_key) < len(seen_text) * 0.8):
                    is_fragment = True
                    break
                # Remove previous fragment if this is the complete version
                elif (len(seen_text) < len(text_key) and 
                      seen_text in text_key and 
                      len(seen_text) < len(text_key) * 0.8):
                    cleaned_outline = [h for h in cleaned_outline 
                                     if h['text'].strip().lower() != seen_text]
                    seen_texts.discard(seen_text)
            
            if not is_fragment:
                seen_texts.add(text_key)
                cleaned_outline.append(item)
        
        return cleaned_outline

def save_to_json(data: Dict, output_path: str):
    """Save extracted data to JSON file"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def process_pdf(input_path: str, output_dir: str):
    """Process a single PDF file"""
    extractor = PDFHeadingExtractor()
    result = extractor.extract_headings(input_path)
    
    output_filename = os.path.basename(input_path).replace('.pdf', '.json')
    output_path = os.path.join(output_dir, output_filename)
    save_to_json(result, output_path)
    
    print(f"Processed {input_path} -> {output_path}")
    print(f"Found {len(result['outline'])} headings")

def docker_main():
    input_dir = '/app/input'
    output_dir = '/app/output'
    
    # Create output directory
    try:
        os.makedirs(output_dir, exist_ok=True)
    except OSError as e:
        print(f"Error creating output directory: {e}")
        return

    # Process all PDFs
    for filename in sorted(os.listdir(input_dir)):
        if filename.lower().endswith('.pdf'):
            input_path = os.path.join(input_dir, filename)
            try:
                print(f"Processing {filename}...")
                process_pdf(input_path, output_dir)
            except Exception as e:
                print(f"Error processing {filename}: {str(e)}")

if __name__ == '__main__':
    docker_main()

