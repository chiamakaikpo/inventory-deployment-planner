"""Build the as-is and to-be deployment process maps (.bpmn + .svg)."""
from pathlib import Path
from bpmn_builder import Process

OUT = Path(__file__).resolve().parents[1] / "process"

asis = Process("Deploy_AsIs", "Inventory deployment (as-is)", ["Deployment planner", "Sales", "Logistics"])
(asis
 .node("s", "start", "Weekly deployment cycle", "Deployment planner", 0)
 .node("a1", "task", "Extract stock and sales data from SAP", "Deployment planner", 1)
 .node("a2", "task", "Merge data manually in spreadsheets", "Deployment planner", 2, issue=True)
 .node("a3", "task", "Allocate by judgement, no shared rules", "Deployment planner", 3, issue=True)
 .node("a4", "task", "Review every SKU and depot with planner", "Sales", 4)
 .node("a5", "task", "Dispatch from breweries to depots", "Logistics", 5)
 .node("g1", "xor", "Depot short?", "Logistics", 6)
 .node("a6", "task", "Firefight: emergency transfer after the fact", "Logistics", 7, issue=True)
 .node("e", "end", "Cycle closed", "Deployment planner", 8)
 .flow("s", "a1").flow("a1", "a2").flow("a2", "a3").flow("a3", "a4").flow("a4", "a5").flow("a5", "g1")
 .flow("g1", "a6", "Yes").flow("g1", "e", "No").flow("a6", "e"))

tobe = Process("Deploy_ToBe", "Inventory deployment (to-be)", ["Planning workbook", "Deployment planner", "Sales & logistics"])
(tobe
 .node("s", "start", "Weekly deployment cycle", "Deployment planner", 0)
 .node("t1", "task", "Sync: agreed data cut-off, single SAP source", "Planning workbook", 1)
 .node("t2", "task", "Rule-based draft allocation (BR-01, BR-02)", "Planning workbook", 2)
 .node("g1", "xor", "Exceptions or transfers? (BR-03, BR-04)", "Planning workbook", 3)
 .node("t3", "task", "Review exceptions only", "Deployment planner", 4)
 .node("t4", "task", "Align in short S&OP-style huddle", "Sales & logistics", 5)
 .node("t5", "task", "Dispatch and planned transfers", "Sales & logistics", 6)
 .node("t6", "task", "Monitor cover, imbalance and service", "Deployment planner", 7)
 .node("e", "end", "Cycle closed", "Deployment planner", 8)
 .flow("s", "t1").flow("t1", "t2").flow("t2", "g1")
 .flow("g1", "t3", "Yes").flow("g1", "t4", "No").flow("t3", "t4")
 .flow("t4", "t5").flow("t5", "t6").flow("t6", "e"))

for p, stem, title, sub in [
    (asis, "as_is", "Inventory deployment · as-is", "Red tasks are pain points: manual consolidation, judgement-based allocation, reactive firefighting."),
    (tobe, "to_be", "Inventory deployment · to-be", "Rules produce the draft; planners review exceptions only; sales and logistics align once."),
]:
    (OUT / f"{stem}.bpmn").write_text(p.to_bpmn())
    (OUT / f"{stem}.svg").write_text(p.to_svg(title, sub))
    print("wrote", stem)
