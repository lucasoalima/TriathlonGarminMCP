# CV & Personal Statement snippets (English)

Honest wording — reflects what the repository actually does (deterministic guardrails +
evaluation harness + model-comparison scaffold on top of a third-party MCP server). No RAG,
no model training claimed, because those are not implemented.

## CV bullets (2)

- Built a **neuro-symbolic guardrail layer** (Python) that validates and audits an LLM agent's
  triathlon-coaching decisions over the **Model Context Protocol (MCP)**, and designed an
  **offline evaluation harness** (precision/recall, Cohen's κ, confusion matrices) over
  hand-labeled datasets — **117 passing tests**, zero runtime dependencies.
- Implemented a **pluggable model-comparison framework** (deterministic baseline, local **Ollama**,
  **Anthropic Claude**) measuring agreement between LLM decisions and a deterministic safety oracle,
  and documented limitations, bias and data privacy (LGPD) in a **model card**.

## Personal statement / RPEL paragraph (1)

My transition into AI Engineering is grounded in building and *measuring* LLM systems rather than
just using them. In my open-source project *Triathlon Coach*, I designed a neuro-symbolic layer in
which a deterministic rules engine acts as a safety guardrail and auditor around an LLM agent
exposed through the Model Context Protocol: the language model handles dialogue and final decisions,
while the deterministic layer validates every training prescription and audits whether the agent
followed a safety protocol. Crucially, I built an evaluation harness with hand-labeled datasets and
reported real metrics — 79% agreement with human safety labels (Cohen's κ = 0.58) on the safety
gate, 94% accuracy on execution classification — and a framework to compare a simple baseline
against local (Ollama) and frontier (Claude) models. I also wrote a model card analysing the
system's limitations, bias and privacy implications. This work reflects exactly what I want to
deepen in an MSc in Artificial Intelligence: machine-learning evaluation, NLP with large language
models, and responsible, well-engineered AI.
