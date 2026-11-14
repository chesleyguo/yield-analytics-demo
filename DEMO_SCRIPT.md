# Demo script: Product X Yield Analytics

**Before you share your screen**
* Run `streamlit run app.py` and open it in a browser window at 1440 px or wider. Zoom out to 90% if the window is narrow.
* Leave it on **Overview** with Week 12 selected. Hide the sidebar collapse arrow and the browser bookmarks bar.
* Say the disclaimer once at the start: *"Everything here is simulated data I generated. It's a generic laptop, not any real product or process."*

---

## 2-minute version (about 280 words of talk)

**0:00 – Overview (20 s)**
> "Here's the scenario. A new contract manufacturer is ramping a laptop, Product X, through final assembly and test. Week 1 final yield was 39%. By week 12 it's 91%. The useful part is *how*. Each of these three dotted lines is a fix, and each one lines up with a step change in yield. Underneath, you can see which station the loss came from each week."

**0:20 – Drill-down (20 s)** · click **Drill-down**, choose **Line**
> "Step one is finding the problem. If I break yield down by line, Line 2 falls away in weeks 3 and 4. In week 4 it's almost 19 points behind the best line. By station, only Display Attach differs between lines. So the problem is local, not systemic."

**0:40 – SPC (20 s)** · click **SPC** (it opens on cure temp, Line 2)
> "That points to the adhesive-cure process. This X-bar chart uses week-1 control limits. The Line 2 oven starts drifting hot in week 2, and every red dot is a Western Electric rule violation. An SPC alarm would have caught this weeks before it showed up in yield. After the fix, Cpk goes from 0.08 to 1.49."

**1:00 – AI Insights (35 s)** · click **AI Insights** (it opens on **Anomaly detection**)
> "I don't want engineers hunting through pivot tables, so the tool does the first pass. Anomaly detection compares each line, shift and lot with its peers built in the same week. The top three cards are one keyboard lot, the night shift and Line 2. Each card comes with a suggested action, an owner and a deadline: SQE quarantines the lot within 24 hours, the process engineer audits the Line 2 oven, and the line supervisor retrains night shift within a week."
> · click the **Root-cause hints** tab
> "The root-cause hints turn the data into sentences an engineer can act on. For example: key-stick failures are about 26 times more likely on lot KB-B-3104, and display delamination is about 23 times more likely when cure temp is above 84 °C on Line 2."
> · click the **DOE** tab
> "To choose the new recipe we ran a small factorial DOE. Lower temperature with a longer cure is the robust setting, and that's the week-5 fix."

**1:35 – Pareto (10 s)** · click **Defect Pareto**, choose **Before vs after fixes**
> "To validate the fix: the targeted defect codes have dropped off the top of the Pareto, and total failures are down by about 80%."

**1:45 – Program view (15 s)** · click **Program view**
> "As a TPM, I'd treat this as a program, not a dashboard. The users are process engineers, SQE and supplier management. The data comes from MES and test logs. The rollout goes pilot line, then all lines, then new suppliers, with an exit gate at each step. Success is measured in days to root cause and weeks to yield target. The main risk is acting on correlation, so the hints trigger a DOE or failure analysis and never an automatic action."

---

## 30-second version

> "This is a simulated yield ramp for a generic laptop at a new contract manufacturer. Yield goes from 39% to 91% in 12 weeks." *(Overview: point at the three fix lines.)*
> "The tool flags anomalies automatically against same-week peers. It then ranks likely root causes in plain English: a bad keyboard lot, a cure oven drifting hot on Line 2, and a night-shift handling gap." *(AI Insights → Root-cause hints.)*
> "SPC confirms the oven drift weeks before it hit yield, and Cpk after the fix shows the gain is holding." *(SPC.)*
> "As a program, I'd measure it by time to root cause and ramp speed, rolling out from a pilot line to all lines and then to new suppliers." *(Program view.)*

---

## Likely follow-up questions

* **"Is this real AI?"** — "It's deliberately simple and explainable: two-proportion tests against same-week peers, decision trees and stratified risk ratios. In a factory, being able to say *why* a factor was flagged matters more than model complexity. An LLM layer could sit on top for Q&A. It's built so it works without one."
* **"How do you avoid false leads?"** — "Every comparison is made against units built in the same week, so the learning curve isn't blamed on whichever lot happened to be early. Display-panel lots are a built-in negative control, and they don't get flagged."
* **"What would it take to make this real?"** — "MES genealogy linked to test logs and process data, a data-sharing agreement with the CM, and a pilot line where we check the alarms against manual failure analysis before scaling."
* **Live Q&A trick:** on AI Insights → *Ask the data*, type *"Which line has the lowest yield in week 4?"*
* **"Why is RTY lower than FPY?"** — "RTY multiplies the six station first-pass yields as if failures were independent. In reality defects cluster on the same marginal units, so the share of units that sail through every station first time, which is FPY, comes out slightly higher. Each KPI card shows its definition, and the code checks these relationships every week."
