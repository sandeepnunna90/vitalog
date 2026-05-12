# Custom Capstone — Vitalog

**Your health data is scattered. Your care doesn't have to be.**

*100xEngineers · Applied AI Capstone Series*

---

## Part I: The Fragmented Patient

Healthcare in the United States is organized around a fundamental assumption: that the doctor you are seeing today has access to the complete picture of your health. That assumption is wrong for the majority of Americans.

There are over 4 billion laboratory tests performed in the United States every year, at an estimated cost of $65 billion. Of those, redundant testing alone — tests repeated because the ordering physician did not know a recent result already existed — wastes an estimated $5 billion annually. The lack of interoperability between healthcare systems costs the industry an additional $30 billion in avoidable inefficiencies per year. A large-scale study of 232 million patients found that nearly 1 in 4 tested individuals had undergone excessive laboratory testing — tests repeated not because they were medically necessary, but because no one in the system had visibility into what had already been done. [1][2][3]

The crisis is not a shortage of data. It is a crisis of fragmentation.

In 2024, more than 59% of Americans had multiple online medical records or patient portals with different organizations. They had records at their primary care provider (68%), other health providers (40%), their insurer (30%), a clinical laboratory (29%), a pharmacy (24%), or a hospital (22%). These systems do not talk to each other. They were not designed to. Each was built to serve the institution, not the patient. [4]

The result is a healthcare system where every doctor you see knows a piece of your story — but no one, including you, knows the whole thing.

### The chronic condition at the center

More than 129 million Americans live with at least one major chronic disease — heart disease, cancer, diabetes, obesity, hypertension. Nearly 42% of adults have two or more. Approximately 12% manage five or more simultaneously. People with five or more chronic conditions average more than twelve physician visits per year. Each visit is another data point scattered into a separate system, another lab result filed in a different portal, another specialist who starts from scratch. [5][6]

Six in ten young adults, eight in ten midlife adults, and nine in ten older adults now report at least one chronic condition. Chronic disease is not an edge case. It is the normal state of American healthcare. And the system designed to manage it was built for acute care — single encounters, single providers, single episodes. It was not built for a person who has been accumulating health data across a dozen providers for four years and needs someone to see the whole thing at once. [7]

The $4.1 trillion US healthcare system spends an estimated 90% of its annual expenditures on managing and treating chronic diseases and mental health conditions. The cost of fragmentation — the redundant tests, the missed trends, the uninformed clinical decisions — is baked into that number. It just does not appear as a line item anyone is accountable for. [8]

---

## Part II: Meet Mark

Mark Sullivan is 56 years old. He works as a project manager at a technology firm in New Jersey and lives with his wife and two adult children. Four years ago he was diagnosed with Type 2 Diabetes. Two years ago, hypertension was added. Last year, his primary care physician noted that his thyroid levels were "borderline" and "something to watch." He sees a primary care physician and an endocrinologist. Following a brief hospitalization for chest pain last year — which turned out to be acid reflux — he was referred to a cardiologist for the first time. Each specialist ordered initial bloodwork. Each used a different lab.

His HbA1c — the primary marker for diabetes management — has been measured nine times across four years. Three of those results are in his endocrinologist's portal (LabCorp). Three are in his primary care physician's system (Quest Diagnostics). Two were drawn at a hospital lab during that admission. The ninth was ordered by his new cardiologist who wanted a "fresh baseline" and did not know any of the previous eight existed.

His total cholesterol has been tested six times by three different doctors. Three of those results overlap in timing and are effectively duplicates. His new cardiologist, seeing him for the first time last March, ordered a full lipid panel. The exact same panel had been ordered by his primary care physician eleven weeks earlier. Mark did not know how to tell the cardiologist. The cardiologist did not know to ask.

**Mark has a folder.**

It is a manila folder, slightly bent at one corner, with a rubber band around it. Inside are printouts from every lab report he has received in the last three years — whatever he could download from portals, whatever was mailed to him, whatever the receptionist printed at the front desk. He brings it to every appointment. Every new doctor picks it up, flips through it without context, and puts it back on the table. No one reads all of it. No one has time. No one can make sense of it without knowing which tests were duplicates, which numbers are trends, which results have already been incorporated into a prior treatment plan.

Mark is not someone who struggles with technology. As a project manager, he works with data tools daily and is comfortable navigating software. That is what makes the next part so telling.

Before a recent appointment with his new cardiologist, Mark spent ninety minutes trying to compile his health history. He logged into four different patient portals. One had not been updated since 2021. One sent a password reset to an email address he no longer used. One displayed only "Lab Result Received" with no values shown. He gave up and brought the folder.

Mark is not unusual. He is a composite of the 129 million Americans living with at least one major chronic disease — a number that includes 42% of adults with two or more conditions, and 12% managing five or more simultaneously. [5][6]

Mark's problem is not that he lacks health data. He has more than he can process. His problem is that the data has no memory, no narrative, and no intelligence. Every doctor he sees starts from scratch. Every new appointment is an interrogation of his own history. Every new specialist is a stranger to the story that has been accumulating for four years — a story that only Mark carries, imperfectly, in a manila folder with a rubber band.

---

## What Exists Today

Mark's current options:

**Option A: Hospital and provider patient portals.**
Most hospitals and large health systems now offer patient portals — MyChart, HealtheLife, Athena, and others. In theory, these give patients access to their test results. In practice, they give patients access to results within a single health system. Mark has a MyChart account for his primary care network, a Quest Diagnostics portal for standalone labs, and a separate portal for his cardiologist's practice. Each requires a different login. None share data. When his endocrinologist migrated to a new EHR in 2023, her portal's history before that date became inaccessible. Portals were designed to serve providers, not patients. The patient is downstream of the institution. [9]

**Option B: Apple Health and FHIR-connected apps.**
Apple Health, Google Health, and similar apps can connect to some EHR systems via FHIR standards and pull limited structured data. The coverage is incomplete — not every lab, hospital, or specialist supports FHIR API connections. But more critically, these apps aggregate raw data without intelligence. Mark can see that his most recent HbA1c was 6.9 in January, but the app cannot tell him that three months earlier it was 7.2, that the trend over 24 months is downward, that this represents meaningful improvement, or that his new cardiologist is working from a baseline that does not account for any of it. The data lands. The meaning does not. [10]

**Option C: Paper records and the manila folder.**
Mark's current system. He downloads PDFs, prints whatever he can, files everything in a folder he can barely parse himself. The folder is not searchable. It has no trends. It cannot tell him whether his February cholesterol result was materially different from August. It cannot generate a one-page health summary for a new specialist. It can be lost, forgotten, or left in the car. One patient described during treatment for colorectal cancer how he was subjected to repeated blood draws "because the doctors couldn't get their hands on earlier results." The folder did not prevent this. The folder never does. [11]

**Option D: Ask each doctor to share records with each other.**
Mark has tried. His primary care physician can fax records "upon request." His endocrinologist sends summaries at the end of each calendar year. His cardiologist can view records only "if the other providers use the same EHR system" — which they do not. Medical record sharing between institutions is slow, manual, incomplete, and provider-initiated, not patient-initiated. Repeated tests or treatment delays due to missing records add an average of $1,100 to a patient's cost of care per occurrence. [12]

**Option E: Health data aggregation services.**
A handful of companies — OneRecord, Fasten Health, Metriport — are building platforms that aggregate health records from multiple providers using FHIR APIs. These are genuine technical solutions to part of the problem. But they still face significant gaps: not every provider is FHIR-connected, the aggregated data is raw and uninterpreted, and none currently offer an intelligence layer that can answer "What is my cholesterol trend over three years?" or "Generate a one-page health summary for my new specialist" or "Is my HbA1c trajectory consistent with my current treatment plan?" The data is consolidated. The knowledge is not. [13]

**Option F: Ask an AI chatbot.**
Mark has tried pasting lab results into AI tools and asking "Is this normal?" The model answers from general medical knowledge, without context. It does not know Mark is diabetic, so the HbA1c reference range it applies is the wrong one. It does not know his prior results, so it cannot identify a trend. It does not know his medications — Metformin for diabetes, Lisinopril for blood pressure, and a statin added six months ago — so it cannot flag a potential interaction or note that his most recent lipid panel was drawn before the statin was started, making it an unreliable baseline for his cardiologist. It gives general information that may or may not apply to his specific situation. It is more useful than a Google search and less useful than a doctor who knows his history. Neither of those is a high bar.

Every existing solution fails in the same fundamental way: it treats Mark's health data as a file to store and retrieve, not as a longitudinal narrative to understand. The problem is not access. It is intelligence. The folder contains everything Mark needs. What it cannot do is read itself.

---

## The Contradictions That Matter

Here is where it gets interesting. Consider these real-world scenarios:

### Scenario 1: The same test, the same patient, twice in eleven weeks.

Mark's primary care physician ordered a comprehensive lipid panel in November. His cardiologist, seeing him for the first time in February, ordered the same panel. The cardiologist did not know about November. Mark mentioned it; the cardiologist said he preferred to "establish my own baseline." The result: a second lipid panel, a second needle stick, a second bill, and numbers not materially different from the first.

Redundant testing is estimated to account for $5 billion in unnecessary laboratory costs annually. A large study found 23.8% of tested patients had undergone excessive laboratory testing. The data Mark's cardiologist needed already existed. It was eleven weeks old, in a portal the cardiologist had never heard of. [1][3]

Your system needs to surface prior results before a test is re-ordered. But who does it surface them to? The cardiologist, who may not want a patient pre-empting their clinical judgment? The patient, who may not know how to raise this without seeming confrontational? What form does this information take, and how does it create value without creating friction in a clinical relationship?

### Scenario 2: The trend nobody sees.

Mark's HbA1c results over four years, in order: 7.9, 7.6, 7.4, 7.4, 7.1, 6.9, 7.2, 7.0, 6.9. Nine measurements across three systems. Each individual result was reviewed by a physician. But no physician has ever seen all nine in sequence. No one has noted that after a period of improvement, a reversal occurred — the 7.2 after the 6.9 — coinciding with a medication change. The reversal resolved, but had the trend been visible, the adjustment might have been caught earlier. The data to detect this pattern has existed for four years. It lives in three siloed systems, each of which can show one row but not the table.

When your system surfaces a trend, what does it claim? That the 7.2 was a warning sign? That is a clinical inference — and you are not a doctor. That something changed around the 7.2? That is observation, not interpretation. What is the line between surfacing useful patterns and leading patients to draw their own possibly wrong medical conclusions?

### Scenario 3: The new doctor who starts from scratch.

Mark's cardiologist is new. In the first appointment, she asks: "Tell me about your medical history." Mark has four years of history, three chronic conditions, nine HbA1c measurements, six lipid panels, a hospitalization for a non-cardiac event, and a thyroid finding of uncertain significance. He has eleven minutes of appointment time. He summarizes in two minutes. He forgets the thyroid result. He forgets that one lipid panel was drawn during a period when he was on a medication that was later discontinued. The cardiologist's treatment plan is built on this two-minute summary.

Your system should generate a one-page structured health summary for a new provider — a document Mark can email ahead of the appointment or hand over at check-in. But what goes in it? Who decides which results are clinically relevant and which are noise? What if your system surfaces a value the new doctor would have found on their own — does it undermine the diagnostic process? What if it omits something that later turns out to be critical?

### Scenario 4: The number that looks normal but isn't.

Mark's most recent fasting glucose was 104. The lab report flagged it within the general "normal" reference range. His primary care physician's visit summary noted "within normal range." But Mark is a Type 2 diabetic. The appropriate fasting glucose target for a managed diabetic patient is different from the general population reference. The lab printed a population-level range. The physician did not flag the distinction. Mark did not know the distinction existed.

Your system has access to both the lab result and the diagnosis in Mark's record. Should it flag this discrepancy? If it does, how does it communicate without alarming Mark unnecessarily or undermining his physician's interpretation? If it does not, has it failed the core value proposition? The FDA has a regulatory framework for Software as a Medical Device (SaMD). The line between surfacing context and making a clinical inference is real, consequential, and not always obvious from the text of a lab result.

### Scenario 5: The result that belongs to no one.

One of Mark's lab reports from 2022 exists only in paper form. The hospital lab had no portal. They mailed a paper copy. Mark filed it in the folder and later photographed it with his phone. Your system may allow document upload. But the uploaded document is an image — text on a photographed page, with handwritten notes from Mark's doctor in the margin, captured under fluorescent light at 11 PM in a hospital waiting room.

How does your system handle documents where it is not certain it read the data correctly? What does it communicate to Mark when its confidence in a parsed lab value is 70% rather than 100%? Does Mark understand what "confidence" means in this context? If your system ingests a misread value and includes it in a trend, the trend is wrong. If a physician later adjusts a treatment plan based on a data point your system hallucinated from a blurry photograph, the error may not surface for months. This is not a data quality problem. It is a patient safety problem.

### Scenario 6: The recommendation nobody asked for.

Based on Mark's trend data, your system might reasonably observe that his HbA1c improved, plateaued, briefly reversed, and has now restabilized. That is useful. But if his HbA1c were trending upward, your system might observe that "HbA1c has increased over three consecutive measurements." That observation, while factual, carries implicit meaning that Mark will interpret as an alarm. He might cancel a vacation out of anxiety. He might ask his physician for a medication change that is not clinically indicated. He might share the trend with a family member who provides lay advice.

Your system is not a medical advisor. But every factual output it produces will be interpreted as one. Where is the line between information and advice? Who draws it? And how do you maintain that line as Mark's conditions change, as he adds new specialists, and as the platform accumulates four more years of his history?

---

Each of these scenarios demands a different kind of reasoning. Some require document parsing and data extraction under uncertainty. Some require longitudinal pattern recognition across fragmented sources. Some require communication design under health anxiety and time pressure. Some require navigating the regulatory boundary between information and clinical inference. A system that handles only one of these is a file cabinet. A system that handles all of them is a personal health intelligence layer that does not yet exist in any coherent form.

---

## Your Job

**Solve Mark's problem.**

That is the entire brief. Everything below is here to help you think, not to tell you what to build.

---

## Questions to Sit With Before You Design Anything

Do not skim these. Each question points at a design decision that will shape your entire solution. If you cannot answer a question clearly, you are not ready to build that part of the system.

### On the nature of the data

Lab reports arrive as PDFs from portals, as paper mailed to the patient, as printed sheets handed at check-out, as images photographed on phones in hospital waiting rooms, and increasingly as structured FHIR resources from connected systems. An HbA1c value from LabCorp and an HbA1c value from Quest are the same biomarker but may be reported with different reference ranges, different units of measurement, and different test codes. A lipid panel from 2021 and one from 2024 may use different methodologies. How do you build an ingestion layer that normalizes data from these sources into a unified, comparable format? What happens when two labs report the same value with different reference ranges — which range does your system use to contextualize the result?

Not all health data is structured the same way. A CBC contains fifteen or more values. A urine microalbumin is a single number. A thyroid panel has multiple components with complex interpretive dependencies. Some values only make sense in combination: a hemoglobin level means different things depending on whether the patient is iron deficient, receiving chemotherapy, or managing a chronic condition. How does your system represent this complexity without collapsing into a raw list of numbers?


### On what the system needs to know but doesn't

Mark's HbA1c of 6.9 is in the "good control" range for a managed diabetic. But is it improving? Relative to when? And compared to what clinical target? The target for a 56-year-old with well-managed diabetes and hypertension is different from the target for someone older with additional comorbidities or declining kidney function — a common progression in long-term diabetic patients. The normal reference ranges printed on lab reports are population-level standards. Mark is not a population. He is a person with a specific medical history, a specific set of comorbidities, and a treatment plan established by physicians who do not all communicate with each other.

Your system needs to know things like: the target HbA1c for a Type 2 diabetic patient without additional comorbidities is typically below 7.0 per ADA guidelines. Fasting glucose above 100 in a diagnosed diabetic is not "normal" even if it falls within the lab's general reference range. A TSH above 4.0 may warrant monitoring for thyroid dysfunction. Where does this clinical knowledge come from? How do you keep it current as guidelines change? And how does your system distinguish between applying clinical context and providing medical advice — a distinction with regulatory, legal, and ethical weight?

When your system flags a value as outside the expected range for Mark's specific profile, it is making a claim with consequences. If the claim is wrong, it could cause unnecessary anxiety or prompt an unneeded clinical intervention. If the claim is right but unsupported by traceable evidence, it is opinion masquerading as intelligence. How do you ensure your system is applying what it knows rather than generating plausible-sounding clinical context?

### On trust and confidence

If Mark uploads a photographed lab report and your system extracts values from it, what is the probability that every extracted value is correct? What does your system do with values it extracted but cannot verify? If it surfaces uncertain values in a trend and they are wrong, it has corrupted Mark's health record. If it withholds them pending verification, the record is incomplete. If it flags them as uncertain, it places the burden of verification on Mark — who has no way to verify them without re-obtaining the original document.

A physician may access the same aggregated record. If a physician sees a trend that includes a misread value, they may update a treatment plan based on incorrect data. How does your system represent the provenance and confidence level of every data point? How does it communicate that to the patient and to any clinician who accesses the record? Is "70% confident" a number that belongs in a patient-facing interface at all?

### On the line between information and medical advice

The FDA has a regulatory framework for Software as a Medical Device (SaMD) that defines when a digital tool crosses from information into clinical decision support. "Here is your HbA1c trend over time" is information. "Your HbA1c trend suggests your current treatment may not be adequately controlling your blood sugar" is a clinical inference. The difference between those two sentences is significant from a regulatory, legal, and clinical standpoint.

How does your system consistently stay on the right side of that line across all of its outputs? And how do you design for the fact that patients will routinely interpret the information side as though it were the inference side — regardless of how carefully you word it?

### On structure and resilience

If a patient's primary care physician migrates to a new EHR next year, does your system detect the migration and reconnect? If a lab updates its PDF format, does your parser break? If FHIR API access for a given provider goes offline for 72 hours, what does the patient see? Your system depends on external systems that will change without notice.

Your system will also accumulate data over years and decades. What is the data retention model? If Mark asks to delete his account, what happens to the health history he has uploaded? HIPAA specifies patient rights around data access and correction but has specific provisions about what constitutes a covered entity. Is your platform a covered entity? What are the consequences of that answer for how you store, process, share, and delete data?

If a new standard emerges that significantly changes how lab results are classified and coded, how much of your system needs to be rewritten? What does your answer tell you about how the system should be structured from the beginning?

### On the person reading the output

Mark is not a physician. He is a project manager who is comfortable with data but not trained in clinical interpretation. When your system shows him a trend chart of his HbA1c over four years, he will draw conclusions. Some will be correct. Some will be wrong. Some will cause anxiety without cause. Some will catch a genuine pattern his doctors missed.

Your system's output is not a dashboard for clinicians. It is an interface for a person who is worried about his health and trying to have a productive eleven-minute appointment with a cardiologist he met thirty minutes ago. What does he need to see? What does he need to understand? And what does he need your system to not show him, because he cannot act on it without a physician's guidance?

If your system produces a twenty-page analytical report, Mark cannot use it. If it produces a single line that says "You are healthy," he cannot trust it. Where is the level of output that is comprehensive enough to be credible and simple enough to be actionable? And how do you calibrate that for the full range of users — a 28-year-old who just moved cities and started seeing a new doctor, and a 56-year-old managing three chronic conditions?

---

## Why This Matters Beyond the Capstone

Consider the numbers. Over 4 billion laboratory tests are conducted annually in the United States at a cost of $65 billion. Redundant testing wastes an estimated $5 billion each year. Duplication of lab and imaging tests accounts for an estimated $43 billion in wasteful healthcare spending annually. The lack of interoperability between systems costs the healthcare industry over $30 billion more in avoidable inefficiencies. A study of 232 million patients found that nearly 1 in 4 people tested had undergone excessive laboratory testing. One in five laboratory tests performed in the United States may be unnecessary. The waste is not theoretical. It is happening in clinics and hospitals every day, driven not by malice but by the absence of a patient-centered memory. [1][2][3][14]

129 million Americans live with at least one major chronic disease. 42% of adults have two or more. People with five or more chronic conditions average more than twelve physician visits per year — each one a new encounter with a system that does not know their history. [5]

The problem is solvable. The data exists. The standards are emerging. The 21st Century Cures Act mandated patient access to health records through standardized APIs. FHIR R4 is being adopted by major EHR vendors. The regulatory scaffolding to build patient-centered health intelligence is being erected in real time. What does not yet exist is a system that takes all of this — the scattered lab results, the disconnected portals, the photographed paper reports, the manila folders — and turns them into a coherent, longitudinal, intelligent health narrative that the patient actually owns. [10]

One that a person can walk into a new doctor's office with and say: here is everything. Here is the trend. Here is what you need to know.

The student who solves this well does not have a capstone project. They have the foundation of a platform that every patient managing a chronic condition and every physician who sees fragmented patients in thirty-minute appointment slots would use. 129 million people with chronic conditions. A $65 billion laboratory testing industry where one in five tests may be unnecessary. A $43 billion annual cost of duplicated testing and imaging. A $30 billion annual cost of interoperability failure.

**Build it like it matters. Because it does.**

---

## References

[1] American Journal of Clinical Pathology — *Reduction in Unnecessary Clinical Laboratory Testing Through Utilization Management at a US Government Veterans Affairs Hospital*
Estimated redundant lab testing wastes up to $5 billion annually in the United States. Up to 42% of laboratory testing can be considered wasteful depending on clinical setting.
https://academic.oup.com/ajcp/article/145/3/355/1766513

[2] Chart Request / Healthcare IT — *Challenges of Interoperability in Healthcare: Breaking Down the Silos*
Lack of interoperability estimated to cost the U.S. healthcare system over $30 billion each year in avoidable inefficiencies including unnecessary testing and administrative overhead.
https://www.chartrequest.com/articles/interoperability-healthcare-challenges

[3] Archives of Pathology & Laboratory Medicine — *Inappropriate Laboratory Testing: Significant Waste Quantified by a Large-Scale Year-Long Study of Medicare and Commercial Payer Reimbursement*
Study of 232 million people found 23.8% of tested individuals had undergone excessive laboratory testing. Medicare alone may have incurred $1.95–$3.28 billion in excess testing expenses in 2019.
https://meridian.allenpress.com/aplm/article/149/3/253/501199

[4] Office of the National Coordinator for Health IT (ONC) — *Individuals' Access and Use of Patient Portals and Smartphone Health Apps, 2024*
In 2024, 59% of Americans had multiple online medical records or patient portals with different organizations. Breakdown by provider type (primary care 68%, other providers 40%, insurer 30%, lab 29%, pharmacy 24%, hospital 22%).
https://healthit.gov/data/data-briefs/individuals-access-and-use-patient-portals-and-smartphone-health-apps-2024/

[5] RAND Corporation — *Multiple Chronic Conditions in the United States*
Nearly 150 million Americans live with at least one chronic condition; around 100 million have more than one. Nearly 30 million live with five or more chronic conditions. Those with five or more conditions average 12+ physician visits per year.
https://www.rand.org/pubs/tools/TL200/TL221/RAND_TL221.pdf

[6] CDC — *Chronic Disease Prevalence in the US: Sociodemographic and Geographic Variations*
An estimated 129 million people in the US have at least one major chronic disease. About 90% of the annual $4.1 trillion health care expenditure is attributed to managing and treating chronic diseases and mental health conditions.
https://www.cdc.gov/pcd/issues/2024/23_0267.htm

[7] CDC — *Trends in Multiple Chronic Conditions Among US Adults, By Life Stage, 2013–2023*
Approximately 6 in 10 young, 8 in 10 midlife, and 9 in 10 older US adults report one or more chronic conditions. Multiple chronic conditions affect more than half (128 million) of US adults.
https://www.cdc.gov/pcd/issues/2025/24_0539.htm

[8] CDC — *Chronic Disease Prevalence in the US*
About 90% of the annual $4.1 trillion US healthcare expenditure is attributed to managing and treating chronic diseases and mental health conditions.
https://www.cdc.gov/pcd/issues/2024/23_0267.htm

[9] Healthcare Information Technology — *How Fragmented Health Records and Its Limited Accessibility Affect Quality of Care and Patients' Satisfaction*
Decentralized storage of health records leads to incomplete records in multiple places, poor access to current records, and duplicated services including lab tests, imaging, and prescriptions.
https://jk2015site.wordpress.com/noteworthy-assignments/how-fragmented-health-records-and-its-limited-accessibility-affect-quality-of-care-and-patients-satisfaction/

[10] MDPI Information — *From Data Silos to Health Records Without Borders: A Systematic Survey on Patient-Centered Data Interoperability*
Current FHIR standards prioritize institutional interoperability rather than patient-centered interoperability. Patients cannot access their own medical records in a timely manner when stored across various healthcare systems.
https://www.mdpi.com/2078-2489/16/2/106

[11] PBS NewsHour / Healthcare Finance News — *Unnecessary Medical Tests, Treatments Cost $200 Billion Annually, Cause Harm*
Patient accounts of repeated unnecessary blood draws "because the doctors couldn't get their hands on earlier results." Some experts estimate at least $200 billion wasted annually on excessive testing and treatment.
https://www.pbs.org/newshour/health/200-billion-perils-unnecessary-medical-tests

[12] Verato / AHIMA — *Duplicate Medical Records: Causes, Impacts & Solutions*
A recent AHIMA study showed that repeated tests or treatment delays caused by duplicate or missing records added an average of $1,100 to the cost of the patient's care.
https://verato.com/blog/duplicate-medical-records/

[13] Metriport — *Patient Tools and Apps to Access Health Records*
Overview of existing patient-facing tools including Apple Health, MyChart, OneRecord, and Fasten Health, and their current coverage gaps and limitations.
https://www.metriport.com/blog/patient-tools-and-apps-to-access-health-records

[14] ResearchGate / PMC — *Reducing Overuse of Repeat Testing*
Duplication of lab and imaging tests accounts for an estimated $43 billion in wasteful healthcare spending annually.
https://www.researchgate.net/figure/Cost-for-Type-and-Screen-Assay_tbl1_321626620

[15] PMC — *Duplicate Patient Records — Implication for Missed Laboratory Results*
Duplicate records were associated with a significantly higher rate of missed laboratory results (OR=1.44). Duplicate records lead to patient harm and considerable costs.
https://pmc.ncbi.nlm.nih.gov/articles/PMC3540536/

[16] Medical Economics / 4medica — *Why Duplicate and Mismatched Patient Records Are a Bigger Problem Than You Think*
Some healthcare organizations have medical record duplication rates as high as 30%; 10% is common. A Texas hospital found 22% of patient records were duplicates. In 4% of confirmed duplicate record cases, clinical care was directly affected.
https://www.medicaleconomics.com/view/why-duplicate-and-mismatched-patient-records-are-a-bigger-problem-than-you-think

[17] PMC — *Lab Testing Overload: A Comprehensive Analysis of Overutilization in Hospital-Based Settings*
Over 4 billion laboratory tests are conducted annually in the United States, costing $65 billion. One out of every five inpatient laboratory examinations ordered is unnecessary.
https://pmc.ncbi.nlm.nih.gov/articles/PMC10857549/

[18] Managed Healthcare Executive — *Lab Testing Volume, Spend to Rise*
As many as one out of five tests performed may be unnecessary. A 2020 study found that repeat testing of normal test results occurred in up to 85% of patients.
https://www.managedhealthcareexecutive.com/view/lab-testing-volume-spend-to-rise

[19] PMC — *Patient Health Record Smart Network: Challenges and Trends for a Smarter World*
Overview of global PHR adoption, challenges in interoperability, and the role of AI, IoT, and blockchain in modern personal health record systems. Reviews PHR architectures, data sources, and policy landscape from 2020–2024.
https://pmc.ncbi.nlm.nih.gov/articles/PMC12196791/
