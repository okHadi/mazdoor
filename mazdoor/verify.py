"""PDF render-to-PNG verification (AGENTS.md: render and inspect for
clipping/overlap/overflow). Uses pypdfium2; numpy optional for blank check."""

from pathlib import Path


def render_pdf_png(pdf_path, out=None, scale=2):
    """Render the first page of a PDF to a PNG at `scale` (default 2x).

    Returns a PIL Image (pypdfium2's built-in bitmap wrapper or PIL image).
    """
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        page = pdf[0]
        bitmap = page.render(scale=scale)
        pil = bitmap.to_pil()
    finally:
        pdf.close()
    if out is not None:
        out = Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        pil.save(str(out))
    return pil


def verify_renders(artifacts_dir, out_dir=None, scale=2):
    """Render every PDF in artifacts_dir to PNG. Returns (rendered, failed)."""
    out_dir = Path(out_dir or (Path(artifacts_dir) / "preview"))
    rendered, failed = [], []
    for pdf in sorted(Path(artifacts_dir).glob("*.pdf")):
        try:
            render_pdf_png(pdf, out=out_dir / (pdf.stem + ".png"), scale=scale)
            rendered.append(pdf.name)
        except Exception as exc:  # noqa: BLE001
            failed.append((pdf.name, str(exc)))
    return rendered, failed
