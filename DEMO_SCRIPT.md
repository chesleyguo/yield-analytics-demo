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
> "Step one is finding the problem. If I break yield down by line, Line 2 falls away in weeks 3 and 4. In week 4 it's 18 points behind the other lines. By station, only Display Attach differs between lines. So the problem is local, not systemic."

**0:40 – SPC (20 s)** · click **SPC** (it opens on cure temp, Line 2)
> "That points to the adhesive-cure process. This X-bar chart uses week-1 control limits. The Line 2 oven starts drifting hot in week 2, and every red dot is a Western Electric rule violation. An SPC alarm would have caught this weeks before it showed up in yield. After the fix, Cpk goes from 0.08 to 1.49."

**1:00 – AI Insights (35 s)** · click **AI Insights**, then the **Root-cause hints** tab
> "I don't want engineers hunting through pivot tables, so the tool does the first pass. Anomaly detection compares each line, shift and lot with its peers built in the same week. It flags three clusters: one keyboard lot, the night shift and Line 2. The root-cause hints turn that into sentences an engineer can act on. For example: key-stick failures are 28 times more likely on lot KB-B-3104, and display delamination is about 14 times more likely when cure temp is above 84 °C on Line 2."
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

* **"Is this real AI?"** — "It's deliberately simple and explainable: p-charts, decision trees and stratified risk ratios. In a factory, being able to say *why* a factor was flagged matters more than model complexity. An LLM layer could sit on top for Q&A. It's built so it works without one."
* **"How do you avoid false leads?"** — "Every comparison is made against units built in the same week, so the learning curve isn't blamed on whichever lot happened to be early. Display-panel lots are a built-in negative control, and they don't get flagged."
* **"What would it take to make this real?"** — "MES genealogy linked to test logs and process data, a data-sharing agreement with the CM, and a pilot line where we check the alarms against manual failure analysis before scaling."
* **Live Q&A trick:** on AI Insights → *Ask the data*, type *"Which line has the lowest yield in week 4?"*
