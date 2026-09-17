"""Check the frozen parser and Electron UI without development tools on PATH."""
import json
import os
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.generate_smart_synthetic import pdf


def main():
    package=ROOT/'dist/SmartFileOrganizer';state=ROOT/'build/smart-package-check';state.mkdir(parents=True,exist_ok=True)
    environment=dict(os.environ);environment['PATH']=str(Path(os.environ['WINDIR'])/'System32')
    for key in ['PYTHONHOME','PYTHONPATH','SMART_PYTHON','SMART_ENGINE_SCRIPT','SMART_QA_PYTHON','ELECTRON_RUN_AS_NODE','NODE_OPTIONS']:environment.pop(key,None)
    engine=package/'resources/engine/SmartFileEngine.exe'
    smoke=subprocess.run([str(engine),'--smoke-test','--state-dir',str(state)],capture_output=True,text=True,encoding='utf-8',env=environment,timeout=20)
    assert smoke.returncode==0 and json.loads(smoke.stdout)['ok'] and json.loads(smoke.stdout)['report_created']
    fixture=state/'synthetic-parser.pdf';pdf(fixture,'Invoice Date 2026-09-17 Invoice Total 100')
    parsed=subprocess.run([str(engine),'--extract',str(fixture)],capture_output=True,text=True,encoding='utf-8',env=environment,timeout=10)
    payload=json.loads(parsed.stdout);assert not payload['error'] and 'Invoice' in payload['text']
    startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
    gui=subprocess.run([str(package/'SmartFileOrganizer.exe'),'--self-test',f'--state-dir={state}'],env=environment,startupinfo=startup,timeout=30)
    assert gui.returncode==0
    ui=json.loads((state/'desktop-test.json').read_text(encoding='utf-8'))
    assert ui['bridge']=='function' and not ui['errors']
    report=dict(passed=True,engine_exit=smoke.returncode,parser_exit=parsed.returncode,desktop_exit=gui.returncode,
                bundled_pdf_parser=True,bundled_docx_generation=True,bridge=True,renderer_errors=ui['errors'],python_node_on_path=False,
                independent_computer_tested=False)
    (ROOT/'docs/smart-package-test.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))


if __name__=='__main__':main()
