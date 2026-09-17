import fnmatch, re
from pathlib import Path
from app.core.models import ClassificationResult

EXTENSIONS = {'Documents': '.pdf .doc .docx .txt .md .rtf .odt',
              'Work/Spreadsheets': '.xlsx .xls .csv .ods',
              'Work/Presentations': '.ppt .pptx .odp', 'Photos': '.jpg .jpeg .png .heic .webp .gif',
              'Videos': '.mp4 .mov .mkv .avi', 'Media/Audio': '.mp3 .wav .flac .m4a',
              'Archives': '.zip .rar .7z .tar .gz', 'Installers': '.exe .msi .iso'}

class RuleBasedClassifier:
    def __init__(self, settings, policy): self.settings, self.policy = settings, policy
    def classify(self, record):
        reason = self.policy.veto(record.current_path)
        if reason: return ClassificationResult('Projects' if record.project_member else 'Protected', '', 0, reason)
        name = record.filename.lower()
        for rule in self.settings['rules']:
            if fnmatch.fnmatch(name, rule['pattern'].lower()):
                return self.result(rule['category'], rule['confidence'], 'User rule: '+rule['pattern'], record)
        profile = self.settings['profile']
        signals = [('screenshot', 'Screenshots', 97), ('invoice', 'Finance/Invoices', 92),
                   ('receipt', 'Finance/Receipts', 92), ('budget', 'Finance/Budgets', 90),
                   ('meeting', 'Work/Meetings', 90), ('report', 'Work/Reports', 85)]
        if profile == 'Student':
            signals += [(k, 'Education/'+v, 92) for k,v in [('assignment','Assignments'),('lecture','Lectures'),('notes','Notes'),('lab','Labs'),('exam','Exams')]]
        if profile == 'Teacher':
            signals += [(k, 'Teaching/'+v, 94) for k,v in [('lesson','Lesson_Plans'),('exam','Exams'),('physics','Physics/Materials'),('student','Student_Work')]]
        for keyword, category, confidence in signals:
            if keyword == 'screenshot' and record.extension not in EXTENSIONS['Photos'].split():
                continue
            if keyword != 'screenshot' and record.extension not in (EXTENSIONS['Documents']+' '+EXTENSIONS['Work/Spreadsheets']+' '+EXTENSIONS['Work/Presentations']).split():
                continue
            if re.search(r'(?<![a-z])'+keyword+r'(?![a-z])', name):
                return self.result(category, confidence, f'Filename keyword "{keyword}"; {profile} profile', record)
        for category, extensions in EXTENSIONS.items():
            if record.extension in extensions.split():
                return self.result(category, 82, 'Extension '+record.extension+'; content not inspected', record)
        return self.result('Unclassified', 20, 'No reliable filename or extension signal', record)
    def result(self, category, confidence, reason, record):
        if confidence < 50:
            category = 'Unclassified'
        elif confidence < self.settings['review_threshold']:
            reason = 'Low-confidence proposal for '+category+'. '+reason
            category = 'Inbox'
        parts = category.split('/')
        destination = str(Path(self.settings['library']).joinpath(*parts, record.filename))
        return ClassificationResult(parts[0], '/'.join(parts[1:]), confidence, reason,
                                    suggested_destination=destination)
