"""Bounded, read-only extraction. PDFs are parsed in timeout-limited workers."""
import json
from pathlib import Path
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET

SUPPORTED = {'.pdf', '.docx', '.pptx', '.xlsx', '.txt', '.md'}
MAX_FILE = 10 * 1024 * 1024
MAX_XML = 2 * 1024 * 1024


def extract_local(path: str) -> str:
    p = Path(path)
    if p.stat().st_size > MAX_FILE:
        raise ValueError('Document exceeds lightweight inspection limit')
    suffix = p.suffix.lower()
    if suffix in {'.txt', '.md'}:
        with p.open('rb') as file:
            return file.read(65536).decode('utf-8', errors='replace')[:20000]
    if suffix == '.pdf':
        from pypdf import PdfReader
        reader = PdfReader(p, strict=False)
        if reader.is_encrypted:
            raise ValueError('Encrypted PDF skipped')
        return '\n'.join((reader.pages[i].extract_text() or '')[:10000] for i in range(min(2, len(reader.pages))))[:20000]
    with zipfile.ZipFile(p) as archive:
        if suffix == '.docx':
            names = ['word/document.xml']
        elif suffix == '.pptx':
            names = sorted(n for n in archive.namelist() if n.startswith('ppt/slides/slide') and n.endswith('.xml'))[:3]
        elif suffix == '.xlsx':
            names = ['xl/sharedStrings.xml'] + sorted(n for n in archive.namelist() if n.startswith('xl/worksheets/sheet') and n.endswith('.xml'))[:2]
        else:
            return ''
        text = []
        budget = MAX_XML
        for name in names:
            if name not in archive.namelist():
                continue
            info = archive.getinfo(name)
            if info.file_size > budget:
                raise ValueError('Expanded XML exceeds inspection limit')
            budget -= info.file_size
            with archive.open(name) as member:
                data = member.read(info.file_size + 1)
            if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
                raise ValueError('XML entities are not supported')
            root = ET.fromstring(data)
            text.extend(element.text or '' for element in root.iter() if element.tag.rsplit('}', 1)[-1] in {'t', 'v'})
        return ' '.join(text)[:20000]


def inspect_document(path: str) -> tuple[str, str]:
    p = Path(path)
    if p.suffix.lower() not in SUPPORTED:
        return '', ''
    if p.stat().st_size > MAX_FILE:
        return '', 'ContentSkippedLarge'
    command = [sys.executable, '--extract', str(p)] if getattr(sys, 'frozen', False) else [sys.executable, str(Path(__file__).resolve().parents[2] / 'smart_engine.py'), '--extract', str(p)]
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=5, creationflags=flags)
        payload = json.loads(result.stdout)
        return payload.get('text', ''), payload.get('error', '')
    except subprocess.TimeoutExpired:
        return '', 'ContentInspectionTimeout'
    except (OSError, ValueError):
        return '', 'ContentInspectionFailed'
