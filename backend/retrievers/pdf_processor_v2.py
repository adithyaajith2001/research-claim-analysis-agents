"""
Improved PDF Processor

Responsibilities:
1. Download research paper PDFs.
2. Extract text from the complete PDF by default.
3. Store extracted text in StandardPaper.raw_metadata["raw_text"].
4. Store text length in StandardPaper.raw_metadata["text_length"].
5. Preserve useful metadata from papers.json.
6. Fail gracefully so the pipeline can fall back to the abstract.

Development note:
verify_ssl=False is used by default because the current development
environment has SSL certificate verification problems.
For production, use proper CA certificates instead.
"""

import json
import os
from io import BytesIO
from typing import Optional, List, Dict, Any

import requests
import PyPDF2

from paper_schema import StandardPaper


class PDFProcessor:

    def __init__(
        self,
        verify_ssl: bool = False,
        max_pages: Optional[int] = None
    ):
        """
        Args:
            verify_ssl:
                Whether to verify SSL certificates when downloading PDFs.

            max_pages:
                Maximum number of pages to extract.

                None = extract the complete PDF.
        """

        self.verify_ssl = verify_ssl
        self.max_pages = max_pages


    # =========================================================
    # BUILD STANDARD PAPER FROM JSON DICT
    # =========================================================

    def _standard_paper_from_dict(
        self,
        paper_dict: Dict[str, Any]
    ) -> StandardPaper:
        """
        Convert the application's papers.json format into the
        StandardPaper format.

        The JSON file contains fields such as:
            id
            published_date
            updated_date
            metadata_tags
            raw_text
            text_length

        Some of these are not constructor arguments of
        StandardPaper, so they are preserved inside raw_metadata.
        """

        # -----------------------------------------------------
        # Existing raw metadata
        # -----------------------------------------------------

        raw_metadata = paper_dict.get(
            "raw_metadata",
            {}
        )


        if not isinstance(
            raw_metadata,
            dict
        ):

            raw_metadata = {}


        # -----------------------------------------------------
        # Preserve application metadata
        # -----------------------------------------------------

        if paper_dict.get(
            "id"
        ) is not None:

            raw_metadata[
                "application_id"
            ] = paper_dict.get(
                "id"
            )


        if paper_dict.get(
            "published_date"
        ):

            raw_metadata[
                "published_date"
            ] = paper_dict.get(
                "published_date"
            )


        if paper_dict.get(
            "updated_date"
        ):

            raw_metadata[
                "updated_date"
            ] = paper_dict.get(
                "updated_date"
            )


        if paper_dict.get(
            "metadata_tags"
        ) is not None:

            raw_metadata[
                "metadata_tags"
            ] = paper_dict.get(
                "metadata_tags"
            )


        # -----------------------------------------------------
        # Preserve already-existing raw text
        # -----------------------------------------------------

        existing_raw_text = (
            paper_dict.get(
                "raw_text",
                ""
            )
            or raw_metadata.get(
                "raw_text",
                ""
            )
            or ""
        )


        if existing_raw_text:

            raw_metadata[
                "raw_text"
            ] = existing_raw_text


        existing_text_length = (
            paper_dict.get(
                "text_length"
            )
            or raw_metadata.get(
                "text_length"
            )
            or 0
        )


        raw_metadata[
            "text_length"
        ] = existing_text_length


        # -----------------------------------------------------
        # Build only fields expected by StandardPaper
        # -----------------------------------------------------

        return StandardPaper(

            arxiv_id=paper_dict.get(
                "arxiv_id"
            ),

            title=paper_dict.get(
                "title",
                ""
            ),

            authors=paper_dict.get(
                "authors",
                []
            ),

            abstract=paper_dict.get(
                "abstract",
                ""
            ),

            year=paper_dict.get(
                "year"
            ),

            pdf_url=paper_dict.get(
                "pdf_url"
            ),

            source=paper_dict.get(
                "source",
                ""
            ),

            retrieved_at=paper_dict.get(
                "retrieved_at"
            ),

            raw_metadata=raw_metadata

        )


    # =========================================================
    # DOWNLOAD PDF
    # =========================================================

    def download_pdf(
        self,
        pdf_url: str,
        timeout: int = 30
    ) -> Optional[bytes]:
        """
        Download a PDF from a URL.

        Returns:
            PDF bytes if successful, otherwise None.
        """

        try:

            if not pdf_url:

                print(
                    "❌ No PDF URL provided."
                )

                return None


            print(
                f"📥 Downloading PDF: "
                f"{pdf_url[:100]}..."
            )


            headers = {
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/131.0 Safari/537.36"
                )
            }


            response = requests.get(
                pdf_url,
                headers=headers,
                timeout=timeout,
                verify=self.verify_ssl,
                allow_redirects=True
            )


            response.raise_for_status()


            content = response.content


            content_type = (
                response.headers
                .get(
                    "content-type",
                    ""
                )
                .lower()
            )


            # -------------------------------------------------
            # PDF signature
            # -------------------------------------------------

            is_pdf_signature = (
                content.startswith(
                    b"%PDF"
                )
            )


            is_pdf_content_type = (
                "application/pdf"
                in content_type
            )


            if not (
                is_pdf_signature
                or is_pdf_content_type
            ):

                print(
                    "❌ Downloaded content does not "
                    "appear to be a PDF."
                )

                print(
                    f"   Content-Type: {content_type}"
                )

                return None


            if not content:

                print(
                    "❌ Downloaded PDF is empty."
                )

                return None


            print(
                f"✓ PDF downloaded successfully "
                f"({len(content):,} bytes)"
            )


            return content


        except requests.exceptions.SSLError as error:

            print(
                "❌ SSL error while downloading PDF:"
            )

            print(
                str(error)
            )

            return None


        except requests.exceptions.Timeout as error:

            print(
                "❌ PDF download timed out:"
            )

            print(
                str(error)
            )

            return None


        except requests.exceptions.RequestException as error:

            print(
                "❌ PDF download failed:"
            )

            print(
                str(error)
            )

            return None


        except Exception as error:

            print(
                "❌ Unexpected PDF download error:"
            )

            print(
                str(error)
            )

            return None


    # =========================================================
    # EXTRACT TEXT FROM PDF
    # =========================================================

    def extract_text(
        self,
        pdf_bytes: bytes,
        max_pages: Optional[int] = None
    ) -> Optional[str]:
        """
        Extract text from PDF bytes.

        None means:
            use processor setting.

        If processor setting is also None:
            extract all pages.
        """

        if not pdf_bytes:

            print(
                "❌ No PDF bytes supplied."
            )

            return None


        if max_pages is None:

            max_pages = self.max_pages


        try:

            pdf_file = BytesIO(
                pdf_bytes
            )


            reader = PyPDF2.PdfReader(
                pdf_file
            )


            num_pages = len(
                reader.pages
            )


            # -------------------------------------------------
            # Determine pages to extract
            # -------------------------------------------------

            if max_pages is None:

                pages_to_extract = num_pages

            else:

                pages_to_extract = min(
                    max_pages,
                    num_pages
                )


            print(
                f"📖 PDF contains "
                f"{num_pages} pages."
            )


            print(
                f"📖 Extracting "
                f"{pages_to_extract} page(s)..."
            )


            extracted_pages = []


            # -------------------------------------------------
            # Extract each page
            # -------------------------------------------------

            for page_num in range(
                pages_to_extract
            ):

                try:

                    page = reader.pages[
                        page_num
                    ]


                    page_text = (
                        page.extract_text()
                    )


                    if page_text is None:

                        print(
                            f"  ⚠ Page "
                            f"{page_num + 1}: "
                            "No text extracted."
                        )

                        continue


                    page_text = (
                        page_text
                        .strip()
                    )


                    if not page_text:

                        print(
                            f"  ⚠ Page "
                            f"{page_num + 1}: "
                            "Empty text."
                        )

                        continue


                    extracted_pages.append(
                        (
                            f"\n"
                            f"--- Page "
                            f"{page_num + 1} ---\n"
                            f"{page_text}\n"
                        )
                    )


                    print(
                        f"  ✓ Page "
                        f"{page_num + 1}: "
                        f"{len(page_text):,} characters"
                    )


                except Exception as page_error:

                    print(
                        f"  ⚠ Page "
                        f"{page_num + 1} "
                        f"extraction failed: "
                        f"{page_error}"
                    )

                    continue


            # -------------------------------------------------
            # Combine pages
            # -------------------------------------------------

            extracted_text = (
                "\n".join(
                    extracted_pages
                )
                .strip()
            )


            if not extracted_text:

                print(
                    "❌ No text could be extracted "
                    "from this PDF."
                )

                print(
                    "   The PDF may be scanned/image-based."
                )

                return None


            print(
                f"✓ Extracted "
                f"{len(extracted_text):,} characters "
                f"from "
                f"{len(extracted_pages)} page(s)."
            )


            return extracted_text


        except Exception as error:

            print(
                "❌ PDF extraction failed:"
            )

            print(
                str(error)
            )

            return None


    # =========================================================
    # PROCESS ONE PAPER
    # =========================================================

    def process_paper(
        self,
        paper: StandardPaper,
        max_pages: Optional[int] = None
    ) -> StandardPaper:
        """
        Download and extract the PDF for one paper.

        Extracted text is stored in:
            paper.raw_metadata["raw_text"]

        Text length is stored in:
            paper.raw_metadata["text_length"]
        """

        if paper is None:

            print(
                "❌ Cannot process empty paper."
            )

            return paper


        # -----------------------------------------------------
        # Get PDF URL
        # -----------------------------------------------------

        try:

            pdf_url = paper.get_pdf_url()

        except Exception as error:

            print(
                "❌ Could not get PDF URL:"
            )

            print(
                str(error)
            )

            return paper


        if not pdf_url:

            print(
                f"⚠ No PDF URL for: "
                f"{getattr(paper, 'title', '')[:80]}"
            )

            return paper


        # -----------------------------------------------------
        # Processing header
        # -----------------------------------------------------

        title = getattr(
            paper,
            "title",
            "Untitled Paper"
        )


        source = getattr(
            paper,
            "source",
            "Unknown"
        )


        print()
        print(
            "=" * 70
        )


        print(
            f"PROCESSING PDF: "
            f"{title[:80]}"
        )


        print(
            f"Source: {source}"
        )


        print(
            "=" * 70
        )


        # -----------------------------------------------------
        # Download
        # -----------------------------------------------------

        pdf_bytes = self.download_pdf(
            pdf_url
        )


        if not pdf_bytes:

            print(
                "⚠ PDF download failed."
            )

            print(
                "   Existing paper data retained."
            )

            return paper


        # -----------------------------------------------------
        # Extract
        # -----------------------------------------------------

        text = self.extract_text(
            pdf_bytes,
            max_pages=max_pages
        )


        if not text:

            print(
                "⚠ PDF text extraction failed."
            )

            print(
                "   Existing paper data retained."
            )

            return paper


        # -----------------------------------------------------
        # Ensure raw metadata
        # -----------------------------------------------------

        if not isinstance(
            getattr(
                paper,
                "raw_metadata",
                None
            ),
            dict
        ):

            paper.raw_metadata = {}


        # -----------------------------------------------------
        # Store full text
        # -----------------------------------------------------

        paper.raw_metadata[
            "raw_text"
        ] = text


        paper.raw_metadata[
            "text_length"
        ] = len(
            text
        )


        paper.raw_metadata[
            "pdf_text_extracted"
        ] = True


        paper.raw_metadata[
            "pdf_pages_processed"
        ] = (
            max_pages
            if max_pages is not None
            else "all"
        )


        print(
            f"✓ Full paper text stored: "
            f"{len(text):,} characters"
        )


        return paper


    # =========================================================
    # PROCESS PAPERS FROM JSON
    # =========================================================

    def process_papers_from_json(
        self,
        input_file: str = "backend/data/papers.json",
        output_file: str = "backend/data/papers_with_text.json",
        max_pages: Optional[int] = None,
        skip_existing: bool = True
    ) -> List[StandardPaper]:
        """
        Process papers from papers.json.

        Important:
        The JSON file may contain fields that StandardPaper does
        not accept, such as application-level "id". These are
        handled by _standard_paper_from_dict().
        """

        if max_pages is None:

            max_pages = self.max_pages


        try:

            # -------------------------------------------------
            # Load JSON
            # -------------------------------------------------

            with open(
                input_file,
                "r",
                encoding="utf-8"
            ) as file:

                papers_data = json.load(
                    file
                )


            if not isinstance(
                papers_data,
                list
            ):

                print(
                    "❌ Expected papers.json "
                    "to contain a list."
                )

                return []


            print()
            print(
                f"📂 Loaded "
                f"{len(papers_data)} papers "
                f"from {input_file}"
            )


            processed_papers = []


            # -------------------------------------------------
            # Process each paper
            # -------------------------------------------------

            for index, paper_dict in enumerate(
                papers_data,
                start=1
            ):

                print()
                print(
                    f"[{index}/{len(papers_data)}]"
                )


                # -------------------------------------------------
                # Validate dictionary
                # -------------------------------------------------

                if not isinstance(
                    paper_dict,
                    dict
                ):

                    print(
                        "❌ Invalid paper record. "
                        "Expected object/dictionary."
                    )

                    continue


                # -------------------------------------------------
                # Convert to StandardPaper
                # -------------------------------------------------

                try:

                    paper = (
                        self._standard_paper_from_dict(
                            paper_dict
                        )
                    )

                except Exception as error:

                    print(
                        "❌ Could not create "
                        "StandardPaper:"
                    )

                    print(
                        str(error)
                    )

                    continue


                # -------------------------------------------------
                # Existing text
                # -------------------------------------------------

                raw_metadata = getattr(
                    paper,
                    "raw_metadata",
                    {}
                )


                if not isinstance(
                    raw_metadata,
                    dict
                ):

                    raw_metadata = {}


                existing_text = str(
                    raw_metadata.get(
                        "raw_text",
                        ""
                    )
                    or ""
                ).strip()


                if (
                    skip_existing
                    and existing_text
                ):

                    print(
                        "✓ Skipping "
                        "(full text already exists): "
                        f"{paper.title[:60]}"
                    )


                    processed_papers.append(
                        paper
                    )

                    continue


                # -------------------------------------------------
                # Process PDF
                # -------------------------------------------------

                updated_paper = self.process_paper(
                    paper,
                    max_pages=max_pages
                )


                processed_papers.append(
                    updated_paper
                )


            # -------------------------------------------------
            # Save output
            # -------------------------------------------------

            print()
            print(
                "=" * 70
            )


            print(
                f"💾 Saving processed papers "
                f"to {output_file}..."
            )


            print(
                "=" * 70
            )


            output_directory = os.path.dirname(
                output_file
            )


            if output_directory:

                os.makedirs(
                    output_directory,
                    exist_ok=True
                )


            papers_dict = []


            for paper in processed_papers:

                if hasattr(
                    paper,
                    "model_dump"
                ):

                    paper_data = (
                        paper.model_dump()
                    )

                elif hasattr(
                    paper,
                    "dict"
                ):

                    paper_data = (
                        paper.dict()
                    )

                else:

                    paper_data = dict(
                        getattr(
                            paper,
                            "__dict__",
                            {}
                        )
                    )


                papers_dict.append(
                    paper_data
                )


            with open(
                output_file,
                "w",
                encoding="utf-8"
            ) as file:

                json.dump(
                    papers_dict,
                    file,
                    indent=2,
                    ensure_ascii=False,
                    default=str
                )


            print(
                f"✓ Saved "
                f"{len(processed_papers)} "
                f"processed papers."
            )


            return processed_papers


        except FileNotFoundError:

            print(
                f"❌ File not found: "
                f"{input_file}"
            )

            return []


        except json.JSONDecodeError:

            print(
                f"❌ Invalid JSON in: "
                f"{input_file}"
            )

            return []


        except Exception as error:

            print(
                "❌ Error processing papers:"
            )

            print(
                str(error)
            )

            return []


# =============================================================
# DIRECT TEST
# =============================================================

if __name__ == "__main__":

    print()
    print(
        "=" * 70
    )

    print(
        "PDF PROCESSOR TEST"
    )

    print(
        "=" * 70
    )


    # ---------------------------------------------------------
    # Current development configuration
    #
    # SSL verification disabled because your machine/network
    # currently has certificate verification issues.
    #
    # max_pages=None means ALL pages.
    # ---------------------------------------------------------

    processor = PDFProcessor(
        verify_ssl=False,
        max_pages=None
    )


    papers = processor.process_papers_from_json(
        input_file="backend/data/papers.json",
        output_file="backend/data/papers_with_text.json",
        max_pages=None,
        skip_existing=True
    )


    print()
    print(
        "=" * 70
    )


    print(
        f"✓ Finished processing "
        f"{len(papers)} papers."
    )


    print(
        "=" * 70
    )