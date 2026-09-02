# Legacy LayoutParser experiment

The notebook and `final.csv` preserve the earlier LayoutParser/Tesseract
experiment. They are not active entry points: the notebook needs obsolete
Detectron2 dependencies and uses paths from the old repository layout. Its image
cleanup cell deletes files in the target directory. The CSV contains paths to
images that are not included here.

The superseded PyPDF2 scripts were deleted. Use the current experiments in the
neighboring directories for reproducible work.
