import os
import re
import subprocess
import tempfile
import pathlib
from typing import Dict, Any

def extract_with_nougat(pdf_path: str) -> Dict[str, Any]:
    """
    Runs Meta's Nougat OCR on the given PDF to extract LaTeX-perfect multi-markdown.
    Creates a dict formatted consistently with the PyMuPDF extractor.
    """
    # Create a temporary directory to hold the nougat output
    with tempfile.TemporaryDirectory() as out_dir:
        try:
            # nougat-ocr invokes the CLI
            # using 'nougat pdf_path --out out_dir --no-skipping'
            # (No skipping prevents Nougat from dropping pages it thinks are bad)
            print(f"  [Nougat] Booting vision transformer for {os.path.basename(pdf_path)}... (This may take minutes)")
            cmd = [
                "nougat",
                pdf_path,
                "--out", out_dir,
                "--no-skipping"
            ]
            
            # Using timeout 600s (10 minutes)
            subprocess.run(cmd, check=True, timeout=600, capture_output=True, text=True)
            
            # nougat outputs to a .mmd file named the same as the pdf
            pdf_base = pathlib.Path(pdf_path).stem
            mmd_path = os.path.join(out_dir, f"{pdf_base}.mmd")
            
            if not os.path.exists(mmd_path):
                raise RuntimeError(f"Nougat completed but {mmd_path} was not generated.")
                
            with open(mmd_path, "r", encoding="utf-8") as f:
                mmd_text = f.read()
                
            # Parse MMD into sections
            return parse_mmd_to_sections(mmd_text)
            
        except subprocess.TimeoutExpired:
            print("  [Nougat] Extraction timed out. Falling back to PyMuPDF.")
            raise
        except subprocess.CalledProcessError as e:
            print(f"  [Nougat] CLI process failed: {e.stderr[-500:]}")
            raise
        except Exception as e:
            print(f"  [Nougat] Extraction failed: {str(e)}")
            raise

def parse_mmd_to_sections(mmd_text: str) -> Dict[str, Any]:
    """
    Parses Nougat `.mmd` output which contains Markdown formatting
    and perfectly extracted math blocks into sections.
    """
    sections = []
    lines = mmd_text.split('\n')
    
    current_heading = "Introduction"
    current_text = []
    
    for line in lines:
        if line.startswith("#"):
            # Clean heading
            heading = re.sub(r'^#+\s*', '', line).strip()
            
            # Save previous section if it has text
            section_content = "\n".join(current_text).strip()
            if section_content:
                sections.append({
                    "heading": current_heading,
                    "text": section_content,
                    "page_num": len(sections) + 1,  # Approx, MMD loses precise pages
                    "citations": [],
                    "has_images": False
                })
            
            current_heading = heading
            current_text = []
        else:
            current_text.append(line)
            
    # Add final section
    section_content = "\n".join(current_text).strip()
    if section_content:
        sections.append({
            "heading": current_heading,
            "text": section_content,
            "page_num": len(sections) + 1,
            "citations": [],
            "has_images": False
        })
        
    return {
        "text": mmd_text,
        "pages": len(sections), # Estimating pages as section chunks
        "sections": sections,
        "images": [] # Nougat natively compiles image math to LaTeX text so no specific image slices exist here
    }
