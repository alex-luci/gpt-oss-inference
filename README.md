# GPT‑OSS Kitchen Assistant (PyQt UI)

An autonomous, tool‑using kitchen assistant that plans, validates, and executes robot actions via GPT‑OSS with gr00t. The UI is built with PyQt5 and communicates with the local GPT‑OSS chat API and robot socket.

## What’s in this repo
- `gpt-oss-chat-function-ui.py`: PyQt UI application and the `GPTOSSChatBot` backend
- Minimal project state; no extra scripts or assets

## Key capabilities
- Fully autonomous flow (no hardcoded task logic):
  - Creates a plan (`create_plan`)
  - Validates plan with an AI-only reviewer (`review_plan`)
  - Executes approved plan with canonical robot commands (`execute_robot_command`)
  - Tracks and updates kitchen state (`update_kitchen_state`)
  - Marks tasks complete (`mark_task_complete`)
- Canonical command enforcement: exact phrases only (no paraphrasing) so gr00t understands actions.
- Streaming assistant messages with smooth, throttled updates and emoji-friendly rendering.
- Activity Log panel showing concise, high-signal runtime logs (tools, steps, review results, HTTP fallback notes).
- Dark theme UI with:
  - Chat (left pane)
  - Status & Activity (right pane): Robot Status, User Task, Executing, Next Step, Plan Approved
  - Checklist (half height) with widening and elided long texts
  - Kitchen State with human-friendly Yes/No formatting
  - Buttons: Refresh Status, Clear Checklist
  - Activity Log (under buttons)
- No tool logs in chat; only meaningful assistant messages are shown to the user.

## Autonomous lifecycle
1. User requests a task (e.g., “make a pineapple smoothie”).
2. Assistant generates a plan using canonical robot commands only.
3. Assistant calls `review_plan`:
   - The reviewer approves if ordering and preconditions are valid and all steps are canonical.
   - If not approved, the reviewer returns a minimal revision (reorder/insert/remove only).
4. Assistant executes the approved plan end-to-end without asking for “go/yes”.
5. After each action: state updates and checklist progression.
6. Assistant communicates progress and completion succinctly.

## Canonical robot commands
The assistant must use exactly these phrases:
- "Open the left cabinet door"
- "Close the left cabinet door"
- "Take off the lid from the gray recipient and place it on the counter"
- "Pick up the lid from the counter and put it on the gray recipient"
- "Pick up the green pineapple from the left cabinet and place it in the gray recipient"
- "Put salt in the gray recipient"

## Model tools (function calling)
- `execute_robot_command(language_instruction, use_angle_stop=True)`
- `get_robot_status()`
- `update_kitchen_state(state_updates)`
- `mark_task_complete(task_id)`
- `get_current_plan()`
- `create_plan(tasks)`
- `review_plan(instructions?)`

## Design principles
- AI-only validation: no hardcoded guards; planning and review are delegated to the model.
- Canonical action contract: exact strings ensure gr00t can perform every step.
- Concise logging: terminal and Activity Log prioritize signal over noise.
- Robust streaming: newlines are deduplicated; rendering avoids blank gaps.

## Notes
- Robot socket sending in `send()` can be toggled; currently the raw socket code is present but commented for safety. Enable as needed to control a real robot.
- If the streaming endpoint returns no content, a non-streaming fallback is attempted and mirrored into the UI for consistency.
- The Plan Approved status reflects the latest `review_plan` result and gates execution behavior as instructed in the system prompt.
