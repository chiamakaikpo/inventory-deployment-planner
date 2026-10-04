# Analysis: pain points, business rules and KPIs

Supporting analysis for the [Inventory Deployment Planner](../README.md). Based on my experience as a Country Inventory Deployment Planner (and previously Material Requirement Planner) at a global FMCG brewer. The organisation is anonymised and figures are left out; the planner workbook uses synthetic data.

## 1. Pain-point analysis

| # | Pain point (as-is step) | Root cause | Effect | Addressed by |
|---|---|---|---|---|
| 1 | **Consolidate:** stock and sales data merged manually in spreadsheets | No agreed data cut-off; several extracts at different times | Decisions made on snapshots that were already out of date by execution | To-be step 1 *Sync*: one SAP source, one agreed cut-off |
| 2 | **Allocate:** allocation based on judgement, no shared rules | Priorities varied by planner and by week | Outcomes hard to repeat or explain; shortages in some depots while others built excess | BR-01, BR-02 in the planner workbook |
| 3 | **Approve:** every SKU and depot reviewed with sales and logistics | No way to tell which rows needed attention | Review time spent confirming rows that were fine | BR-04 exception flag: review only out-of-band rows |
| 4 | **React:** firefighting shortages after the fact | Transfers decided when a depot was already short | Costly emergency transfers, lost sales | BR-03 transfer rule, applied before dispatch |
| 5 | Sales forecast and production plan not reconciled | Forecast and supply owned by different teams with no shared review | Supply short for some SKUs, surplus for others | S&OP-style alignment step (process change, not tool) |

> The key insight: the tooling problem was really an alignment problem. Rules had to be agreed by planning, sales and logistics *before* anything was automated.

## 2. Business rules

| ID | Rule | Where it is implemented |
|---|---|---|
| BR-01 | Each depot has a target days-of-cover band per SKU class (fast / medium / slow movers). | `Inputs` → cover bands; `Allocation` columns H, W, X |
| BR-02 | When supply is short, allocate in proportion to forecast demand, with a minimum floor for priority depots. | `Allocation` columns L–T and AE–AI |
| BR-03 | Suggest an inter-depot transfer only when projected excess at one depot covers a projected shortfall at another within the transfer lead time. | `Transfers` tab |
| BR-04 | A depot/SKU is flagged as an exception when projected cover falls outside its band. | `Allocation` column Y (Status) |

### How BR-02 is calculated

1. **Need** for each depot = target cover × forecast − (stock on hand + in transit), never below zero.
2. If total need ≤ supply, every depot gets its need.
3. If supply is short:
   - **Priority floor first.** Priority depots receive up to *floor days × forecast* (3 days by default), capped at their need. If floors alone exceed supply, they are scaled down.
   - **Fair share of the rest.** Each depot receives *min(remaining need, λ × forecast)*. The workbook solves for the λ that uses all remaining supply, so stock freed up by depots that hit their need is shared out again ("water-filling").
   - Allocations are rounded down to whole cases.

The `tests/test_planner.py` script re-implements these rules in Python and checks the workbook's results line by line.

## 3. KPIs

| KPI | Definition | Why it matters |
|---|---|---|
| Service level / fill rate by depot | Cases delivered to customers ÷ cases ordered | The outcome customers feel |
| Stock imbalance index | Standard deviation of days of cover across depots, per SKU | Low = stock is where demand is; high = shortages and excess at the same time |
| Reactive transfers | Number, cases and cost of inter-depot transfers not planned in the deployment cycle | Measures firefighting |
| Planner time on exceptions | Share of planner review time spent on exception rows vs routine checking | Measures whether the rules are trusted |
| Exceptions per cycle | Depot/SKU rows outside their cover band after deployment | Workload indicator for the review step |

## 4. Findings from the synthetic scenario

All numbers come from the `Summary` tab of `planner/Deployment_Planner.xlsx`.

- **Exceptions to review fall from 17 to 4 of 30 depot/SKU rows** (87% of rows need no review).
- **Imbalance index falls from 5.2 to 3.5 days** on average across the six SKUs.
- **Three SKUs are short of supply.** The rules allocate all available stock (unallocated stock on short SKUs is at most rounding).
- **One transfer is suggested:** 53 cases of Malt drink 33cl from Depot Coastal (24 days of cover, above its 18-day maximum) to Depot North (6.8 days, below its 7-day minimum). The transfer arrives in 2 days, well before North runs out.

### A finding to take back to stakeholders

Allocating **in proportion to forecast** (BR-02 as agreed) does not equalise cover. In the Malt drink example, Depot North starts with the lowest cover (4.2 days) but ends below its band, while Depot South-East, which started with 10.2 days, is topped up to target. A **fair-share-by-days-of-cover** rule would bring every depot to the same cover instead. I would present both options to planning, sales and logistics with this example, rather than change the rule myself, because the rule is theirs to agree.

### Other open questions

- Which depots are "priority", and should priority be by depot or by customer?
- Should the cover bands be set by class only, or adjusted for depots with longer replenishment lead times?
- What is the minimum transfer size worth a truck?
