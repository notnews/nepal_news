import PyPDF2
import os

path = "../"
for fil in os.listdir(path):  # iterate over the pdf file in path folder
    if ".pdf" in fil:
        page = ""
        pdfobj = open(fil, "rb")
        pdfreader = PyPDF2.PdfFileReader(pdfobj)
        # One Pdf can have multiple pages
        for x in range(pdfreader.getNumPages()):
            pageobj = pdfreader.getPage(x)
            page += pageobj.extractText()
        with open("./text_outputs/" + fil[:4] + ".txt", "a+") as fp:
            fp.write(page)



# convert pdf to image
import os
import pdf2image

def pdf_to_tiff(path):
    for fil in os.listdir(path):
        if '.pdf' not in fil:
            continue
        pil_images=pdf2image.convert_from_path(
                    f'{path}/{fil}',
                    dpi=500,
                    output_folder='pdf2images/',
                    first_page=None,
                    last_page=None,
                    fmt='jpg',
                    thread_count=1,
                    userpw=None,
                    use_cropbox=False,
                    strict=False,
                )
        for idx, image in enumerate(pil_images, 1):
            os.rename(image.filename, '/'.join(image.filename.split('/')[:-1])+f'/{fil}_{idx}.tiff.test')

pdf_to_tiff('./')