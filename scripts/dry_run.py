import argparse, sys, time
from pathlib import Path
from collections import Counter, defaultdict
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config.settings import defaults
from app.safety.policy import SafetyPolicy
from app.scanner.scanner import scan
from app.classifier.rule_based import RuleBasedClassifier

def run(folders, output):
    settings=defaults();settings['folders']=[str(Path(p).absolute()) for p in folders]
    policy=SafetyPolicy(settings);start=time.perf_counter();records,errors=scan(settings['folders'],policy)
    classifier=RuleBasedClassifier(settings,policy);results=[(r,classifier.classify(r)) for r in records]
    sizes=Counter(r.size for r in records if not r.protected)
    counts=Counter(c.category for r,c in results)
    proposed=[(r,c) for r,c in results if not r.protected and c.confidence>=80]
    collisions=sum(Path(c.suggested_destination).exists() for r,c in proposed)
    projects={policy.project_root(r.current_path) for r in records if r.project_member}
    duration=time.perf_counter()-start
    lines=['# MVP Dry Run Report','', 'Version: 0.1.0-alpha',
        'Mode: READ ONLY. Metadata only; no moves, renames, deletion or content inspection.',
        'Scope: explicitly selected Downloads folder. Paths and filenames omitted from this shareable report.', '',
        f'Files scanned / classified: {len(records)}',
        f'High confidence (95–100): {sum(c.confidence>=95 for r,c in results)}',
        f'Medium confidence (80–94): {sum(80<=c.confidence<95 for r,c in results)}',
        f'Inbox confidence (50–79): {sum(50<=c.confidence<80 for r,c in results)}',
        f'Unclassified: {counts["Unclassified"]}',
        f'Protected files: {sum(r.protected for r in records)}',
        f'Detected projects: {len(projects)}',
        f'Duplicate size-candidate groups (NOT confirmed): {sum(n>1 for n in sizes.values())}',
        f'Proposed moves: {len(proposed)}',f'Existing destination name collisions: {collisions}',
        f'Project-member proposed moves: {sum(r.project_member for r,c in proposed)}',
        f'Protected proposed moves: {sum(r.protected for r,c in proposed)}',
        f'Elapsed seconds: {duration:.3f}', '', '## Categories', '',
        *[f'- {k}: {v}' for k,v in sorted(counts.items())], '', '## Errors and prevented actions', '',
        *[f'- {k}: {v}' for k,v in sorted(Counter(errors).items())], '',
        'Protected subtrees, application dependencies, projects, reparse points and incomplete downloads are excluded from move proposals.', '',
        '## Review', '',
        'No project-member or protected file can have an actionable move proposal. Extension-only classifications use 82 confidence and cannot auto-move at the default threshold. Filename heuristics are suggestions requiring human review; document meaning was not inspected.',
        'Dry-run evidence does not establish classification accuracy or authorize personal-file moves.',
        'Controlled personal-file test and second-computer runtime validation remain pending.']
    Path(output).write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(f'DRY RUN: {len(records)} files; {duration:.3f}s; {len(proposed)} proposals; {len(errors)} skipped/errors')
    assert not any(r.protected or r.project_member for r,c in proposed)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--folders',nargs='+',required=True);p.add_argument('--output',default='MVP_DRY_RUN_REPORT.md');a=p.parse_args();run(a.folders,a.output)
