from docxtpl import DocxTemplate
import datetime
import os

class DocumentService:
    def __init__(self, template_dir="templates", output_dir="storage/contracts"):
        self.template_dir = template_dir
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate_contract(self, template_name, data):
        # A data egy szótár legyen: {'name': '...', 'address': '...', 'date': '...'}
        # Példa sablon: "szerzodes_sablon.docx"
        
        template_path = os.path.join(self.template_dir, template_name)
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Sablon fájl nem található: {template_path}")

        doc = DocxTemplate(template_path)
        
        # Mai dátum hozzáadása a kitöltéshez
        data['today'] = datetime.datetime.now().strftime("%Y. %m. %d.")
        
        # Sablon kitöltése Jinja2 szintaxissal (pl: {{ name }})
        doc.render(data)
        
        filename = f"szerzodes_{data.get('nev', 'Ismeretlen')}_{datetime.datetime.now().timestamp()}.docx"
        output_path = os.path.join(self.output_dir, filename)
        doc.save(output_path)
        
        return output_path

    def convert_to_pdf(self, docx_path):
        # 1. Ha Windows-on vagyunk (Lokális fejlesztés)
        if os.name == 'nt':
            try:
                from docx2pdf import convert
                pdf_path = docx_path.replace(".docx", ".pdf")
                convert(docx_path, pdf_path)
                return pdf_path
            except Exception as e:
                return f"Hiba: {str(e)}"
        
        # 2. Ha Linux-on vagyunk (pl. Render szerver)
        else:
            try:
                # LibreOffice-t használunk a headless konverzióhoz Linux alatt
                import subprocess
                pdf_path = docx_path.replace(".docx", ".pdf")
                subprocess.run(['libreoffice', '--headless', '--convert-to', 'pdf', docx_path, '--outdir', self.output_dir], check=True)
                return pdf_path
            except Exception as e:
                return f"Linux PDF hiba (LibreOffice szükséges): {str(e)}"

# Használati példa logic az API-hoz:
# doc_service = DocumentService()
# docx_file = doc_service.generate_contract("dualis_sablon.docx", extracted_data)
# pdf_file = doc_service.convert_to_pdf(docx_file)
