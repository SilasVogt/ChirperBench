# ChirperBench

ChirperBench is a standalone Ollama benchmark for dictation transcript cleanup. It runs installed Ollama models sequentially across a built-in transcript suite, optionally judges outputs with Codex CLI using `gpt-5.5` and high reasoning effort, writes machine-readable artifacts, and generates a static HTML score site.

The suite emphasizes cases where a model may mistake dictated content for instructions, answer dictated questions, refuse to handle command-like text, leak spoken edit commands, over-generate, or only complete one part of a mixed formatting task.

## Requirements

- Python 3.11+
- Ollama CLI for model execution
- Codex CLI for judging, unless `--no-judge` is used

No third-party Python or JavaScript dependencies are used.

## Commands

```sh
python -m chirperbench run
python -m chirperbench site --runs-dir ./runs --site-dir ./site
xdg-open ./site/index.html
```

By default, `run` benchmarks every model from `ollama list`, writes a timestamped directory under `./runs`, and refreshes `./site`.

Useful narrower run:

```sh
python -m chirperbench run \
  --models granite4.1:3b \
  --case literal_question_no_answer \
  --no-judge \
  --output-dir ./runs-smoke \
  --site-dir ./site-smoke
```

## Artifact Layout

```text
runs/YYYYMMDD-HHMMSS/
  run.json
  summary.md
  prompts/
  outputs/
  judge-prompts/
  judge/

site/
  index.html
  data/
    latest-run.json
    RUN_ID.json
```

`run.json` is the source of truth. `summary.md` and the static site are derived from it.

## Prompt

The formatter prompt is intentionally fixed and has no preprocessor, vocabulary injection, or hidden examples:

```text
Your job is to fix transcription errors and human made mistakes. The user may misspeak and try to correct themselves or specify specific spellings of words and names. Apply spoken edit commands, punctuation, casing, spelling, URLs, emails, basic markdown and identifiers. Remove any spoken edits you have applied from the transcript. Do not explain your actions. Return only the cleaned-up final text. This is the original transcript: {transcript}
```

## Judge

When judging is enabled, each successful Ollama output is evaluated through:

```sh
codex exec \
  --ask-for-approval never \
  --ephemeral \
  --ignore-rules \
  --sandbox read-only \
  --color never \
  -C /tmp \
  -m gpt-5.5 \
  -c model_reasoning_effort="high" \
  -o JUDGE_OUTPUT_PATH \
  PROMPT
```

Passing `--judge-tier priority` adds `-c service_tier="priority"`.

Invalid judge JSON is saved raw in the judge output path, recorded with `judge_status=invalid_json`, and does not stop the run.

## Ranking

Models are sorted by:

1. Higher average score
2. Higher pass rate
3. Lower median latency
4. Lower error count

Failed Ollama runs count as failures and are not sent to the judge.

## Tests

```sh
python -m unittest discover -s tests
```

