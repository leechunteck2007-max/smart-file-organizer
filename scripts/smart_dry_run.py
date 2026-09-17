"""Read-only real-folder analysis; never calls the operation engine."""
import argparse
from collections import Counter
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.safety.policy import SafetyPolicy
from app.scanner.scanner import scan
from app.smart.inspect import inspect_document
from app.smart.understand import FileUnderstanding
from app.smart.cleanup import cleanup_candidates


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--folders',nargs='+',required=True);parser.add_argument('--output',default='SMART_DRY_RUN_REPORT.md');args=parser.parse_args()
    settings=dict(folders=[str(Path(p).absolute()) for p in args.folders],library=str(Path.home()/'File Library'),protected=[],ignored=[])
    for folder in settings['folders']:
        if Path(folder).parent==Path(folder):raise ValueError('Whole-drive scans disabled')
    policy=SafetyPolicy(settings);start=time.perf_counter();records,errors=scan(settings['folders'],policy)
    texts={}
    for record in records:
        if not record.protected:
            text,error=inspect_document(record.current_path);texts[record.id]=text
            if error:errors.append(error)
    understanding=FileUnderstanding(records,texts,policy)
    proposals=[(r,*understanding.analyze(r)) for r in records]
    actionable=[(r,c,n) for r,c,n in proposals if c.suggested_destination and not r.protected]
    cleanup,groups,duplicate_errors=cleanup_candidates(records);errors+=duplicate_errors
    assert not any(r.project_member or r.protected for r,c,n in actionable)
    lines=['# Smart File Organizer dry run','', 'Version: 0.2.0-alpha. Mode: READ ONLY.',
        'Scope: selected Downloads folder. No moves, renames, deletions or document modifications.',
        'Supported small documents were inspected locally; only aggregate counts are included here. Filenames, paths and document text are omitted.', '',
        f'Files scanned: {len(records)}',f'Proposed organizations: {len(actionable)}',
        f'High-confidence rename proposals: {sum(n!=r.filename for r,c,n in actionable)}',
        f'Protected files: {sum(r.protected for r in records)}',
        f'Uncertain files: {sum(c.confidence<80 and not r.protected for r,c,n in proposals)}',
        f'Confirmed duplicate groups: {len(groups)}',f'Cleanup candidates: {len(cleanup)}',
        f'Potential cleanup bytes: {sum(c["size"] for c in cleanup)}',
        f'Protected/project move proposals: {sum(r.protected or r.project_member for r,c,n in actionable)}',
        f'Elapsed seconds: {time.perf_counter()-start:.3f}', '', '## Categories', '',
        *[f'- {category}: {count}' for category,count in sorted(Counter(c.category for r,c,n in proposals).items())],
        '', '## Errors and skips', '', *[f'- {code}: {count}' for code,count in sorted(Counter(errors).items())], '',
        'Review conclusion: no protected/project file has an actionable proposal. Renames require at least 95 confidence; ordinary images are not assumed to be screenshots. Age alone never flags personal documents or photos for cleanup. Suggestions remain heuristic and require human approval.',
        'No personal-file controlled test or independent second-PC test was performed.']
    (ROOT/args.output).write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(f'DRY RUN: {len(records)} scanned, {len(actionable)} proposals, {len(cleanup)} cleanup candidates, no operations')


if __name__=='__main__':main()
