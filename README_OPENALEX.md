# OpenAlex configuration

1. Copy [.env.example](.env.example) to .env at the repository root.
2. Fill in the values:
   - OPENALEX_API_KEY: your OpenAlex API key (optional but recommended)
3. Run the pipeline from the project directory.

Example:

```powershell
Copy-Item .env.example .env
# edit .env
python LibroBlanco_Pulso_pipeline_v1/LibroBlanco_Pulso/scripts/run_pipeline.py
```
