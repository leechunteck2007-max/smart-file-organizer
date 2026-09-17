"""Computer discovery dry run. Never constructs or calls a moving operation."""
from pathlib import Path
import json,sys,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.smart.v2 import V2Service
def main():
 service=V2Service(ROOT/'build/real-v2-readonly-state');runs=[]
 try:
  for n in range(2):
   start=time.perf_counter();result=service.scan_computer(content=False)
   unsafe=sum(i['plan'].file.protected and bool(i['plan'].destination) for i in service.plans.values())
   retained=sum(i['plan'].file.current_path in service.already and bool(i['plan'].destination) for i in service.plans.values())
   outside=sum(bool(i['plan'].destination) and not any(__import__('app.safety.policy',fromlist=['under']).under(i['plan'].file.current_path,p) for p in service.settings['folders']) for i in service.plans.values())
   assert unsafe==retained==outside==0
   runs.append(dict(run=n+1,seconds=round(time.perf_counter()-start,3),**result['totals'],unsafe_proposals=unsafe,organized_folder_proposals=retained,outside_scope=outside))
  assert service.store.connection.execute('SELECT COUNT(*) FROM actions').fetchone()[0]==0
 finally:service.store.close()
 lines=['# Real computer scan validation','', 'Smart File Organizer MVP V2 0.2.0-alpha. READ ONLY.', 'Two repeated automatic storage-discovery scans used the production Safety Engine. No moves, renames, quarantine or deletions were performed.', 'Metadata and eligible duplicate-candidate bytes were read locally. Document content extraction was disabled for this validation. Filenames, personal paths and text are omitted.', '', '| Measure | Run 1 | Run 2 |','|---|---:|---:|']
 for key in ['scanned','analyzed','ready','already_organized','protected','protected_trees','projects','cleanup_candidates','cleanup_size','unchanged','unsafe_proposals','organized_folder_proposals','outside_scope','seconds']:
  lines.append(f'| {key.replace("_"," ")} | {runs[0][key]} | {runs[1][key]} |')
 lines+=['','## Findings','', 'No protected files, preserved human folders or files outside discovered user-data scope received move proposals. Unknown formats remained unchanged. Protected tree counts do not claim to count contents of skipped trees. Exact duplicates use candidate-only SHA-256; old personal files are never quarantined solely because of age.', 'The repeated scans exercise safety invariants and metadata classification, not semantic ground truth. Content-based rename quality is covered by synthetic PDF tests. Cloud placeholders/reparse trees, network shares and unknown system-drive roots are conservatively excluded.', '', '## Acceptance status','', 'Synthetic full organization and Undo are tested separately. The first reorganization of personal originals still requires explicit confirmation. Independent Windows PC and physical external-drive testing remain pending. This is a private alpha, not a public-release certification.']
 (ROOT/'REAL_SCAN_VALIDATION_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8');(ROOT/'docs/v2-real-scan-counts.json').write_text(json.dumps(runs,indent=2),encoding='utf-8');print(json.dumps(runs))
if __name__=='__main__':main()
