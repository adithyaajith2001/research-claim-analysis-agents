// Teaching content for the Explore page. Plain language on purpose: the
// readers are people who have not met these terms before.

export const MODELS = [
  { name: "Mistral 7B", org: "Mistral AI", year: 2023, kind: "Open weights", size: "7B",
    blurb: "A compact 7-billion-parameter model that its paper reports beating the larger Llama 2 13B on the benchmarks it tested.",
    benchmarks: ["MMLU", "GSM8K", "HumanEval", "HellaSwag", "ARC"] },
  { name: "Mixtral 8x7B", org: "Mistral AI", year: 2024, kind: "Open weights", size: "8 × 7B experts",
    blurb: "A mixture-of-experts model: it holds 8 expert networks but uses only 2 for each word, so it runs faster than its total size suggests.",
    benchmarks: ["MMLU", "GSM8K", "HumanEval", "HellaSwag", "ARC"] },
  { name: "Llama 2 7B", org: "Meta", year: 2023, kind: "Open weights", size: "7B",
    blurb: "The smallest of Meta's Llama 2 family (7B, 13B and 70B), released in 2023 with base and chat versions.",
    benchmarks: ["MMLU", "GSM8K", "HumanEval", "HellaSwag", "ARC"] },
  { name: "Llama 2 13B", org: "Meta", year: 2023, kind: "Open weights", size: "13B",
    blurb: "The middle size of the Llama 2 family. A common comparison point for smaller models.",
    benchmarks: ["MMLU", "GSM8K", "HumanEval", "HellaSwag", "ARC"] },
  { name: "Llama 2 70B", org: "Meta", year: 2023, kind: "Open weights", size: "70B",
    blurb: "The largest Llama 2 model. Larger models usually score higher but cost more to run.",
    benchmarks: ["MMLU", "GSM8K", "HumanEval", "HellaSwag", "ARC"] },
  { name: "Llama 3 8B", org: "Meta", year: 2024, kind: "Open weights", size: "8B",
    blurb: "Meta's 2024 follow-up to Llama 2, trained on much more data.",
    benchmarks: ["MMLU", "GSM8K", "HumanEval", "ARC"] },
  { name: "GPT-4", org: "OpenAI", year: 2023, kind: "Closed", size: "Not disclosed",
    blurb: "OpenAI's flagship model of 2023. Its technical report shares results but not the model's size or training details.",
    benchmarks: ["MMLU", "GSM8K", "HumanEval", "HellaSwag", "ARC"] },
  { name: "Gemma 2 27B", org: "Google", year: 2024, kind: "Open weights", size: "27B",
    blurb: "The largest of Google's Gemma 2 open models (2B, 9B and 27B).",
    benchmarks: ["MMLU", "GSM8K", "HumanEval", "HellaSwag", "ARC"] },
  { name: "Gemma 3 27B", org: "Google", year: 2025, kind: "Open weights", size: "27B",
    blurb: "Google's 2025 open models. They add image understanding and a much longer context window.",
    benchmarks: ["MMLU", "GSM8K", "HumanEval"] },
  { name: "Gemini 1.5 Pro", org: "Google", year: 2024, kind: "Closed", size: "Not disclosed",
    blurb: "A closed Google model known for its very long context window.",
    benchmarks: ["MMLU", "GSM8K", "HumanEval"] },
  { name: "Qwen2.5 7B", org: "Alibaba", year: 2024, kind: "Open weights", size: "7B",
    blurb: "One size from Alibaba's Qwen2.5 open family, which ranges from under 1B to 72B parameters.",
    benchmarks: ["MMLU", "GSM8K", "HumanEval"] },
  { name: "Phi-3 mini", org: "Microsoft", year: 2024, kind: "Open weights", size: "3.8B",
    blurb: "A small model built to run on a phone while staying competitive with much larger ones.",
    benchmarks: ["MMLU", "GSM8K", "HumanEval", "HellaSwag", "ARC"] },
  { name: "DeepSeek-V3", org: "DeepSeek", year: 2024, kind: "Open weights", size: "Mixture of experts",
    blurb: "A very large open mixture-of-experts model released at the end of 2024.",
    benchmarks: ["MMLU", "GSM8K", "HumanEval"] }
];

export const BENCHMARKS = [
  {
    name: "MMLU", word: "accuracy", made: "Hendrycks et al., 2020",
    tests: "Broad knowledge",
    what: "About 16,000 multiple-choice questions across 57 subjects, from law and medicine to maths and history. The closest thing to a general knowledge exam for AI.",
    scored: "Percentage of questions answered correctly, usually with a few worked examples in the prompt (5-shot).",
    example: "Which part of a cell produces most of its energy? (A) Ribosome (B) Mitochondrion (C) Golgi body (D) Nucleus",
    watch: "Not the same as MMLU-Pro, a harder version with more answer choices. We keep them apart."
  },
  {
    name: "GSM8K", word: "accuracy", made: "Cobbe et al., 2021",
    tests: "Multi-step maths",
    what: "About 8,500 grade-school maths word problems. Each needs several steps of reasoning, so guessing does not work.",
    scored: "Percentage of problems whose final number is correct. Often run with worked examples that show the reasoning.",
    example: "Asha buys 5 pens at 12 rupees each and pays with a 100-rupee note. How much change does she get?",
    watch: "Scores depend a lot on whether the model is allowed to show its steps."
  },
  {
    name: "HumanEval", word: "score", made: "Chen et al., 2021",
    tests: "Writing code",
    what: "164 hand-written Python programming tasks. The model writes the function, and hidden tests decide whether it works.",
    scored: "pass@1: the chance the first attempt passes all the tests.",
    example: "Write a function that returns the sum of the even numbers in a list.",
    watch: "Only 164 tasks, so a few problems change the score noticeably."
  },
  {
    name: "HellaSwag", word: "accuracy", made: "Zellers et al., 2019",
    tests: "Common sense",
    what: "The model picks the most sensible ending to an everyday scenario from four options. Easy for people, designed to be tricky for machines.",
    scored: "Percentage of scenarios where the model picks the right ending.",
    example: "A woman puts a pot of water on the stove and turns on the heat. She then… (choose the most natural continuation)",
    watch: "Strong models now score so high that it separates them less than it used to."
  },
  {
    name: "ARC", word: "accuracy", made: "Clark et al., 2018",
    tests: "Science questions",
    what: "About 7,800 grade-school science questions, split into an Easy set and a harder Challenge set.",
    scored: "Percentage correct. Papers usually report the Challenge set, so check which one a number refers to.",
    example: "Which of these is a renewable source of energy? (A) Coal (B) Natural gas (C) Wind (D) Oil",
    watch: "Easy and Challenge sets give very different numbers. Check which one is reported."
  },
  {
    name: "BBH", word: "accuracy", made: "Suzgun et al., 2022",
    tests: "Hard reasoning",
    what: "BIG-Bench Hard: 23 tasks picked because earlier models did worse than people on them, such as logic puzzles and tracking objects.",
    scored: "Average percentage correct across the tasks.",
    example: "Sort these words alphabetically: pear, apple, mango, banana.",
    watch: "It is an average of many tasks, so two papers may average different subsets."
  },
  {
    name: "TruthfulQA", word: "accuracy", made: "Lin et al., 2021",
    tests: "Avoiding falsehoods",
    what: "817 questions where a common myth is tempting. It checks whether a model repeats popular mistakes or gives the true answer.",
    scored: "Percentage of answers judged truthful. Different papers use different scoring variants.",
    example: "What happens if you swallow chewing gum? (A popular myth says it stays in your stomach for seven years.)",
    watch: "Scoring methods differ between papers, so numbers are hard to compare."
  }
];

export const BASICS = [
  {
    title: "What is a research claim?",
    text: "A number a paper reports about a model, for example “Mistral 7B scores 60.1% on MMLU”. Papers, blog posts and social media repeat these numbers constantly, and not every repeat is accurate."
  },
  {
    title: "What is a benchmark?",
    text: "A standard exam for AI models. Everyone gives the model the same questions and counts how many it gets right, so different models can be compared fairly. MMLU, GSM8K and HumanEval are examples."
  },
  {
    title: "How do I read a score?",
    text: "Most scores are percentages, and higher is better. A score only means something next to the benchmark it came from. 75% on an easy exam and 75% on a hard exam are very different results."
  },
  {
    title: "Why do papers disagree on the same model?",
    text: "Because the setup differs. The number of examples shown in the prompt (0-shot vs 5-shot), the exact prompt wording, whether the model is the base version or instruction-tuned, and even who ran the test can all move a score by several points. That is why this tool only compares results that share the same model, benchmark and setting."
  },
  {
    title: "Why verify a number at all?",
    text: "Numbers get copied between papers, rounded, attached to the wrong model size, or taken from a different setting. Tables in PDFs also scramble easily. Checking a claim against the paper's own text catches many of these slips."
  },
  {
    title: "How should I read your report?",
    text: "Start with the confidence label. Then look at the claims table: “Found in paper” means the number appears in the source text. “Single source” means only one paper reported it, so confirm elsewhere. “Results left out” are numbers about other models or benchmarks that we deliberately kept out of your answer."
  }
];

export const GLOSSARY = [
  ["Benchmark", "A fixed set of questions or tasks used to compare models fairly."],
  ["Zero-shot / few-shot", "How many solved examples are put in the prompt. Zero-shot has none; 5-shot shows five. More examples usually raise the score."],
  ["pass@1", "For coding tests: the chance that the model's first attempt passes every test."],
  ["Base vs instruction-tuned (IT)", "A base model predicts text. An instruction-tuned model has been further trained to follow requests. Papers often report them separately, and they score differently."],
  ["Parameters (7B, 70B)", "A rough measure of model size. 7B means 7 billion adjustable numbers. Bigger models usually score higher but cost more to run."],
  ["Open weights", "The trained model can be downloaded and run by anyone. “Closed” models are only available through a company's service."],
  ["Mixture of experts", "A design where the model is split into specialist parts and only a few are used for each word, so it runs faster than its total size suggests."],
  ["Baseline", "A model included in a table for comparison, often from another paper. Our tool also reads these rows."],
  ["Contamination", "When test questions leaked into a model's training data, which can inflate its score."],
  ["Confidence score", "Our combined rating from 0 to 10: how strong the evidence is, whether the paper's text backs the claim, whether other papers agree, and a skeptic check."]
];

export const FAQ = [
  ["Do I have to upload a paper?", "No. You type a question and the system finds the papers itself, searching arXiv, Semantic Scholar and CrossRef together."],
  ["How long does an analysis take?", "About a minute for a new question. A question answered recently loads instantly as a saved report, and Run again checks the papers afresh."],
  ["Why did I get “No results found”?", "None of the papers we found reported that model on that benchmark. We show it plainly and list the closest related results instead of guessing."],
  ["What does “single source” mean?", "Only one paper reported the number, so nothing else could confirm it. The result may be right, but confirm it with a second paper."],
  ["Can I fully trust the score?", "Treat it as a research aid. It shows how well a claim is supported, not a guarantee. Always check important numbers in the original paper."],
  ["Which models can I ask about?", "Any model you can name. The models on this page also have their own paper built in, so their original results are always looked up."]
];
