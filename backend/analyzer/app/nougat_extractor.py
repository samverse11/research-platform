import os
import re
import shutil
import subprocess
import tempfile
import pathlib
from typing import Dict, Any


def _nougat_executable() -> str:
    exe = shutil.which("nougat")
    if exe:
        return exe
    raise FileNotFoundError(
        "Nougat CLI not found on PATH. Install with: pip install nougat-ocr "
        "(requires PyTorch; first run downloads model weights)."
    )


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
            nougat_bin = _nougat_executable()
            cmd = [
                nougat_bin,
                pdf_path,
                "-o", out_dir,
                "--no-skipping",
            ]
            
            # Using timeout 600s (10 minutes)
            subprocess.run(cmd, check=True, timeout=600, capture_output=True, text=True)
            
            # Nougat writes markdown next to the PDF basename (.mmd or .md depending on version)
            pdf_base = pathlib.Path(pdf_path).stem
            out = pathlib.Path(out_dir)
            candidates = sorted(out.glob(f"{pdf_base}.mmd")) + sorted(out.glob(f"{pdf_base}.md"))
            mmd_path = str(candidates[0]) if candidates else ""

            if not mmd_path or not os.path.exists(mmd_path):
                found = list(out.iterdir()) if out.exists() else []
                names = [p.name for p in found[:20]]
                raise RuntimeError(
                    f"Nougat finished but no {pdf_base}.mmd/.md in {out_dir}. "
                    f"Files seen: {names or '(empty)'}"
                )
                
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
