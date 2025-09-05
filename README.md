# Kitchen Robot Assistant (GPT-OSS UI)

This repository contains a single Tkinter desktop application that connects to a local GPT‑OSS model and a local robot control server, enabling end‑to‑end kitchen task automation via native function calling.

## What's included

- `gpt-oss-chat-function-ui.py`: The only app in the repo. A modern UI for chatting with GPT‑OSS and letting it control a kitchen robot via function calls.
- `README.md`: This file.

All previous experimental scripts were removed to keep the repo focused and easy to run.

## Requirements

- Python 3.8+
- A running GPT‑OSS server at `http://localhost:11434` (chat API compatible)
- A robot control server listening on `localhost:7000` (raw TCP socket). The app sends JSON commands like:
  ```json
  {"command": "execute_task", "language_instruction": "Open the left cabinet door", "actions_to_execute": 150, "use_angle_stop": true}
  ```

## Install

Create a virtual environment (optional) and install dependencies:
```bash
pip install requests
```

## Run

```bash
python gpt-oss-chat-function-ui.py
```

## How it works (brief)

- You chat with GPT‑OSS from the left panel; the model can decide to call functions to control the robot.
- The app exposes two tools to GPT‑OSS:
  - `execute_robot_command(language_instruction, actions_to_execute=150, use_angle_stop=True)`
  - `get_robot_status()`
- Tool calls are executed and the results are added back to the conversation so the model can iterate.
- The right panel shows robot status, the current message being executed, and (optionally) a checklist if the model emits one.

## Current behavior

- No hardcoded kitchen logic: the model is free to plan and act. There are no preconditions or forced steps in the app.
- No heuristic state updates: the UI does not guess state from text; status comes from the robot.
- Task completion is not auto‑inferred; the model can communicate progress in natural language or by emitting a plan.

## Customizing

- To change the system prompt or tool descriptions, edit `_get_system_prompt()` and the `tools` schema inside `_call_gpt_oss()`.
- If you want stricter sequencing (e.g., always remove lid before adding salt), re‑introduce guards inside `execute_robot_command()` or a planner in `_plan_tasks()`.

## Notes

- This UI assumes both GPT‑OSS and the robot server are reachable locally. Adjust endpoints in `GPTOSSChatBot.__init__` if needed.
- The UI uses background threads and queues for smooth updates.

## License

Experimental/educational use only.
