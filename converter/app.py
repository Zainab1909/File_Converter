from flask import Flask, render_template, request, send_file, redirect, url_for
import os
POPPLER_PATH = r'C:\poppler-24.08.0\Library\bin'
os.environ["PATH"] += os.pathsep + POPPLER_PATH
import uuid
from docx2pdf import convert as docx2pdf
from pdf2docx import Converter
from pdf2image import convert_from_path
import pytesseract
from flask import send_from_directory
from docx import Document
import fitz  # PyMuPDF
from PIL import Image

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
CONVERTED_FOLDER = 'converted'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CONVERTED_FOLDER, exist_ok=True)

# Paths (edit if needed)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def is_scanned_pdf(filepath):
    doc = fitz.open(filepath)
    for page in doc:
        if page.get_text().strip():
            return False
    return True

def ocr_pdf_to_docx(pdf_path, docx_path):
    try:
        pages = convert_from_path(pdf_path, poppler_path=POPPLER_PATH)
        doc = Document()
        for page in pages:
            text = pytesseract.image_to_string(page)
            doc.add_paragraph(text)
        doc.save(docx_path)
    except Exception as e:
        print(f"OCR conversion failed: {e}")
        raise e

@app.route('/')
def index():
    return render_template('index.html')

import pythoncom
import win32com.client
import time  # optional

@app.route('/convert_to_pdf', methods=['POST'])
def convert_to_pdf():
    pythoncom.CoInitialize()

    file = request.files['file']
    ext = os.path.splitext(file.filename)[1].lower()

    if ext not in ['.doc', '.docx']:
        return render_template('index.html', error="Only DOC and DOCX files are supported.")

    # Create and save file
    input_filename = f"{uuid.uuid4()}{ext}"
    temp_input = os.path.abspath(os.path.join(UPLOAD_FOLDER, input_filename))
    output_filename = f"{uuid.uuid4()}.pdf"
    output_path = os.path.abspath(os.path.join(CONVERTED_FOLDER, output_filename))
    file.save(temp_input)

    try:
        time.sleep(0.5)  # Optional: let file settle
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        word.DisplayAlerts = False

        doc = word.Documents.Open(temp_input)
        doc.SaveAs(output_path, FileFormat=17)
        doc.Close()
        word.Quit()
    except Exception as e:
        return render_template('index.html', error=f"Conversion failed: {e}")

    original_name = os.path.splitext(file.filename)[0] + ".pdf"
    return redirect(url_for('show_preview', filename=os.path.basename(output_path), original=original_name))



@app.route('/convert_to_word', methods=['POST'])
def convert_to_word():
    file = request.files['file']
    output_format = request.form['output_format']
    ext = os.path.splitext(file.filename)[1].lower()
    if ext != '.pdf':
        return render_template('index.html', error="Only PDF files are supported for this conversion.")

    temp_input = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}.pdf")
    output_ext = '.docx' if output_format == 'docx' else '.doc'
    output_path = os.path.join(CONVERTED_FOLDER, f"{uuid.uuid4()}{output_ext}")
    file.save(temp_input)

    if is_scanned_pdf(temp_input):
        ocr_pdf_to_docx(temp_input, output_path)
    else:
        cv = Converter(temp_input)
        cv.convert(output_path)
        cv.close()

    original_name = os.path.splitext(file.filename)[0] + output_ext
    return redirect(url_for('show_preview', filename=os.path.basename(output_path), original=original_name))

ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']

def is_image_file(filename):
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_IMAGE_EXTENSIONS

@app.route('/convert_image_to_pdf', methods=['POST'])
def convert_image_to_pdf():
    file = request.files['file']
    if not is_image_file(file.filename):
        return render_template('index.html', error="Only image files are supported for this conversion.")

    # Use original filename (without extension) + .pdf
    original_basename = os.path.splitext(file.filename)[0]
    output_filename = original_basename + ".pdf"

    ext = os.path.splitext(file.filename)[1].lower()
    temp_input = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}{ext}")
    output_path = os.path.join(CONVERTED_FOLDER, f"{uuid.uuid4()}.pdf")
    file.save(temp_input)

    try:
        image = Image.open(temp_input).convert("RGB")
        image.save(output_path)
    except Exception as e:
        return render_template('index.html', error=f"Image to PDF conversion failed: {e}")

    return redirect(url_for('show_preview', filename=os.path.basename(output_path), original=output_filename))

@app.route('/convert_pdf_to_images', methods=['POST'])
def convert_pdf_to_images():
    file = request.files['file']
    image_format = request.form['image_format'].lower()
    ext = os.path.splitext(file.filename)[1].lower()
    if ext != '.pdf':
        return render_template('index.html', error="Only PDF files are supported for this conversion.")

    format_map = {
        "jpg": "JPEG",
        "jpeg": "JPEG",
        "png": "PNG",
        "bmp": "BMP",
        "tiff": "TIFF",
        "webp": "WEBP"
    }

    if image_format not in format_map:
        return render_template('index.html', error=f"Unsupported image format: {image_format}")

    pil_format = format_map[image_format]

    temp_input = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}.pdf")
    file.save(temp_input)

    try:
        images = convert_from_path(temp_input, poppler_path=POPPLER_PATH)
        output_files = []
        for i, image in enumerate(images):
            img_path = os.path.join(CONVERTED_FOLDER, f"{uuid.uuid4()}.{image_format}")
            image.save(img_path, format=pil_format)
            output_files.append(img_path)

        if len(output_files) == 1:
            original_name = os.path.splitext(file.filename)[0] + f".{image_format}"
            return redirect(url_for('show_preview', filename=os.path.basename(output_files[0]), original=original_name))
        else:
            import zipfile
            zip_path = os.path.join(CONVERTED_FOLDER, f"{uuid.uuid4()}.zip")
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for img_file in output_files:
                    zipf.write(img_file, os.path.basename(img_file))
            original_name = os.path.splitext(file.filename)[0] + ".zip"
            return redirect(url_for('show_preview', filename=os.path.basename(zip_path), original=original_name))

    except Exception as e:
        return render_template('index.html', error=f"PDF to image conversion failed: {e}")

@app.route('/show_preview/<filename>')
def show_preview(filename):
    ext = os.path.splitext(filename)[1].lower()
    file_url = url_for('preview_file', filename=filename)
    original_name = request.args.get('original', filename)
    return render_template('preview.html',
                           file_url=file_url,
                           ext=ext,
                           filename=original_name,
                           converted_filename=filename)

@app.route('/preview/<path:filename>')
def preview_file(filename):
    original = request.args.get('original', filename)
    return send_from_directory(CONVERTED_FOLDER, filename, as_attachment=False, download_name=original)

@app.route('/download/<path:filename>')
def download_file(filename):
    original = request.args.get('original', filename)
    return send_from_directory(CONVERTED_FOLDER, filename, as_attachment=True, download_name=original)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)


