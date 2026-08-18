# Report Prompts

These prompts are downstream of the data pipeline. They must use only checksum-protected files in `artifacts/report_inputs/` plus the explicitly listed audit/configuration files.

Required order:

1. `01_data_auditor.md`
2. `02_statistical_interpreter.md`
3. `03_report_writer.md`
4. `04_adversarial_reviewer.md`
5. `05_final_reviser.md`

The prompts forbid recovering numbers from chat, notebook prose, notebook display output, external memory or web searches. If a requested result is absent from the empirical bundle, the report must say it is unavailable.
