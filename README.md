# Aerospace Medicine Assistant

A chat client for an Azure AI Foundry agent that answers questions about pilot
health, fatigue, and aeromedical standards. The agent, its knowledge base, and
any connected tools are configured in Azure AI Foundry — this repo just
provides two ways to talk to it.

## Files

| File                 | What it is                                                          |
| -------------------- | -------------------------------------------------------------------- |
| `aerospace_app.py`   | Streamlit web UI — chat interface, sidebar status, tool-approval flow |
| `aerospace-agent.py` | Minimal command-line client for the same agent                       |
| `requirements.txt`   | Python dependencies                                                  |
| `.streamlit/config.toml` | Theme for the Streamlit UI                                       |

## Setup

1. **Install dependencies** (a virtual environment is recommended):

   ```bash
   pip install -r requirements.txt
   ```

2. **Authenticate with Azure.** Both clients use `DefaultAzureCredential`
   (environment and managed-identity credentials excluded), so sign in with
   the Azure CLI first:

   ```bash
   az login
   ```

3. **Configure the agent connection.** Create a `.env` file in the project
   root:

   ```
   PROJECT_ENDPOINT=<your Azure AI Foundry project endpoint>
   AGENT_NAME=<your agent name>
   ```

## Usage

**Web UI:**

```bash
streamlit run aerospace_app.py
```

Opens a chat interface at `http://localhost:8501`. If the agent calls a tool
that needs approval, a card appears with the tool name, server, and arguments
— review it and submit Approve or Deny before the conversation continues.

**Command line:**

```bash
python aerospace-agent.py
```

Type your question at the `You:` prompt. Type `history` to print the full
conversation so far, or `quit` to exit. Tool approvals are confirmed inline
with a `yes`/`no` prompt.

## Notes

- Each run/session starts a fresh conversation with the agent; history is not
  persisted between runs.
- This assistant is for education and reference only — it is not a substitute
  for evaluation by a certified aviation medical examiner.
