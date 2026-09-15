from __future__ import annotations

from .config import Settings
from .models import SourceDocument
from .rag_service import RagService


def main() -> None:
    service = RagService(Settings.from_env())

    # The exercise starts from extracted text. In a real PDF/DOCX pipeline, a parser should
    # populate source/page/version metadata before calling ingest_documents().
    service.ingest_documents(
        [
            SourceDocument(
                text="El protocolo interno establece ...",
                source="protocolo_demo.pdf",
                page=12,
                version="3.2",
                document_id="protocol-demo",
            )
        ]
    )

    result = service.ask("¿Qué establece el protocolo?")
    print(result.text)
    print(result.citations)


if __name__ == "__main__":
    main()
