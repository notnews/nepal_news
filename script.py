import PyPDF2
import os
path='./'
for fil in os.listdir(path):
    if '.pdf' in fil:
        page = ''
        pdfobj=open(fil,'rb')
        pdfreader=PyPDF2.PdfFileReader(pdfobj)
        for x in range(pdfreader.getNumPages()):
            pageobj=pdfreader.getPage(x)
            page+=pageobj.extractText()
        with open(fil[:4]+'.txt','w') as fp:
            fp.write(page)