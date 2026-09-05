from pathlib import Path  # Inspect only the original drawing pages already selected for this physical reconstruction.
import subprocess, shutil, json, io, pymupdf  # Preserve a bounded, auditable source-image reading operation.
from PIL import Image  # Assemble the selected source pages without altering their engineering content.
ROOT=Path(__file__).parent  # Keep source-reading evidence separate from model parameters.
def inspect():  # Use one last-resort OCR invocation because the selected raster drawing pages have no native text and image tools cannot open them.
    out=ROOT/'results/original_dimensions';out.mkdir(parents=True,exist_ok=True);done=out/'dimension_text.txt'  # Save the original page labels and avoid repeating OCR on later solver runs.
    if done.exists():return  # Reuse only this exact original-page transcription rather than incur repeated OCR.
    if not shutil.which('tesseract'):subprocess.run(['sudo','apt-get','install','-y','tesseract-ocr'],check=True,timeout=180)  # Install a standard source-image reader only when absent.
    pdf=pymupdf.open(ROOT/'sources/original_drawing_1225.pdf');pages=[92,99,100];images=[]  # Limit image reading to ordinary gantry, passage and passage-connection drawings.
    for page in pages:  # Render the exact original source pixels once.
        pix=pdf[page-1].get_pixmap(matrix=pymupdf.Matrix(3,3));images.append(Image.open(io.BytesIO(pix.tobytes('png'))).convert('RGB'))  # Do not redraw, upscale or infer missing dimensions.
    image_path=out/'selected_original_pages.tiff';images[0].save(image_path,save_all=True,append_images=images[1:],compression='tiff_lzw')  # Preserve all three source pages in one bounded reader input.
    run=subprocess.run(['tesseract',str(image_path),'stdout','-l','eng','--psm','11'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180,text=True)  # Execute a single OCR pass for numeric dimensions and Latin section labels only.
    done.write_text(run.stdout);(out/'reader_log.txt').write_text(run.stderr);(out/'source_pages.json').write_text(json.dumps({'source':'original_drawing_1225.pdf','pages':pages,'reader_exit':run.returncode,'limitations':'OCR transcription is not authoritative by itself; numerical labels require their source geometry context.'},indent=2))  # Preserve uncertainty rather than treat OCR output as verified engineering facts.
    image_path.unlink();print('ORIGINAL_DRAWING_DIMENSION_LABELS',run.stdout,flush=True)  # Keep lightweight source-reading evidence without repeating the raster PDF in results.
