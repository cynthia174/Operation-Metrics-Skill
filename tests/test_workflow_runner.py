import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from workflow_runner import run

def _plan(tmp, fail_once=False):
    code = "from pathlib import Path; p=Path(r'{root}/marker'); p.write_text('ok')"
    retry_code = code
    if fail_once:
        retry_code = "from pathlib import Path\np=Path(r'{root}/attempt')\nif p.exists():\n    Path(r'{root}/marker').write_text('ok')\nelse:\n    p.write_text('failed once')\n    raise SystemExit(3)"
    stages=[]
    previous=[]
    for sid in ["metrics", "rule_result", "report_md", "docx", "fact_qa", "structure_qa", "docx_qa", "ooxml_qa"]:
        stage_code = retry_code if fail_once and sid == "rule_result" else code
        stages.append({"id":sid,"dependencies":previous[:],"executor":[sys.executable,"-c",stage_code],"outputs":["marker"],"validator":"files_exist","retry_policy":{"max_attempts":2 if fail_once and sid=="rule_result" else 1}})
        previous=[sid]
    plan={"stages":stages,"definition_of_done":{"required_stages":[s["id"] for s in stages]}}
    pp=tmp/"plan.json"; pp.write_text(json.dumps(plan)); return pp

def test_runner_cases_continue_and_recovery(tmp_path):
    # Covers metrics/rule/report/docx->QA continuation and a recoverable retry.
    plan=_plan(tmp_path, True); state=tmp_path/"state.json"
    result=run(plan,state,tmp_path)
    assert result["status"] == "DONE"
    saved=json.loads(state.read_text())
    assert saved["stages"]["rule_result"]["attempts"] == 2
    assert [x["stage"] for x in saved["history"]] == [s["id"] for s in json.loads(plan.read_text())["stages"]]

def test_resume_skips_done_stage(tmp_path):
    plan=_plan(tmp_path); state=tmp_path/"state.json"
    run(plan,state,tmp_path)
    before=json.loads(state.read_text())["stages"]["metrics"]["attempts"]
    run(plan,state,tmp_path)
    assert json.loads(state.read_text())["stages"]["metrics"]["attempts"] == before
