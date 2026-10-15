"""Regression checks for DOCX upload validation before document parsing."""

import io
import unittest

from docx import Document
from fastapi import HTTPException

from app.upload_validation import DOCX_MEDIA_TYPE, validate_docx_upload


def make_docx() -> bytes:
    document = Document()
    document.add_paragraph("Проверочный текст")
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


class UploadValidationTests(unittest.TestCase):
    def test_accepts_real_docx(self) -> None:
        validate_docx_upload(
            filename="work.docx",
            content_type=DOCX_MEDIA_TYPE,
            document_bytes=make_docx(),
        )

    def test_rejects_fake_docx_and_incorrect_content_type(self) -> None:
        with self.assertRaises(HTTPException) as fake_file:
            validate_docx_upload(
                filename="malicious.docx",
                content_type=DOCX_MEDIA_TYPE,
                document_bytes=b"PKnot-a-real-ooxml-document",
            )
        self.assertEqual(fake_file.exception.status_code, 400)

        with self.assertRaises(HTTPException) as bad_type:
            validate_docx_upload(
                filename="work.docx",
                content_type="application/pdf",
                document_bytes=make_docx(),
            )
        self.assertEqual(bad_type.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
