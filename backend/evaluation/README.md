# Accuracy evaluation

Measures how often ResearchClaimAI extracts the right result, compared with a
person reading the same papers. The labels must come from people; the script
never guesses them.

1. Start the backend (`uvicorn main:app --reload`).
2. From the `backend` folder, collect claims:

       python evaluation/evaluate.py collect --queries evaluation/queries.txt --out evaluation/labels.csv

3. Open `labels.csv` in Excel. For every row open the paper and check the table.
   Fill `human_correct` with `yes` or `no`. A second person should label a
   sample of rows so you can report how often you agree.
4. List results the system missed in `missed.csv` (copy `missed_template.csv`).
5. Score:

       python evaluation/evaluate.py score --labels evaluation/labels.csv --missed evaluation/missed.csv

The report (`evaluation/report.md`) gives precision, recall, how well the
"Found in paper" check agrees with the person, and 95% intervals. Report the
interval, not only the percentage, and say who labelled the data.
