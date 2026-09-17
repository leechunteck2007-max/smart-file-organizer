"""Discover shallow categories and concise names from files, never user profiles."""
from collections import Counter
from datetime import datetime
from pathlib import Path
import re
from app.core.models import ClassificationResult

DOCS = {'.pdf', '.doc', '.docx', '.txt', '.md', '.rtf', '.ppt', '.pptx', '.xlsx', '.xls', '.csv'}
PHOTOS = {'.png', '.jpg', '.jpeg', '.heic', '.webp', '.gif'}
COURSE = re.compile(r'\b([A-Z]{2,6}[ -]?\d{2,4})\b', re.I)


def safe_name(text: str) -> str:
    name = re.sub(r'[^\w -]', '', text, flags=re.UNICODE)
    name = re.sub(r'[\s_]+', '_', name).strip('_. ')[:85]
    if not name or name.upper() in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}:
        return 'File'
    return name


class FileUnderstanding:
    def __init__(self, records, texts, policy):
        self.policy = policy
        self.texts = texts
        codes = []
        for record in records:
            if record.protected:
                continue
            signals = record.filename+' '+str(Path(record.current_path).parent)+' '+texts.get(record.id, '')[:3000]
            codes.extend({re.sub(r'[ -]', '', m.upper()) for m in COURSE.findall(signals)})
        self.codes = {code for code, count in Counter(codes).items() if count >= 2}

    def analyze(self, record):
        veto = self.policy.veto(record.current_path)
        if veto:
            return ClassificationResult('Protected', '', 0, veto, 'FileUnderstanding'), record.filename
        content = self.texts.get(record.id, '')
        name = Path(record.filename).stem
        context = ' '.join(Path(record.current_path).parent.parts[-3:])
        text = (name+' '+context+' '+content[:6000]).replace('_', ' ')
        category, confidence, reason = 'Other', 30, 'No reliable file signal; leave unchanged until reviewed'
        kind = ''
        code = next((re.sub(r'[ -]', '', m.upper()) for m in COURSE.findall(text) if re.sub(r'[ -]', '', m.upper()) in self.codes), '')
        if record.extension in DOCS:
            signals = [(r'bank\s+statement', 'Finance/Bank Statements', 'Bank_Statement'),
                       (r'\binvoices?\b', 'Finance/Invoices', 'Invoice'),
                       (r'\breceipts?\b', 'Finance/Receipts', 'Receipt'),
                       (r'\b(?:lecture|lectures)\b', 'Education/Lectures', 'Lecture'),
                       (r'\b(?:assignment|assignments)\b', 'Education/Assignments', 'Assignment'),
                       (r'\b(?:tutorial|tutorials)\b', 'Education/Tutorials', 'Tutorial'),
                       (r'\b(?:lab|laboratory)\b', 'Education/Labs', 'Lab'),
                       (r'\b(?:exam|examination)\b', 'Education/Exams', 'Exam'),
                       (r'\b(?:research|abstract|doi)\b', 'Research', 'Research'),
                       (r'\b(?:isbn|textbook|chapter)\b', 'Books', 'Book'),
                       (r'\bmeeting\b', 'Work/Meetings', 'Meeting'),
                       (r'\breport\b', 'Work/Reports', 'Report')]
            for pattern, destination, label in signals:
                if re.search(pattern, text, re.I):
                    category, kind = destination, label
                    filename_signal = bool(re.search(pattern, name.replace('_',' '), re.I))
                    content_signal = bool(re.search(pattern, content, re.I))
                    confidence = 97 if code and category.startswith('Education') else 96 if filename_signal and content_signal else 90
                    origin = 'filename and document text' if filename_signal and content_signal else 'document text' if content_signal else 'filename or existing folder context'
                    reason = f'{label.replace("_", " ")} signal in {origin}'
                    if code and category.startswith('Education'):
                        category = 'Education/'+code+'/'+category.split('/')[-1]
                        reason += f'; repeated topic code {code} discovered across files'
                    break
            if category == 'Other':
                category = 'Presentations' if record.extension in {'.ppt','.pptx'} else 'Spreadsheets' if record.extension in {'.xlsx','.xls','.csv'} else 'Documents'
                confidence, reason = 82, 'Document format; no stronger subject signal found'
        elif record.extension in PHOTOS:
            if re.search(r'\bscreenshot\b|screen\s+shot', name.replace('_',' '), re.I):
                category, kind, confidence = 'Screenshots', 'Screenshot', 97
                reason = 'Screenshot filename and image format agree'
            else:
                category, confidence, reason = 'Photos', 82, 'Image format; image contents are not interpreted'
        elif record.extension in {'.mp4','.mov','.mkv','.avi'}:
            category, confidence, reason = 'Videos', 85, 'Video format'
        elif record.extension in {'.mp3','.wav','.flac','.m4a'}:
            category, confidence, reason = 'Media/Audio', 85, 'Audio format'
        elif record.extension in {'.exe','.msi','.iso'}:
            category, confidence, reason = 'Installers', 82, 'Installation-package format; never executed'
        elif record.extension in {'.zip','.rar','.7z','.tar','.gz'}:
            category, confidence, reason = 'Archives', 82, 'Archive format; archive contents are not extracted'
        proposed = record.filename
        if confidence >= 95 and kind:
            if category.startswith('Education'):
                number = re.search(r'(?:lecture|assignment|tutorial|lab|exam)\s*\(?\s*(\d{1,3})', name, re.I)
                if code and number:
                    proposed = safe_name(f'{code}_{kind}_{int(number.group(1)):02d}')+Path(record.filename).suffix
            elif kind == 'Screenshot':
                explicit = re.search(r'(20\d{2})[-_](\d{2})[-_](\d{2})', name)
                date = '-'.join(explicit.groups()) if explicit else datetime.fromtimestamp(record.created_at).strftime('%Y-%m-%d')
                proposed = safe_name(date+'_'+kind)+Path(record.filename).suffix
                if not explicit:
                    reason += '; rename date comes from filesystem creation metadata'
            elif kind in {'Invoice','Receipt','Bank_Statement'}:
                date = re.search(r'\b(20\d{2})[-/](0[1-9]|1[0-2])(?:[-/](?:0[1-9]|[12]\d|3[01]))?\b', name+' '+content)
                if date:
                    proposed = safe_name(date.group(1)+'-'+date.group(2)+'_'+kind)+Path(record.filename).suffix
                    reason += '; date explicitly present in filename or document text'
        parts = category.split('/')
        destination = str(Path(self.policy.settings['library']).joinpath(*parts, proposed)) if confidence >= 80 else ''
        return ClassificationResult(parts[0], '/'.join(parts[1:]), confidence, reason, 'FileUnderstanding', destination), proposed
